#!/usr/bin/env python3
"""Start the USB camera and Scout2Map Vision wrapper."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('scout_vision')
    default_params = os.path.join(share, 'config', 'vision.yaml')
    params = LaunchConfiguration('params_file')

    camera = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        output='screen',
        parameters=[params],
        remappings=[('image_raw', '/camera/image_raw')],
        condition=IfCondition(LaunchConfiguration('use_camera_driver')),
    )
    vision = Node(
        package='scout_vision',
        executable='vision_node',
        name='scout_vision',
        output='screen',
        emulate_tty=True,
        parameters=[
            params,
            {
                'model_path': LaunchConfiguration('model_path'),
                'labels_path': LaunchConfiguration('labels_path'),
            },
        ],
    )
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params),
        DeclareLaunchArgument('model_path', default_value=''),
        DeclareLaunchArgument('labels_path', default_value=''),
        DeclareLaunchArgument('use_camera_driver', default_value='true'),
        camera,
        vision,
    ])
