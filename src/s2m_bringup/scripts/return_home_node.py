#!/usr/bin/env python3
"""Return to a captured start pose when the control-network heartbeat is lost."""

import json
import time
from copy import deepcopy

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.clock import Clock, ClockType
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import Bool, Empty, String
from std_srvs.srv import SetBool, Trigger
from tf2_ros import Buffer, TransformException, TransformListener

from return_home_policy import Decision, Health, decide


ACTIVE_STATES = {'NORMAL', 'RETURN_REQUESTED', 'RETURNING'}


class ReturnHomeNode(Node):
    """Capture a map-frame start pose and conditionally send it to Nav2."""

    def __init__(self):
        super().__init__('return_home')

        self.declare_parameter('global_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('heartbeat_topic', '/control/heartbeat')
        self.declare_parameter('drive_link_topic', '/drive/link_ok')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter(
            'motion_inhibit_topic', '/return_home/motion_inhibit')
        self.declare_parameter('navigate_action', '/navigate_to_pose')
        self.declare_parameter('heartbeat_timeout_sec', 3.0)
        self.declare_parameter('drive_link_timeout_sec', 1.0)
        self.declare_parameter('tf_max_age_sec', 1.0)
        self.declare_parameter('return_timeout_sec', 120.0)
        self.declare_parameter('progress_timeout_sec', 30.0)
        self.declare_parameter('progress_min_delta_m', 0.05)
        self.declare_parameter('auto_capture_start', True)
        self.declare_parameter('auto_capture_delay_sec', 5.0)
        self.declare_parameter('auto_arm', True)
        self.declare_parameter('control_rate_hz', 10.0)

        gp = self.get_parameter
        self._global_frame = str(gp('global_frame').value)
        self._base_frame = str(gp('base_frame').value)
        self._heartbeat_timeout = float(gp('heartbeat_timeout_sec').value)
        self._drive_timeout = float(gp('drive_link_timeout_sec').value)
        self._tf_max_age = float(gp('tf_max_age_sec').value)
        self._return_timeout = float(gp('return_timeout_sec').value)
        self._progress_timeout = float(gp('progress_timeout_sec').value)
        self._progress_min_delta = float(gp('progress_min_delta_m').value)
        self._auto_capture = bool(gp('auto_capture_start').value)
        self._auto_capture_delay = float(gp('auto_capture_delay_sec').value)
        self._auto_arm = bool(gp('auto_arm').value)

        self._state = 'WAITING_FOR_START'
        self._armed = False
        self._start_pose = None
        self._heartbeat_seen = False
        self._last_heartbeat_mono = None
        self._drive_seen = False
        self._drive_link_ok = False
        self._last_drive_status_mono = None
        self._goal_handle = None
        self._return_reason = ''
        self._node_started_mono = time.monotonic()
        self._return_started_mono = None
        self._last_progress_mono = None
        self._best_distance = None
        self._last_tf_stamp_ns = None
        self._last_tf_update_mono = None
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)

        self._tf_buffer = Buffer(node=self)
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._navigate = ActionClient(
            self, NavigateToPose, str(gp('navigate_action').value))

        latched_qos = QoSProfile(depth=1)
        latched_qos.reliability = ReliabilityPolicy.RELIABLE
        latched_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self._status_pub = self.create_publisher(
            String, '/return_home/status', latched_qos)
        self._start_pose_pub = self.create_publisher(
            PoseStamped, '/return_home/start_pose', latched_qos)
        self._inhibit_pub = self.create_publisher(
            Bool, str(gp('motion_inhibit_topic').value), latched_qos)
        self._stop_pub = self.create_publisher(
            Twist, str(gp('cmd_vel_topic').value), 10)

        self.create_subscription(
            Empty, str(gp('heartbeat_topic').value), self._on_heartbeat, 10)
        self.create_subscription(
            Bool, str(gp('drive_link_topic').value), self._on_drive_link, 10)

        self.create_service(
            Trigger, '/return_home/capture_start', self._capture_service)
        self.create_service(SetBool, '/return_home/arm', self._arm_service)
        self.create_service(
            Trigger, '/return_home/trigger', self._trigger_service)
        self.create_service(Trigger, '/return_home/reset', self._reset_service)

        rate = max(1.0, float(gp('control_rate_hz').value))
        self.create_timer(
            1.0 / rate, self._control_tick, clock=self._steady_clock)
        self.create_timer(
            1.0, self._publish_status, clock=self._steady_clock)
        self._inhibit_pub.publish(Bool(data=True))
        self._publish_status()
        self.get_logger().info(
            'return_home ready; waiting for heartbeat, drive link, and TF')

    def _on_heartbeat(self, _msg):
        self._heartbeat_seen = True
        self._last_heartbeat_mono = time.monotonic()

    def _on_drive_link(self, msg):
        self._drive_seen = True
        self._drive_link_ok = bool(msg.data)
        self._last_drive_status_mono = time.monotonic()

    @staticmethod
    def _age(stamp):
        if stamp is None:
            return None
        return max(0.0, time.monotonic() - stamp)

    def _heartbeat_fresh(self):
        age = self._age(self._last_heartbeat_mono)
        return age is not None and age <= self._heartbeat_timeout

    def _drive_healthy(self):
        age = self._age(self._last_drive_status_mono)
        return (
            self._drive_seen
            and self._drive_link_ok
            and age is not None
            and age <= self._drive_timeout
        )

    def _lookup_pose(self):
        try:
            transform = self._tf_buffer.lookup_transform(
                self._global_frame,
                self._base_frame,
                Time(),
                timeout=Duration(seconds=0.02),
            )
        except TransformException:
            return None

        stamp = Time.from_msg(transform.header.stamp)
        stamp_ns = stamp.nanoseconds
        now_mono = time.monotonic()
        if stamp_ns != self._last_tf_stamp_ns:
            self._last_tf_stamp_ns = stamp_ns
            self._last_tf_update_mono = now_mono
        if (
            self._last_tf_update_mono is None
            or now_mono - self._last_tf_update_mono > self._tf_max_age
        ):
            return None

        if stamp_ns:
            ros_age = (self.get_clock().now() - stamp).nanoseconds / 1e9
            if ros_age < -0.1 or ros_age > self._tf_max_age:
                return None

        pose = PoseStamped()
        pose.header.frame_id = self._global_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = transform.transform.translation.x
        pose.pose.position.y = transform.transform.translation.y
        pose.pose.position.z = transform.transform.translation.z
        pose.pose.orientation = transform.transform.rotation
        return pose

    def _capture_start(self):
        if not self._heartbeat_fresh():
            return False, 'control heartbeat is not healthy'
        if not self._drive_healthy():
            return False, 'drive link is not healthy'
        pose = self._lookup_pose()
        if pose is None:
            return False, 'map to base_link TF is unavailable or stale'

        self._start_pose = pose
        self._start_pose_pub.publish(deepcopy(pose))
        self._set_state('START_POSE_CAPTURED')
        self.get_logger().info(
            f'start pose captured: x={pose.pose.position.x:.3f}, '
            f'y={pose.pose.position.y:.3f}')
        return True, 'start pose captured'

    def _capture_service(self, _request, response):
        response.success, response.message = self._capture_start()
        return response

    def _arm_service(self, request, response):
        if request.data:
            if self._start_pose is None:
                response.success = False
                response.message = 'capture the start pose before arming'
                return response
            if (
                not self._heartbeat_fresh()
                or not self._drive_healthy()
                or self._lookup_pose() is None
            ):
                response.success = False
                response.message = (
                    'heartbeat, drive link, or localization is not healthy')
                return response
            self._armed = True
            self._set_state('NORMAL')
            response.success = True
            response.message = 'return-home monitor armed'
        else:
            self._armed = False
            if self._state in {'RETURN_REQUESTED', 'RETURNING'}:
                self._safe_stop('operator disarmed during return')
            else:
                self._set_state('START_POSE_CAPTURED')
            response.success = True
            response.message = 'return-home monitor disarmed'
        return response

    def _trigger_service(self, _request, response):
        ok, message = self._request_return('manual trigger')
        response.success = ok
        response.message = message
        return response

    def _reset_service(self, _request, response):
        if not self._heartbeat_fresh():
            response.success = False
            response.message = 'restore the control heartbeat before reset'
            return response
        if not self._drive_healthy() or self._lookup_pose() is None:
            response.success = False
            response.message = 'drive link or localization is not healthy'
            return response
        if self._start_pose is None:
            response.success = False
            response.message = 'start pose is not captured'
            return response

        self._goal_handle = None
        self._return_reason = ''
        self._return_started_mono = None
        self._last_progress_mono = None
        self._best_distance = None
        self._armed = True
        self._set_state('NORMAL')
        response.success = True
        response.message = 'fault cleared and monitor re-armed'
        return response

    def _control_tick(self):
        now_mono = time.monotonic()
        startup_age = max(0.0, now_mono - self._node_started_mono)

        if (
            self._auto_capture
            and self._start_pose is None
            and startup_age >= self._auto_capture_delay
            and self._heartbeat_fresh()
            and self._drive_healthy()
        ):
            captured, _ = self._capture_start()
            if captured and self._auto_arm and self._heartbeat_fresh():
                self._armed = True
                self._set_state('NORMAL')

        health = Health(
            heartbeat_seen=self._heartbeat_seen,
            heartbeat_fresh=self._heartbeat_fresh(),
            drive_seen=self._drive_seen,
            drive_healthy=self._drive_healthy(),
            tf_healthy=self._lookup_pose() is not None,
        )
        decision = decide(
            self._state, self._armed, self._start_pose is not None, health)

        if decision is Decision.RETURN_HOME:
            self._request_return('control heartbeat timeout')
        elif decision is Decision.SAFE_STOP:
            if not health.drive_healthy:
                reason = 'drive link lost or stale'
            elif not health.tf_healthy:
                reason = 'localization TF lost or stale'
            else:
                reason = 'return-home precondition failed'
            self._safe_stop(reason)

        if self._state == 'RETURNING':
            if now_mono - self._return_started_mono > self._return_timeout:
                self._safe_stop('return-home deadline exceeded')
            elif (
                self._last_progress_mono is not None
                and now_mono - self._last_progress_mono > self._progress_timeout
            ):
                self._safe_stop('Nav2 return made no measurable progress')

        if self._state in {'SAFE_STOP', 'ARRIVED'}:
            self._stop_pub.publish(Twist())

    def _request_return(self, reason):
        if not self._armed:
            return False, 'return-home monitor is not armed'
        if self._state != 'NORMAL':
            return False, f'return cannot start from state {self._state}'
        if self._start_pose is None:
            return False, 'start pose is not captured'
        if not self._drive_healthy():
            self._safe_stop('drive link unhealthy at return request')
            return False, 'drive link is not healthy; safe stop selected'
        if self._lookup_pose() is None:
            self._safe_stop('localization unavailable at return request')
            return False, 'localization is not healthy; safe stop selected'
        if not self._navigate.wait_for_server(timeout_sec=1.0):
            self._safe_stop('Nav2 action server unavailable')
            return False, 'NavigateToPose action server is unavailable'

        goal = NavigateToPose.Goal()
        goal.pose = deepcopy(self._start_pose)
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        self._return_reason = reason
        self._return_started_mono = time.monotonic()
        self._last_progress_mono = self._return_started_mono
        self._best_distance = None
        self._set_state('RETURN_REQUESTED')
        future = self._navigate.send_goal_async(
            goal, feedback_callback=self._goal_feedback)
        future.add_done_callback(self._goal_response)
        self.get_logger().warn(f'return requested: {reason}')
        return True, 'return goal sent to Nav2'

    def _goal_feedback(self, message):
        distance = float(message.feedback.distance_remaining)
        if (
            self._best_distance is None
            or distance <= self._best_distance - self._progress_min_delta
        ):
            self._best_distance = distance
            self._last_progress_mono = time.monotonic()

    def _goal_response(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._safe_stop(f'Nav2 goal request failed: {exc}')
            return
        if not goal_handle.accepted:
            self._safe_stop('Nav2 rejected the return goal')
            return

        self._goal_handle = goal_handle
        if self._state == 'SAFE_STOP':
            goal_handle.cancel_goal_async()
            return
        self._set_state('RETURNING')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result)

    def _goal_result(self, future):
        if self._state not in {'RETURN_REQUESTED', 'RETURNING'}:
            return
        try:
            status = future.result().status
        except Exception as exc:
            self._safe_stop(f'Nav2 result failed: {exc}')
            return

        if status == GoalStatus.STATUS_SUCCEEDED:
            self._armed = False
            self._set_state('ARRIVED')
            self.get_logger().info('return-home goal reached')
        else:
            self._safe_stop(f'Nav2 return ended with status {status}')

    def _safe_stop(self, reason):
        if self._state == 'SAFE_STOP':
            return
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
        self._return_reason = reason
        self._armed = False
        self._set_state('SAFE_STOP')
        self._stop_pub.publish(Twist())
        self.get_logger().error(f'safe stop: {reason}')

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            self._inhibit_pub.publish(Bool(data=state not in ACTIVE_STATES))
            self._publish_status()

    def _publish_status(self):
        payload = {
            'state': self._state,
            'armed': self._armed,
            'start_captured': self._start_pose is not None,
            'heartbeat_seen': self._heartbeat_seen,
            'heartbeat_age_sec': self._age(self._last_heartbeat_mono),
            'drive_seen': self._drive_seen,
            'drive_link_ok': self._drive_link_ok,
            'drive_status_age_sec': self._age(self._last_drive_status_mono),
            'best_distance_m': self._best_distance,
            'reason': self._return_reason,
        }
        self._inhibit_pub.publish(Bool(data=self._state not in ACTIVE_STATES))
        self._status_pub.publish(String(data=json.dumps(payload, sort_keys=True)))


def main(args=None):
    rclpy.init(args=args)
    node = ReturnHomeNode()
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
