#!/usr/bin/env python3
"""Simulated selective gas sensor and hexagonal gas-risk map.

A single gas sensor (e.g. an MQ-4 = CH4 sensor) is "mounted" on the robot.
The world holds MULTIPLE gas zones (CH4, CO, CO2, ...). The sensor responds
ONLY to its target gas (plus optional cross-sensitivity) -- which proves that a
specific sensor measures a specific gas: the robot reads high in the CH4 zone
and ~0 in the CO/CO2 zones, even though those gases are physically present
(see the /gas/truth/<SPECIES> ground-truth topics).

Pipeline:
  TF(map->base_link) -> per-species gas fields -> selective sensor reading
     -> hex grid -> events + markers + JSON sidecar  (+ occupancy map auto-save)

Topics:
  /gas/concentration     std_msgs/Float32   the sensor's reading (target gas, ppm)
  /gas/truth/<SPECIES>   std_msgs/Float32   ground-truth field per gas (proof)
  /gas/hex               MarkerArray        hex heatmap (by sensor reading)
  /gas/sources           MarkerArray        gas-zone markers (per gas, labeled)

Saved files (where the data goes):
  <output_path>          hex cells + events + sensor/world config   (auto, atomic)
  <map_output>.pgm/.yaml occupancy map snapshot           (auto: periodic+shutdown)
"""
import json
import math
import os
import tempfile

import numpy as np
import rclpy
import tf2_ros
import yaml
from geometry_msgs.msg import Point
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import ColorRGBA, Float32
from visualization_msgs.msg import Marker, MarkerArray

SQRT3 = math.sqrt(3.0)
LEVEL_NAMES = ('safe', 'warning', 'danger')

DEFAULT_DATA_DIR = os.environ.get(
    'SCOUT2MAP_DATA_DIR',
    os.path.join(os.path.expanduser('~'), 'scout2map_data'),
)

# distinct colors per gas species (for the /gas/sources zone markers)
GAS_COLORS = {
    'CH4': (0.20, 0.45, 1.00), 'CO': (1.00, 0.55, 0.00), 'CO2': (0.65, 0.25, 0.85),
    'H2S': (0.85, 0.85, 0.10), 'NH3': (0.10, 0.85, 0.85), 'LPG': (0.40, 0.80, 0.30),
}


# --- pointy-top hexagon math, axial coordinates, size = circumradius R ---------
def axial_round(qf, rf):
    xf, zf = qf, rf
    yf = -xf - zf
    rx, ry, rz = round(xf), round(yf), round(zf)
    dx, dy, dz = abs(rx - xf), abs(ry - yf), abs(rz - zf)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def axial_from_xy(x, y, R):
    return axial_round((SQRT3 / 3.0 * x - 1.0 / 3.0 * y) / R, (2.0 / 3.0 * y) / R)


def xy_from_axial(q, r, R):
    return (R * SQRT3 * (q + r / 2.0), R * 1.5 * r)


def hex_corners(cx, cy, R):
    return [(cx + R * math.cos(math.radians(60 * i - 30)),
             cy + R * math.sin(math.radians(60 * i - 30))) for i in range(6)]


