"""Launch the Scout2Map UGV simulation with SLAM Toolbox and Nav2."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, ExecuteProcess, GroupAction,
    IncludeLaunchDescription, TimerAction)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap


def _include(package_name, launch_file, arguments=None):
    package_share = get_package_share_directory(package_name)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_share, 'launch', launch_file)
        ),
        launch_arguments=(arguments or {}).items(),
    )


def generate_launch_description():
    description_share = get_package_share_directory('s2m_description')
    bringup_share = get_package_share_directory('s2m_bringup')
    nav2_share = get_package_share_directory('nav2_bringup')

    nav2_params = LaunchConfiguration('nav2_params')
    slam_params = LaunchConfiguration('slam_params')
    use_rviz = LaunchConfiguration('use_rviz')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    nav_cmd_vel_topic = LaunchConfiguration('nav_cmd_vel_topic')
    headless = LaunchConfiguration('headless')

    resource_paths = [
        os.path.join(description_share, 'worlds'),
        os.environ.get('GZ_SIM_RESOURCE_PATH', ''),
    ]
    world_file = os.path.join(
        bringup_share, 'worlds', 'slip_test.world.sdf')
    world_env = {
        'GZ_SIM_RESOURCE_PATH': os.pathsep.join(filter(None, resource_paths))
    }
    world_gui = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_file],
        additional_env=world_env,
        output='screen',
        condition=UnlessCondition(headless),
    )
    world_headless = ExecuteProcess(
        cmd=['gz', 'sim', '-s', '-r', world_file],
        additional_env=world_env,
        output='screen',
        condition=IfCondition(headless),
    )
    spawn = _include(
        's2m_description',
        'spawn_robot.launch.py',
        {'x_pose': x_pose, 'y_pose': y_pose},
    )
    lidar_sensor_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='lidar_sensor_frame_bridge',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0',
            '--roll', '0', '--pitch', '0', '--yaw', '0',
            '--frame-id', 'lidar_link',
            '--child-frame-id', 'scout2map/base_link/rplidar_c1',
        ],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )
    imu_sensor_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='imu_sensor_frame_bridge',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0',
            '--roll', '0', '--pitch', '0', '--yaw', '0',
            '--frame-id', 'imu_link',
            '--child-frame-id', 'scout2map/base_link/bno055',
        ],
        parameters=[{'use_sim_time': True}],
        output='screen',
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
    navigation = GroupAction(actions=[
        SetRemap(src='/cmd_vel', dst=nav_cmd_vel_topic),
        _include(
            'nav2_bringup',
            'navigation_launch.py',
            {
                'use_sim_time': 'true',
                'params_file': nav2_params,
                'autostart': 'true',
                'use_composition': 'False',
            },
        ),
    ])
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
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('x_pose', default_value='0.0'),
        DeclareLaunchArgument('y_pose', default_value='0.0'),
        world_gui,
        world_headless,
        DeclareLaunchArgument(
            'nav_cmd_vel_topic',
            default_value='/cmd_vel',
        ),
        TimerAction(
            period=2.0, actions=[spawn, lidar_sensor_tf, imu_sensor_tf]),
        TimerAction(period=4.0, actions=[slam, navigation, rviz]),
    ])
