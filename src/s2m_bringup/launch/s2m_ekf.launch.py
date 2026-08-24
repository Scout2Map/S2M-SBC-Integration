#!/usr/bin/env python3
"""Start robot_localization's EKF as the owner of odom -> base_link.

Kept in its own file so it can be brought up alone against a running bridge,
which is what the S2 step of docs/integration/slam-nav2-ugv-validation.md asks
for. s2m_onboard_bridge.launch.py includes this when use_ekf is true.

Two wirings are supported and the difference is only ekf_odom_topic.

  Production. The bridge publishes wheel odometry on /drive/odom with
  publish_tf false, and the EKF takes over both /odom and the transform.
  Nothing downstream changes because nav2_lowspec.yaml already reads /odom.

    ros2 launch s2m_bringup s2m_onboard_bridge.launch.py use_ekf:=true

  Comparison. The bridge keeps /odom and its transform, and the EKF runs
  alongside on /odometry/filtered publishing no TF. Record both in one bag and
  compare before handing the transform over.

    ros2 launch s2m_bringup s2m_ekf.launch.py \
      ekf_odom_topic:=/odometry/filtered ekf_publish_tf:=false \
      wheel_odom_topic:=/odom
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    bringup_share = get_package_share_directory('s2m_bringup')
    default_params = os.path.join(bringup_share, 'config', 'ekf.yaml')

    args = [
        DeclareLaunchArgument('use_ekf', default_value='true'),
        DeclareLaunchArgument('ekf_params_file', default_value=default_params),

        # Where the filtered estimate lands. /odom in production so Nav2 and
        # the behaviour server keep the topic name they already have.
        DeclareLaunchArgument(
            'ekf_odom_topic', default_value='/odom',
            description='Output topic. Use /odometry/filtered to run the EKF '
                        'alongside the bridge instead of replacing it.'),

        # Input. Must match what the bridge is remapped to.
        DeclareLaunchArgument(
            'wheel_odom_topic', default_value='/drive/odom',
            description='Wheel odometry input, the odom0 source.'),

        DeclareLaunchArgument('imu_topic', default_value='/imu/data'),

        # Exactly one node may publish odom -> base_link. Set this false while
        # the drive bridge still has publish_tf true.
        DeclareLaunchArgument('ekf_publish_tf', default_value='true'),
    ]

    # The yaml names odom0/imu0 too, but a remap is what actually takes effect
    # for the topics the node subscribes to, so both wirings stay in launch.
    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        emulate_tty=True,
        parameters=[
            LaunchConfiguration('ekf_params_file'),
            {'publish_tf': ParameterValue(
                LaunchConfiguration('ekf_publish_tf'), value_type=bool)},
        ],
        remappings=[
            ('odometry/filtered', LaunchConfiguration('ekf_odom_topic')),
            ('/drive/odom', LaunchConfiguration('wheel_odom_topic')),
            ('/imu/data', LaunchConfiguration('imu_topic')),
        ],
        condition=IfCondition(LaunchConfiguration('use_ekf')),
    )

    return LaunchDescription(args + [ekf])