class GasSensorNode(Node):
    def __init__(self):
        super().__init__('gas_sensor_node')

        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('update_rate', 5.0)
        self.declare_parameter('hex_size', 0.3)
        self.declare_parameter('config_file', '')
        self.declare_parameter(
            'output_path', os.path.join(DEFAULT_DATA_DIR, 'maps', 'sim_gas_hex.json'))
        self.declare_parameter(
            'map_output', os.path.join(DEFAULT_DATA_DIR, 'maps', 'sim_map'))

        self.base_frame = self.get_parameter('base_frame').value
        self.map_frame = self.get_parameter('map_frame').value
        rate = float(self.get_parameter('update_rate').value)
        self.R = float(self.get_parameter('hex_size').value)
        self.output_path = self.get_parameter('output_path').value
        self.map_output = self.get_parameter('map_output').value
        cfg_path = self.get_parameter('config_file').value

        if rate <= 0.0:
            raise ValueError('update_rate must be greater than zero')
        if self.R <= 0.0:
            raise ValueError('hex_size must be greater than zero')

        # --- defaults (overridden by config_file) ---
        self.warning, self.danger = 200.0, 600.0
        self.target_gas = 'CH4'
        self.cross = {}  # {species: coeff}
        self.sources = [{'name': 'zone_CH4', 'x': 1.0, 'y': 0.0,
                         'gas': 'CH4', 'peak_ppm': 1000.0, 'sigma': 0.4}]
        if cfg_path and os.path.exists(cfg_path):
            with open(cfg_path, encoding='utf-8') as config_stream:
                cfg = yaml.safe_load(config_stream) or {}
            th = cfg.get('thresholds', {})
            self.warning = float(th.get('warning_ppm', self.warning))
            self.danger = float(th.get('danger_ppm', self.danger))
            sc = cfg.get('sensor', {})
            self.target_gas = sc.get('target_gas', self.target_gas)
            self.cross = sc.get('cross_sensitivity', {}) or {}
            if cfg.get('gas_sources'):
                self.sources = cfg['gas_sources']
            self.get_logger().info(f'loaded gas config from {cfg_path}')
        else:
            self.get_logger().warn(f'config_file not found ({cfg_path!r}); using defaults')

        self._validate_configuration()
        self.species = sorted({s.get('gas', 'gas') for s in self.sources})

        # occupancy map params (for the trinary .pgm we auto-save)
        self.occ_th, self.free_th = 0.65, 0.25

        # state
        self.cells = {}        # (q,r) -> dict
        self.cell_level = {}   # (q,r) -> highest logged level
        self.events = []
        self.latest_map = None
        self.map_res = 0.05
        self.map_origin = [0.0, 0.0]

        # TF + I/O
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.pub_conc = self.create_publisher(Float32, '/gas/concentration', 10)
        self.truth_pubs = {g: self.create_publisher(Float32, f'/gas/truth/{g}', 10)
                           for g in self.species}
        self.pub_hex = self.create_publisher(MarkerArray, '/gas/hex', 1)
        source_qos = QoSProfile(depth=1)
        source_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.pub_src = self.create_publisher(MarkerArray, '/gas/sources', source_qos)
        self.create_subscription(OccupancyGrid, '/map', self._map_cb, 1)

        self.create_timer(1.0 / max(rate, 0.5), self._tick)
        self.create_timer(5.0, self._save)
        self.create_timer(5.0, self._publish_sources)
        self.create_timer(20.0, self._save_map)   # periodic occupancy-map snapshot

        self.get_logger().info(
            f'gas_sensor_node up | SENSOR target={self.target_gas} '
            f'cross={self.cross} | world species={self.species} | hex R={self.R}m '
            f'| json={self.output_path} | map={self.map_output}.pgm')
        self._publish_sources()

    def _validate_configuration(self):
        if self.warning < 0.0 or self.danger <= self.warning:
            raise ValueError('thresholds require 0 <= warning_ppm < danger_ppm')
        if not isinstance(self.sources, list) or not self.sources:
            raise ValueError('gas_sources must be a non-empty list')
        required_fields = ('name', 'x', 'y', 'gas', 'peak_ppm')
        for index, source in enumerate(self.sources):
            if not isinstance(source, dict):
                raise ValueError(f'gas_sources[{index}] must be a mapping')
            missing = [field for field in required_fields if field not in source]
            if missing:
                raise ValueError(
                    f'gas_sources[{index}] missing fields: {", ".join(missing)}'
                )
            float(source['x'])
            float(source['y'])
            if float(source['peak_ppm']) < 0.0:
                raise ValueError(f'gas_sources[{index}].peak_ppm must be non-negative')
            if float(source.get('sigma', 0.4)) <= 0.0:
                raise ValueError(f'gas_sources[{index}].sigma must be greater than zero')

    # --- gas physics --------------------------------------------------------
    def _field(self, species, x, y):
        """Ground-truth concentration of one species at (x,y)."""
        c = 0.0
        for s in self.sources:
            if s.get('gas', 'gas') != species:
                continue
            d2 = (x - float(s['x'])) ** 2 + (y - float(s['y'])) ** 2
            sig = float(s.get('sigma', 0.4))
            c += float(s['peak_ppm']) * math.exp(-d2 / (2.0 * sig * sig))
        return c

    def _sensor_reading(self, x, y):
        """What the MOUNTED (selective) sensor reports: full response to its
        target gas + optional cross-sensitivity to others."""
        r = self._field(self.target_gas, x, y)            # coeff 1.0 for target
        for g in self.species:
            if g == self.target_gas:
                continue
            coeff = float(self.cross.get(g, 0.0))
            if coeff:
                r += coeff * self._field(g, x, y)
        return r

    def _truth_dominant(self, x, y):
        best_g, best_v = (self.species[0] if self.species else 'gas'), -1.0
        for g in self.species:
            v = self._field(g, x, y)
            if v > best_v:
                best_g, best_v = g, v
        return best_g, best_v

    def _level(self, ppm):
        return 2 if ppm >= self.danger else (1 if ppm >= self.warning else 0)

    def _stamp(self):
        t = self.get_clock().now().to_msg()
        return round(t.sec + t.nanosec * 1e-9, 3)

    # --- main loop ----------------------------------------------------------
    def _tick(self):
        try:
            tf = self.tf_buffer.lookup_transform(
                self.map_frame, self.base_frame, rclpy.time.Time())
        except Exception:
            return
        x, y = tf.transform.translation.x, tf.transform.translation.y

        reading = self._sensor_reading(x, y)
        self.pub_conc.publish(Float32(data=float(reading)))
        for g in self.species:                      # publish ground truth per gas
            self.truth_pubs[g].publish(Float32(data=float(self._field(g, x, y))))

        tg, tv = self._truth_dominant(x, y)
        q, r = axial_from_xy(x, y, self.R)
        cx, cy = xy_from_axial(q, r, self.R)
        key = (q, r)
        cell = self.cells.get(key)
        if cell is None or reading > cell['sensor_ppm']:
            self.cells[key] = {'cx': cx, 'cy': cy, 'sensor_ppm': float(reading),
                               'level': self._level(reading),
                               'truth_gas': tg, 'truth_ppm': float(tv)}

        lvl = self.cells[key]['level']
        if lvl >= 1 and lvl > self.cell_level.get(key, -1):
            self.cell_level[key] = lvl
            c = self.cells[key]
            ev = {'q': q, 'r': r, 'x': round(cx, 3), 'y': round(cy, 3),
                  'sensor_gas': self.target_gas, 'ppm': round(c['sensor_ppm'], 1),
                  'level': LEVEL_NAMES[lvl], 't': self._stamp(),
                  'truth_gas': c['truth_gas'], 'truth_ppm': round(c['truth_ppm'], 1)}
            self.events.append(ev)
            self.get_logger().info(
                f'GAS EVENT [{ev["level"]}] {self.target_gas}-sensor={ev["ppm"]}ppm '
                f'@hex({q},{r}) map({cx:.2f},{cy:.2f}) '
                f'[truth here: {ev["truth_gas"]}={ev["truth_ppm"]}ppm]')
            self._save()

        self._publish_hex()

    # --- visualization ------------------------------------------------------
    def _hex_color(self, level):
        if level == 2:
            return ColorRGBA(r=0.90, g=0.10, b=0.10, a=0.85)
        if level == 1:
            return ColorRGBA(r=0.95, g=0.75, b=0.10, a=0.70)
        return ColorRGBA(r=0.20, g=0.70, b=0.20, a=0.30)

    def _publish_hex(self):
        arr = MarkerArray()
        clr = Marker(); clr.action = Marker.DELETEALL; arr.markers.append(clr)
        now = self.get_clock().now().to_msg()
        mid = 0
        for (q, r), c in self.cells.items():
            m = Marker()
            m.header.frame_id = self.map_frame; m.header.stamp = now
            m.ns = 'gas_hex'; m.id = mid; mid += 1
            m.type = Marker.TRIANGLE_LIST; m.action = Marker.ADD
            m.scale.x = m.scale.y = m.scale.z = 1.0; m.pose.orientation.w = 1.0
            col = self._hex_color(c['level'])
            center = Point(x=c['cx'], y=c['cy'], z=0.02)
            corners = hex_corners(c['cx'], c['cy'], self.R * 0.92)
            for i in range(6):
                p1, p2 = corners[i], corners[(i + 1) % 6]
                m.points += [center, Point(x=p1[0], y=p1[1], z=0.02),
                             Point(x=p2[0], y=p2[1], z=0.02)]
                m.colors += [col, col, col]
            arr.markers.append(m)
        self.pub_hex.publish(arr)

    def _publish_sources(self):
        """Markers for every gas zone (per-gas color + text label)."""
        arr = MarkerArray()
        now = self.get_clock().now().to_msg()
        mid = 0
        for s in self.sources:
            gas = s.get('gas', 'gas')
            rgb = GAS_COLORS.get(gas, (0.5, 0.5, 0.5))
            sph = Marker()
            sph.header.frame_id = self.map_frame; sph.header.stamp = now
            sph.ns = 'gas_src'; sph.id = mid; mid += 1
            sph.type = Marker.SPHERE; sph.action = Marker.ADD
            sph.pose.position.x = float(s['x']); sph.pose.position.y = float(s['y'])
            sph.pose.position.z = 0.1; sph.pose.orientation.w = 1.0
            sph.scale.x = sph.scale.y = sph.scale.z = 0.3
            sph.color = ColorRGBA(r=rgb[0], g=rgb[1], b=rgb[2], a=0.9)
            arr.markers.append(sph)
            txt = Marker()
            txt.header.frame_id = self.map_frame; txt.header.stamp = now
            txt.ns = 'gas_src_label'; txt.id = mid; mid += 1
            txt.type = Marker.TEXT_VIEW_FACING; txt.action = Marker.ADD
            txt.pose.position.x = float(s['x']); txt.pose.position.y = float(s['y'])
            txt.pose.position.z = 0.4; txt.pose.orientation.w = 1.0
            txt.scale.z = 0.22
            txt.color = ColorRGBA(r=rgb[0], g=rgb[1], b=rgb[2], a=1.0)
            tag = ' [SENSOR TARGET]' if gas == self.target_gas else ''
            txt.text = f"{gas}{tag}"
            arr.markers.append(txt)
        self.pub_src.publish(arr)

    # --- persistence --------------------------------------------------------
    def _map_cb(self, msg):
        self.latest_map = msg
        self.map_res = msg.info.resolution
        self.map_origin = [msg.info.origin.position.x, msg.info.origin.position.y]

    def _save(self):
        data = {
            'frame_id': self.map_frame, 'hex_size': self.R,
            'sensor': {'target_gas': self.target_gas, 'cross_sensitivity': self.cross},
            'world_species': self.species,
            'map_resolution': self.map_res, 'map_origin': self.map_origin,
            'gas_sources': self.sources,
            'thresholds': {'warning_ppm': self.warning, 'danger_ppm': self.danger},
            'cells': [
                {'q': k[0], 'r': k[1], 'x': round(v['cx'], 3), 'y': round(v['cy'], 3),
                 'sensor_gas': self.target_gas, 'sensor_ppm': round(v['sensor_ppm'], 1),
                 'level': LEVEL_NAMES[v['level']],
                 'truth_gas': v['truth_gas'], 'truth_ppm': round(v['truth_ppm'], 1)}
                for k, v in self.cells.items()],
            'events': self.events,
        }
        self._atomic_write(self.output_path, json.dumps(data, indent=2))

    def _save_map(self):
        """Write the current /map OccupancyGrid as a trinary .pgm + .yaml."""
        g = self.latest_map
        if g is None:
            return
        w, h = g.info.width, g.info.height
        d = np.array(g.data, dtype=np.int16).reshape(h, w)
        img = np.full((h, w), 205, dtype=np.uint8)           # unknown = gray
        img[(d >= 0) & (d <= int(self.free_th * 100))] = 254  # free = white
        img[d >= int(self.occ_th * 100)] = 0                  # occupied = black
        img = np.flipud(img)                                  # PGM row0 = top (max y)
        try:
            os.makedirs(os.path.dirname(self.map_output) or '.', exist_ok=True)
            with open(self.map_output + '.pgm', 'wb') as f:
                f.write(b'P5\n%d %d\n255\n' % (w, h))
                f.write(img.tobytes())
            ox, oy = g.info.origin.position.x, g.info.origin.position.y
            yaml_txt = (f"image: {os.path.basename(self.map_output)}.pgm\n"
                        f"mode: trinary\nresolution: {g.info.resolution}\n"
                        f"origin: [{ox}, {oy}, 0.0]\nnegate: 0\n"
                        f"occupied_thresh: {self.occ_th}\nfree_thresh: {self.free_th}\n")
            with open(self.map_output + '.yaml', 'w') as f:
                f.write(yaml_txt)
        except Exception as e:
            self.get_logger().warn(f'map save failed: {e}')

    def _atomic_write(self, path, text):
        try:
            d = os.path.dirname(path) or '.'
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
            with os.fdopen(fd, 'w') as f:
                f.write(text)
            os.replace(tmp, path)
        except Exception as e:
            self.get_logger().warn(f'save failed ({path}): {e}')


def main():
    rclpy.init()
    node = GasSensorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._save()
        node._save_map()        # ensure map is captured on shutdown
        node.get_logger().info('saved gas json + occupancy map on shutdown.')
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
