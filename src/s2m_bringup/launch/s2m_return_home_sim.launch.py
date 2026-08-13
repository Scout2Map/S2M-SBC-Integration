"""Launch Scout2Map SLAM/Nav2 simulation with return-home fault injection."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup_share = get_package_share_directory('s2m_bringup')

    base_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 's2m_slam_sim.launch.py')
        ),
        launch_arguments={
            'nav2_params': LaunchConfiguration('nav2_params'),
            'slam_params': LaunchConfiguration('slam_params'),
            'use_rviz': LaunchConfiguration('use_rviz'),
            'headless': LaunchConfiguration('headless'),
            'x_pose': LaunchConfiguration('x_pose'),
            'y_pose': LaunchConfiguration('y_pose'),
            'nav_cmd_vel_topic': '/return_home/cmd_vel_input',
        }.items(),
    )

    return_home_params = LaunchConfiguration('return_home_params')
    return_home = Node(
        package='s2m_bringup',
        executable='return_home',
        name='return_home',
        output='screen',
        emulate_tty=True,
        parameters=[return_home_params],
    )
    fault_injector = Node(
        package='s2m_bringup',
        executable='sim_fault_injector',
        name='sim_fault_injector',
        output='screen',
        emulate_tty=True,
        parameters=[return_home_params],
    )
    safety_gate = Node(
        package='s2m_bringup',
        executable='cmd_vel_safety_gate',
        name='cmd_vel_safety_gate',
        output='screen',
        emulate_tty=True,
        parameters=[return_home_params],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'nav2_params',
            default_value=os.path.join(
                bringup_share, 'config', 'nav2_lowspec.yaml'),
        ),
        DeclareLaunchArgument(
            'slam_params',
            default_value=os.path.join(
                bringup_share, 'config', 'slam_toolbox.yaml'),
        ),
        DeclareLaunchArgument(
            'return_home_params',
            default_value=os.path.join(
                bringup_share, 'config', 'return_home_sim.yaml'),
        ),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('x_pose', default_value='-3.0'),
        DeclareLaunchArgument('y_pose', default_value='0.0'),
        base_sim,
        fault_injector,
        safety_gate,
        return_home,
    ])
