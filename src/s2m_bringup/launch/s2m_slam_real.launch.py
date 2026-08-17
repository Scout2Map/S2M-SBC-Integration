#!/usr/bin/env python3
"""Bring up SLAM on the real UGV: URDF, LiDAR, MCU bridges, slam_toolbox, Nav2.

This is the hardware counterpart to s2m_slam_sim.launch.py. Nothing here starts
Gazebo and every node runs on wall time.

Layer order matters, because each layer depends on the TF the previous one
publishes:

  1. robot_state_publisher   base_link -> lidar_link, imu_link, wheel links
  2. s2m_onboard_bridge      odom -> base_link, plus sensor_fusion, range_link
  3. sllidar_ros2            /scan stamped in lidar_link
  4. slam_toolbox            map -> odom
  5. nav2                    consumes all of the above

Nav2 is off by default. Bring the stack up without it, confirm the map and TF
tree are stable, then relaunch with use_nav2:=true.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription, TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    description_share = get_package_share_directory('s2m_description')
    bringup_share = get_package_share_directory('s2m_bringup')

    xacro_file = os.path.join(
        description_share, 'urdf', 'scout2map.urdf.xacro')
    default_slam_params = os.path.join(
        bringup_share, 'config', 'slam_toolbox_real.yaml')
    default_nav2_params = os.path.join(
        bringup_share, 'config', 'nav2_lowspec.yaml')

    args = [
        # --- layer toggles ---
        DeclareLaunchArgument(
            'use_bridges', default_value='true',
            description='Start the MCU bridges. Set false if they are already '
                        'running in another terminal.'),
        DeclareLaunchArgument('use_lidar', default_value='true'),
        DeclareLaunchArgument('use_slam', default_value='true'),
        DeclareLaunchArgument(
            'use_nav2', default_value='false',
            description='Start Nav2. Confirm SLAM and TF first.'),
        DeclareLaunchArgument('use_rviz', default_value='false'),

        # Wheel joints are continuous, so without a joint state source
        # robot_state_publisher cannot complete the tree and RViz complains.
        # The drive bridge does not publish /joint_states yet, so zeros are
        # used. Wheel angle does not affect the sensor TF chain.
        DeclareLaunchArgument('use_joint_state_publisher', default_value='true'),

        # --- lidar ---
        DeclareLaunchArgument(
            'lidar_port', default_value='/dev/scout2map_lidar',
            description='Falls back to /dev/ttyUSB0 if the udev rule is not '
                        'installed yet.'),
        DeclareLaunchArgument('lidar_baudrate', default_value='460800'),

        # sllidar defaults this to "laser". It must match the URDF link or
        # slam_toolbox silently discards every scan.
        DeclareLaunchArgument('lidar_frame', default_value='lidar_link'),
        DeclareLaunchArgument('lidar_scan_mode', default_value='Standard'),

        # --- params ---
        DeclareLaunchArgument('slam_params', default_value=default_slam_params),
        DeclareLaunchArgument('nav2_params', default_value=default_nav2_params),

        # Seconds to wait before starting SLAM and Nav2. The bridges need to
        # open their serial ports and the LiDAR needs to spin up first.
        DeclareLaunchArgument('slam_start_delay', default_value='5.0'),
        DeclareLaunchArgument('nav2_start_delay', default_value='10.0'),
    ]

    # xacro is expanded here so robot_description is a plain URDF string
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': False,
        }],
    )

    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('use_joint_state_publisher')),
    )

    bridges = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 's2m_onboard_bridge.launch.py')
        ),
        condition=IfCondition(LaunchConfiguration('use_bridges')),
    )

    lidar = Node(
        package='sllidar_ros2',
        executable='sllidar_node',
        name='sllidar_node',
        output='screen',
        parameters=[{
            'serial_port': LaunchConfiguration('lidar_port'),
            'serial_baudrate': LaunchConfiguration('lidar_baudrate'),
            'frame_id': LaunchConfiguration('lidar_frame'),
            'inverted': False,
            'angle_compensate': True,
            'scan_mode': LaunchConfiguration('lidar_scan_mode'),
            'use_sim_time': False,
        }],
        condition=IfCondition(LaunchConfiguration('use_lidar')),
    )

    # slam_toolbox is a lifecycle node. Starting it with a plain Node action
    # leaves it unconfigured forever: it never declares its own parameters, so
    # the params file appears to be ignored and nothing is ever published, with
    # no error to explain why. Its own launch file drives the transitions.
    slam = TimerAction(
        period=LaunchConfiguration('slam_start_delay'),
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('slam_toolbox'),
                    'launch', 'online_async_launch.py')
            ),
            launch_arguments={
                'use_sim_time': 'false',
                'slam_params_file': LaunchConfiguration('slam_params'),
            }.items(),
        )],
        condition=IfCondition(LaunchConfiguration('use_slam')),
    )

    nav2 = TimerAction(
        period=LaunchConfiguration('nav2_start_delay'),
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('nav2_bringup'),
                    'launch', 'navigation_launch.py')
            ),
            launch_arguments={
                'use_sim_time': 'false',
                'params_file': LaunchConfiguration('nav2_params'),
                'autostart': 'true',
            }.items(),
        )],
        condition=IfCondition(LaunchConfiguration('use_nav2')),
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        parameters=[{'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription(args + [
        robot_state_publisher,
        joint_state_publisher,
        bridges,
        lidar,
        slam,
        nav2,
        rviz,
    ])
