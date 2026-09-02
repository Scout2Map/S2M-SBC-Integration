#!/usr/bin/env python3
"""Publish simulated network heartbeat, drive-link, and battery health
signals."""

import json

import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from std_msgs.msg import Bool, Empty, String
from std_srvs.srv import SetBool, Trigger


class SimFaultInjector(Node):
    def __init__(self):
        super().__init__('sim_fault_injector')
        self.declare_parameter('heartbeat_topic', '/control/heartbeat')
        self.declare_parameter('drive_link_topic', '/drive/link_ok')
        # Simulation has no MCU behind it, so this stands in for
        # drive_link_adapter's /drive/battery_critical on real hardware -
        # same topic name and contract, so return_home_node stays identical
        # between sim and hardware (see its own module docstring).
        self.declare_parameter(
            'battery_critical_topic', '/drive/battery_critical')
        self.declare_parameter('publish_rate_hz', 5.0)

        gp = self.get_parameter
        self._network_enabled = True
        self._drive_link_ok = True
        self._battery_critical = False
        self._heartbeat_pub = self.create_publisher(
            Empty, str(gp('heartbeat_topic').value), 10)
        self._drive_pub = self.create_publisher(
            Bool, str(gp('drive_link_topic').value), 10)
        self._battery_critical_pub = self.create_publisher(
            Bool, str(gp('battery_critical_topic').value), 10)
        self._status_pub = self.create_publisher(
            String, '/sim_faults/status', 10)

        self.create_service(
            SetBool, '/sim_faults/set_network', self._set_network)
        self.create_service(
            SetBool, '/sim_faults/set_drive_link', self._set_drive_link)
        self.create_service(
            SetBool, '/sim_faults/set_battery_critical',
            self._set_battery_critical)
        self.create_service(Trigger, '/sim_faults/reset', self._reset)

        rate = max(1.0, float(gp('publish_rate_hz').value))
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(
            1.0 / rate, self._tick, clock=self._steady_clock)
        self.get_logger().info('simulation health signals enabled')

    def _tick(self):
        if self._network_enabled:
            self._heartbeat_pub.publish(Empty())
        self._drive_pub.publish(Bool(data=self._drive_link_ok))
        self._battery_critical_pub.publish(Bool(data=self._battery_critical))
        self._publish_status()

    def _set_network(self, request, response):
        self._network_enabled = bool(request.data)
        response.success = True
        response.message = (
            'control heartbeat enabled'
            if self._network_enabled else 'control heartbeat disabled')
        self._publish_status()
        return response

    def _set_drive_link(self, request, response):
        self._drive_link_ok = bool(request.data)
        self._drive_pub.publish(Bool(data=self._drive_link_ok))
        response.success = True
        response.message = (
            'drive link healthy' if self._drive_link_ok else 'drive link lost')
        self._publish_status()
        return response

    def _set_battery_critical(self, request, response):
        self._battery_critical = bool(request.data)
        self._battery_critical_pub.publish(Bool(data=self._battery_critical))
        response.success = True
        response.message = (
            'battery critical fault injected' if self._battery_critical
            else 'battery critical fault cleared')
        self._publish_status()
        return response

    def _reset(self, _request, response):
        self._network_enabled = True
        self._drive_link_ok = True
        self._battery_critical = False
        self._drive_pub.publish(Bool(data=True))
        self._battery_critical_pub.publish(Bool(data=False))
        response.success = True
        response.message = 'simulation health signals reset'
        self._publish_status()
        return response

    def _publish_status(self):
        payload = {
            'network_enabled': self._network_enabled,
            'drive_link_ok': self._drive_link_ok,
            'battery_critical': self._battery_critical,
        }
        self._status_pub.publish(String(data=json.dumps(payload, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = SimFaultInjector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
