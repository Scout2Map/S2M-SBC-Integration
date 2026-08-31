#!/usr/bin/env python3
"""Republish the drive bridge DriveStatus health as a plain Bool link flag.

The return-home policy consumes a std_msgs/Bool on /drive/link_ok because the
simulation fault injector has no MCU behind it. The real drive bridge instead
publishes scout2map_msgs/DriveStatus on /drive/status, which carries link_ok
plus the fault bits that must also inhibit an autonomous return. This node is
the single place where those bits are collapsed into one boolean, so the
policy node stays identical between simulation and hardware.
"""

import time

import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from scout2map_msgs.msg import DriveStatus
from std_msgs.msg import Bool


class DriveLinkAdapter(Node):
    """Collapse DriveStatus into the Bool contract used by return_home."""

    def __init__(self):
        super().__init__('drive_link_adapter')

        self.declare_parameter('drive_status_topic', '/drive/status')
        self.declare_parameter('link_topic', '/drive/link_ok')
        # Separate from link_topic on purpose: batt_critical must reach
        # return_home as its own signal even though it deliberately does
        # NOT block link_ok (see batt_critical_blocks_link below) - a
        # critical-but-not-dead pack should still be able to drive itself
        # home instead of being reported healthy with no way to trigger one.
        self.declare_parameter(
            'battery_critical_topic', '/drive/battery_critical')
        self.declare_parameter('publish_rate_hz', 10.0)

        # DriveStatus arrives at status_rate_hz (10Hz by default in the bridge
        # config). Anything older than this is treated as no link at all.
        self.declare_parameter('status_timeout_sec', 0.5)

        # Latched estop and a stalled motor are not link faults, but a return
        # cannot be driven through them either. Kept as flags so bench tests
        # can isolate the pure link case.
        self.declare_parameter('estop_blocks_link', True)
        self.declare_parameter('fault_blocks_link', True)
        self.declare_parameter('cmd_timeout_blocks_link', True)
        self.declare_parameter('batt_dead_blocks_link', True)

        # Battery critical still allows a return: getting home on a low pack is
        # better than stopping in place. batt_dead is different, the firmware
        # has already cut drive.
        self.declare_parameter('batt_critical_blocks_link', False)

        gp = self.get_parameter
        self._timeout = float(gp('status_timeout_sec').value)
        self._estop_blocks = bool(gp('estop_blocks_link').value)
        self._fault_blocks = bool(gp('fault_blocks_link').value)
        self._cmd_timeout_blocks = bool(gp('cmd_timeout_blocks_link').value)
        self._batt_dead_blocks = bool(gp('batt_dead_blocks_link').value)
        self._batt_critical_blocks = bool(gp('batt_critical_blocks_link').value)

        self._last_status = None
        self._last_status_mono = None
        self._last_published = None
        self._last_reason = ''

        self._link_pub = self.create_publisher(
            Bool, str(gp('link_topic').value), 10)
        self._battery_critical_pub = self.create_publisher(
            Bool, str(gp('battery_critical_topic').value), 10)
        self.create_subscription(
            DriveStatus,
            str(gp('drive_status_topic').value),
            self._on_status,
            10,
        )

        # Steady clock so a paused or jumping /clock cannot freeze the timeout
        rate = max(1.0, float(gp('publish_rate_hz').value))
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(1.0 / rate, self._tick, clock=self._steady_clock)

        self.get_logger().info(
            'drive_link_adapter started; waiting for DriveStatus on '
            f"{gp('drive_status_topic').value}")

    def _on_status(self, message):
        self._last_status = message
        self._last_status_mono = time.monotonic()

    def _evaluate(self):
        """Return (link_ok, reason). Reason is empty when healthy."""
        if self._last_status is None or self._last_status_mono is None:
            return False, 'no DriveStatus received yet'

        age = time.monotonic() - self._last_status_mono
        if age > self._timeout:
            return False, f'DriveStatus stale ({age:.2f}s)'

        status = self._last_status
        if not status.link_ok:
            return False, 'bridge reports link_ok false'
        if self._estop_blocks and status.estop_latched:
            return False, 'estop latched'
        if self._fault_blocks and status.fault_stall:
            return False, 'stall fault'
        if self._cmd_timeout_blocks and status.cmd_timeout:
            return False, 'MCU command timeout'
        if self._batt_dead_blocks and status.batt_dead:
            return False, 'battery dead, firmware cut drive'
        if self._batt_critical_blocks and status.batt_critical:
            return False, 'battery critical'
        return True, ''

    def _battery_critical_state(self):
        """True only when a fresh DriveStatus reports batt_critical.

        Independent of _evaluate(): link_ok can be True (battery critical
        does not block the link by default) while this is also True, and a
        stale/missing DriveStatus reports False here rather than an unknown
        critical state - return_home already gets a stale-status SAFE_STOP
        via drive_healthy, so this only needs to reflect what the firmware
        last actually reported.
        """
        if self._last_status is None or self._last_status_mono is None:
            return False
        if time.monotonic() - self._last_status_mono > self._timeout:
            return False
        return bool(self._last_status.batt_critical)

    def _tick(self):
        link_ok, reason = self._evaluate()
        self._link_pub.publish(Bool(data=link_ok))
        self._battery_critical_pub.publish(
            Bool(data=self._battery_critical_state()))

        # Log only on edges, this runs at 10Hz
        if link_ok != self._last_published:
            if link_ok:
                self.get_logger().info('drive link healthy')
            else:
                self.get_logger().warn(f'drive link unhealthy: {reason}')
            self._last_published = link_ok
            self._last_reason = reason


def main(args=None):
    rclpy.init(args=args)
    node = DriveLinkAdapter()
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
