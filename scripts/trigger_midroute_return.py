#!/usr/bin/env python3
"""Send a Nav2 goal, then drop the simulated network after it is accepted."""

import argparse
import time

import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_srvs.srv import SetBool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--x', type=float, default=1.5)
    parser.add_argument('--y', type=float, default=0.0)
    parser.add_argument('--delay', type=float, default=3.0)
    args = parser.parse_args()

    rclpy.init()
    node = Node('midroute_return_test')
    navigate = ActionClient(node, NavigateToPose, '/navigate_to_pose')
    network = node.create_client(SetBool, '/sim_faults/set_network')

    try:
        if not navigate.wait_for_server(timeout_sec=20.0):
            raise RuntimeError('NavigateToPose action server is unavailable')
        if not network.wait_for_service(timeout_sec=20.0):
            raise RuntimeError('network fault service is unavailable')

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = node.get_clock().now().to_msg()
        goal.pose.pose.position.x = args.x
        goal.pose.pose.position.y = args.y
        goal.pose.pose.orientation.w = 1.0

        goal_future = navigate.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, goal_future)
        goal_handle = goal_future.result()
        if goal_handle is None or not goal_handle.accepted:
            raise RuntimeError('Nav2 rejected the outbound goal')

        print(
            f'outbound goal accepted: ({args.x:.2f}, {args.y:.2f}); '
            f'dropping network in {args.delay:.1f}s',
            flush=True,
        )
        deadline = time.monotonic() + args.delay
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

        request = SetBool.Request()
        request.data = False
        fault_future = network.call_async(request)
        rclpy.spin_until_future_complete(node, fault_future)
        response = fault_future.result()
        if response is None or not response.success:
            raise RuntimeError('failed to disable the simulated network')
        print(response.message, flush=True)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
