#!/usr/bin/env python3
"""Start the real UGV stack with a single fail-safe cmd_vel path.

Thin wrapper around s2m_slam_real.launch.py (use_nav2:=true by default here)
plus cmd_vel_safety_gate + return_home on top. In practice the field
workflow runs s2m_slam_real.launch.py directly with
use_nav2:=true use_return_home:=true instead of this wrapper - kept in sync
(same defaults, same pass-through args) so either path works, but if you're
looking for "the" launch command actually used day to day, that's it.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup_share = get_package_share_directory('s2m_bringup')
    event_share = get_package_share_directory('scout2map_event')
    vision_share = get_package_share_directory('scout_vision')
    comm_relay_share = get_package_share_directory('scout2map_comm')

    real_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 's2m_slam_real.launch.py')
        ),
        launch_arguments={
            'use_bridges': LaunchConfiguration('use_bridges'),
            'use_lidar': LaunchConfiguration('use_lidar'),
            'use_slam': LaunchConfiguration('use_slam'),
            'use_nav2': LaunchConfiguration('use_nav2'),
            'use_event_engine': LaunchConfiguration('use_event_engine'),
            'use_event_markers': LaunchConfiguration('use_event_markers'),
            'use_vision': LaunchConfiguration('use_vision'),
            'use_rviz': LaunchConfiguration('use_rviz'),
            'event_params': LaunchConfiguration('event_params'),
            'vision_params': LaunchConfiguration('vision_params'),
            'vision_model': LaunchConfiguration('vision_model'),
            'vision_labels': LaunchConfiguration('vision_labels'),
            'map_id': LaunchConfiguration('map_id'),
            'nav_cmd_vel_topic': '/return_home/cmd_vel_input',
            # s2m_slam_real.launch.py already starts scout2map_comm itself
            # (use_comm_relay, on by default) - pass these through instead of
            # also starting a second comm_relay node below, which would just
            # fail to bind the same WebSocket port.
            'use_comm_relay': LaunchConfiguration('use_comm_relay'),
            'comm_relay_params': LaunchConfiguration('comm_relay_params'),
        }.items(),
    )

    params = LaunchConfiguration('return_home_params')
    safety_gate = Node(
        package='s2m_bringup',
        executable='cmd_vel_safety_gate',
        name='cmd_vel_safety_gate',
        output='screen',
        emulate_tty=True,
        parameters=[params],
    )
    return_home = Node(
        package='s2m_bringup',
        executable='return_home',
        name='return_home',
        output='screen',
        emulate_tty=True,
        parameters=[params],
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_bridges', default_value='true'),
        DeclareLaunchArgument('use_lidar', default_value='true'),
        DeclareLaunchArgument('use_slam', default_value='true'),
        DeclareLaunchArgument('use_nav2', default_value='true'),
        DeclareLaunchArgument('use_event_engine', default_value='true'),
        DeclareLaunchArgument('use_event_markers', default_value='false'),
        DeclareLaunchArgument('use_vision', default_value='false'),
        DeclareLaunchArgument('use_rviz', default_value='false'),
        DeclareLaunchArgument('map_id', default_value=''),
        DeclareLaunchArgument(
            'event_params',
            default_value=os.path.join(
                event_share, 'config', 'event_engine.yaml')),
        DeclareLaunchArgument(
            'vision_params',
            default_value=os.path.join(
                vision_share, 'config', 'vision.yaml')),
        DeclareLaunchArgument('vision_model', default_value=''),
        DeclareLaunchArgument('vision_labels', default_value=''),
        DeclareLaunchArgument(
            'return_home_params',
            default_value=os.path.join(
                bringup_share, 'config', 'return_home_real.yaml')),
        DeclareLaunchArgument('use_comm_relay', default_value='true'),
        DeclareLaunchArgument(
            'comm_relay_params',
            default_value=os.path.join(
                comm_relay_share, 'config', 'comm_relay.yaml')),
        real_stack,
        safety_gate,
        return_home,
    ])
