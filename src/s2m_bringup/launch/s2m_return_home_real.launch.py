#!/usr/bin/env python3
"""Start the real UGV stack with a single fail-safe cmd_vel path."""

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
        real_stack,
        safety_gate,
        return_home,
    ])
