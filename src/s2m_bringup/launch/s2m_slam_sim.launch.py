"""Launch the Scout2Map UGV simulation with SLAM Toolbox and Nav2."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _include(package_name, launch_file, arguments=None):
    package_share = get_package_share_directory(package_name)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_share, 'launch', launch_file)
        ),
        launch_arguments=(arguments or {}).items(),
    )


def generate_launch_description():
    bringup_share = get_package_share_directory('s2m_bringup')
    nav2_share = get_package_share_directory('nav2_bringup')

    nav2_params = LaunchConfiguration('nav2_params')
    slam_params = LaunchConfiguration('slam_params')
    use_rviz = LaunchConfiguration('use_rviz')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')

    world = _include('s2m_description', 'slip_test_world.launch.py')
    spawn = _include(
        's2m_description',
        'spawn_robot.launch.py',
        {'x_pose': x_pose, 'y_pose': y_pose},
    )
    slam = _include(
        'slam_toolbox',
        'online_sync_launch.py',
        {
            'use_sim_time': 'true',
            'slam_params_file': slam_params,
            'autostart': 'true',
        },
    )
    navigation = _include(
        'nav2_bringup',
        'navigation_launch.py',
        {
            'use_sim_time': 'true',
            'params_file': nav2_params,
            'autostart': 'true',
            'use_composition': 'false',
        },
    )
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=[
            '-d', os.path.join(nav2_share, 'rviz', 'nav2_default_view.rviz')
        ],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'nav2_params',
            default_value=os.path.join(bringup_share, 'config', 'nav2_lowspec.yaml'),
        ),
        DeclareLaunchArgument(
            'slam_params',
            default_value=os.path.join(bringup_share, 'config', 'slam_toolbox.yaml'),
        ),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('x_pose', default_value='0.0'),
        DeclareLaunchArgument('y_pose', default_value='0.0'),
        world,
        TimerAction(period=2.0, actions=[spawn]),
        TimerAction(period=4.0, actions=[slam, navigation, rviz]),
    ])
