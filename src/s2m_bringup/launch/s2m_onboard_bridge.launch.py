#!/usr/bin/env python3
"""Start the real MCU bridges with the topic and frame wiring this repo expects.

scout2map_bridge owns the serial protocol and publishes under its own names
(drive/odom, drive/status, sensors/*). This launch is where the SBC decides how
those names map onto the SLAM/Nav2 contract, which is a system integration
concern and therefore belongs here rather than in the bridge repository.

This launch does NOT start LiDAR, SLAM or Nav2. Bring it up first, confirm the
topics and TF, then start the mapping stack.

use_ekf switches who owns odom -> base_link. With it false the drive bridge
publishes both /odom and the transform, which is the arrangement that has been
running so far. With it true the bridge moves to /drive/odom with publish_tf
off and robot_localization takes over both, so nothing downstream has to change
its topic names.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    bridge_share = get_package_share_directory('scout2map_bridge')
    bringup_share = get_package_share_directory('s2m_bringup')

    sensor_params = os.path.join(bridge_share, 'config', 'sensor_bridge.yaml')
    drive_params = os.path.join(bridge_share, 'config', 'drive_bridge.yaml')
    gpio_params = os.path.join(bridge_share, 'config', 'gpio_events.yaml')
    adapter_params = os.path.join(
        bringup_share, 'config', 'drive_link_adapter.yaml')
    ekf_params = os.path.join(bringup_share, 'config', 'ekf.yaml')

    # LaunchConfiguration values arrive as strings, so quote before comparing
    ekf_on = PythonExpression(
        ["'", LaunchConfiguration('use_ekf'), "'.lower() in ('true', '1')"])
    ekf_off = PythonExpression(['not (', ekf_on, ')'])

    args = [
        # On by default since 2026-08-24 field testing. Set false to fall back
        # to the drive bridge owning /odom and odom -> base_link, which is the
        # only arrangement that works if robot_localization is not installed.
        DeclareLaunchArgument(
            'use_ekf', default_value='true',
            description='Start robot_localization and hand it /odom and the '
                        'odom -> base_link transform.'),
        DeclareLaunchArgument('ekf_params_file', default_value=ekf_params),

        DeclareLaunchArgument('use_sensor_bridge', default_value='true'),
        DeclareLaunchArgument('use_drive_bridge', default_value='true'),
        DeclareLaunchArgument('use_drive_link_adapter', default_value='true'),
        DeclareLaunchArgument('use_gpio_events', default_value='true'),

        DeclareLaunchArgument('sensor_params_file', default_value=sensor_params),
        DeclareLaunchArgument('drive_params_file', default_value=drive_params),
        DeclareLaunchArgument('gpio_params_file', default_value=gpio_params),
        DeclareLaunchArgument(
            'drive_link_adapter_params_file', default_value=adapter_params),

        # Nav2 and slam_toolbox in this repo read /odom. Without the EKF the
        # wheel odometry is published straight onto that name; with it the
        # bridge steps aside to /drive/odom and becomes an EKF input.
        DeclareLaunchArgument(
            'odom_topic',
            default_value=PythonExpression(
                ["'/drive/odom' if ", ekf_on, " else '/odom'"]),
            description='Where the drive bridge odometry is remapped to. '
                        'Follows use_ekf unless set explicitly.'),

        # The bridge publishes Imu on drive/imu; the validation docs use
        # /imu/data, which is also what robot_localization expects by default.
        DeclareLaunchArgument('imu_topic', default_value='/imu/data'),

        # s2m_description defines base_link, lidar_link and imu_link only. The
        # two frames below are referenced by the bridges but have no URDF link,
        # so without these static transforms every TF lookup on them fails.
        DeclareLaunchArgument(
            'publish_sensor_frames', default_value='true',
            description='Publish static TF for sensor_fusion and range_link'),

        # PROVISIONAL. Both offsets are from base_link origin, which is the
        # centre of the platform bottom face. Measure on the built chassis and
        # replace before trusting any marker placed with these frames.
        DeclareLaunchArgument('sensor_fusion_x', default_value='-0.050'),
        DeclareLaunchArgument('sensor_fusion_y', default_value='0.000'),
        DeclareLaunchArgument('sensor_fusion_z', default_value='0.110'),
        DeclareLaunchArgument('range_link_x', default_value='0.132'),
        DeclareLaunchArgument('range_link_y', default_value='0.000'),
        DeclareLaunchArgument('range_link_z', default_value='0.050'),
    ]

    sensor_bridge = Node(
        package='scout2map_bridge',
        executable='sensor_bridge',
        name='sensor_bridge',
        output='screen',
        emulate_tty=True,
        parameters=[LaunchConfiguration('sensor_params_file')],
        condition=IfCondition(LaunchConfiguration('use_sensor_bridge')),
    )

    drive_bridge = Node(
        package='scout2map_bridge',
        executable='drive_bridge',
        name='drive_bridge',
        output='screen',
        emulate_tty=True,
        parameters=[
            LaunchConfiguration('drive_params_file'),
            # Overrides drive_bridge.yaml so the two never both publish the
            # transform. A tf tree with two publishers of one edge does not
            # error, it just jitters, which is expensive to diagnose later.
            {'publish_tf': ParameterValue(ekf_off, value_type=bool)},
        ],
        remappings=[
            ('drive/odom', LaunchConfiguration('odom_topic')),
            ('drive/imu', LaunchConfiguration('imu_topic')),
        ],
        condition=IfCondition(LaunchConfiguration('use_drive_bridge')),
    )

    gpio_events = Node(
        package='scout2map_bridge',
        executable='gpio_events',
        name='gpio_events',
        output='screen',
        emulate_tty=True,
        parameters=[LaunchConfiguration('gpio_params_file')],
        condition=IfCondition(LaunchConfiguration('use_gpio_events')),
    )

    drive_link_adapter = Node(
        package='s2m_bringup',
        executable='drive_link_adapter',
        name='drive_link_adapter',
        output='screen',
        emulate_tty=True,
        parameters=[LaunchConfiguration('drive_link_adapter_params_file')],
        condition=IfCondition(LaunchConfiguration('use_drive_link_adapter')),
    )

    ekf = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 's2m_ekf.launch.py')),
        launch_arguments={
            'use_ekf': LaunchConfiguration('use_ekf'),
            'ekf_params_file': LaunchConfiguration('ekf_params_file'),
            'wheel_odom_topic': LaunchConfiguration('odom_topic'),
            'imu_topic': LaunchConfiguration('imu_topic'),
            'ekf_odom_topic': '/odom',
            'ekf_publish_tf': 'true',
        }.items(),
        condition=IfCondition(LaunchConfiguration('use_ekf')),
    )

    # static_transform_publisher takes positional args as --x --y --z ...
    sensor_fusion_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='sensor_fusion_static_tf',
        output='screen',
        arguments=[
            '--frame-id', 'base_link',
            '--child-frame-id', 'sensor_fusion',
            '--x', LaunchConfiguration('sensor_fusion_x'),
            '--y', LaunchConfiguration('sensor_fusion_y'),
            '--z', LaunchConfiguration('sensor_fusion_z'),
        ],
        condition=IfCondition(LaunchConfiguration('publish_sensor_frames')),
    )

    range_link_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='range_link_static_tf',
        output='screen',
        arguments=[
            '--frame-id', 'base_link',
            '--child-frame-id', 'range_link',
            '--x', LaunchConfiguration('range_link_x'),
            '--y', LaunchConfiguration('range_link_y'),
            '--z', LaunchConfiguration('range_link_z'),
        ],
        condition=IfCondition(LaunchConfiguration('publish_sensor_frames')),
    )

    return LaunchDescription(args + [
        sensor_bridge,
        drive_bridge,
        gpio_events,
        drive_link_adapter,
        ekf,
        sensor_fusion_tf,
        range_link_tf,
    ])