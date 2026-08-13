#!/usr/bin/env python3
"""Single-publisher velocity gate for return-home simulation safety."""

import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from std_msgs.msg import Bool


class CmdVelSafetyGate(Node):
    def __init__(self):
        super().__init__('cmd_vel_safety_gate')
        self.declare_parameter('input_topic', '/return_home/cmd_vel_input')
        self.declare_parameter('output_topic', '/cmd_vel')
        self.declare_parameter(
            'inhibit_topic', '/return_home/motion_inhibit')
        self.declare_parameter('input_timeout_sec', 0.5)
        self.declare_parameter('inhibit_timeout_sec', 1.0)
        self.declare_parameter('publish_rate_hz', 20.0)

        gp = self.get_parameter
        self._input_timeout = float(gp('input_timeout_sec').value)
        self._inhibited = True
        self._last_command = Twist()
        self._last_command_mono = None
        self._last_inhibit_mono = None
        self._inhibit_timeout = float(gp('inhibit_timeout_sec').value)

        self._output = self.create_publisher(
            Twist, str(gp('output_topic').value), 10)
        self.create_subscription(
            Twist, str(gp('input_topic').value), self._on_command, 10)
        self.create_subscription(
            Bool, str(gp('inhibit_topic').value), self._on_inhibit, 10)

        rate = max(1.0, float(gp('publish_rate_hz').value))
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(
            1.0 / rate, self._tick, clock=self._steady_clock)
        self.get_logger().info('cmd_vel gate started in inhibited state')

    def _on_command(self, message):
        self._last_command = message
        self._last_command_mono = time.monotonic()

    def _on_inhibit(self, message):
        self._last_inhibit_mono = time.monotonic()
        self._inhibited = bool(message.data)
        if self._inhibited:
            self._output.publish(Twist())

    def _tick(self):
        command_fresh = (
            self._last_command_mono is not None
            and time.monotonic() - self._last_command_mono <= self._input_timeout
        )
        inhibit_fresh = (
            self._last_inhibit_mono is not None
            and time.monotonic() - self._last_inhibit_mono
            <= self._inhibit_timeout
        )
        if self._inhibited or not inhibit_fresh or not command_fresh:
            self._output.publish(Twist())
        else:
            self._output.publish(self._last_command)


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelSafetyGate()
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
