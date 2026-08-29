#!/usr/bin/env python3
"""Start the USB camera and Scout2Map Vision wrapper."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context, *args, **kwargs):
    share = get_package_share_directory('scout_vision')
    params = os.path.join(share, 'config', 'vision.yaml')

    # only override yaml values when the CLI arg is actually given
    model_path = LaunchConfiguration('model_path').perform(context)
    labels_path = LaunchConfiguration('labels_path').perform(context)
    overrides = {}
    if model_path:
        overrides['model_path'] = model_path
    if labels_path:
        overrides['labels_path'] = labels_path

    vision = Node(
        package='scout_vision',
        executable='vision_node',
        name='scout_vision',
        output='screen',
        emulate_tty=True,
        parameters=[params, overrides] if overrides else [params],
    )
    return [vision]


def generate_launch_description():
    share = get_package_share_directory('scout_vision')
    default_params = os.path.join(share, 'config', 'vision.yaml')

    camera = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        output='screen',
        parameters=[LaunchConfiguration('params_file')],
        remappings=[('image_raw', '/camera/image_raw')],
        condition=IfCondition(LaunchConfiguration('use_camera_driver')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params),
        DeclareLaunchArgument('model_path', default_value=''),
        DeclareLaunchArgument('labels_path', default_value=''),
        DeclareLaunchArgument('use_camera_driver', default_value='true'),
        camera,
        OpaqueFunction(function=launch_setup),
    ])