#!/usr/bin/env python3
"""Bring up SLAM on the real UGV: URDF, LiDAR, MCU bridges, slam_toolbox, Nav2.

This is the hardware counterpart to s2m_slam_sim.launch.py. Nothing here starts
Gazebo and every node runs on wall time.

Layer order matters, because each layer depends on the TF the previous one
publishes:

  1. robot_state_publisher   base_link -> lidar_link, imu_link, wheel links
  2. s2m_onboard_bridge      odom -> base_link, plus sensor_fusion, range_link
                             with use_ekf:=true that transform comes from
                             robot_localization instead of the drive bridge
  3. sllidar_ros2            /scan stamped in lidar_link
  4. slam_toolbox            map -> odom
  5. nav2                    consumes all of the above
  6. explore_lite            optional; drives Nav2 from Nav2's own costmap
  7. scout_vision            optional; publishes detections for Event Engine

Nav2 is off by default. Bring the stack up without it, confirm the map and TF
tree are stable, then relaunch with use_nav2:=true. Frontier exploration
(use_exploration:=true) needs Nav2's global costmap already publishing, so
enable use_nav2 too -- the launch file does not enforce that dependency for
you, it only starts the node later than nav2_start_delay.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    description_share = get_package_share_directory('s2m_description')
    bringup_share = get_package_share_directory('s2m_bringup')
    event_share = get_package_share_directory('scout2map_event')
    vision_share = get_package_share_directory('scout_vision')

    xacro_file = os.path.join(
        description_share, 'urdf', 'scout2map.urdf.xacro')
    default_slam_params = os.path.join(
        bringup_share, 'config', 'slam_toolbox_real.yaml')
    default_nav2_params = os.path.join(
        bringup_share, 'config', 'nav2_lowspec.yaml')
    default_event_params = os.path.join(
        event_share, 'config', 'event_engine.yaml')
    default_explore_params = os.path.join(
        bringup_share, 'config', 'explore_lite.yaml')
    default_vision_params = os.path.join(
        vision_share, 'config', 'vision.yaml')
    default_lidar_port = (
        '/dev/scout2map_lidar'
        if os.path.exists('/dev/scout2map_lidar')
        else '/dev/ttyUSB0'
    )

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
        DeclareLaunchArgument(
            'use_event_engine', default_value='false',
            description='Start the threshold event engine.'),
        DeclareLaunchArgument(
            'use_event_markers', default_value='false',
            description='Show /events as RViz markers (debug/test).'),
        DeclareLaunchArgument(
            'use_exploration', default_value='false',
            description='Start frontier exploration (explore_lite). '
                        'Requires use_nav2:=true; see module docstring.'),
        DeclareLaunchArgument(
            'use_vision', default_value='false',
            description='Start the USB camera and AI Vision wrapper.'),
        DeclareLaunchArgument('use_rviz', default_value='false'),

        # Passed straight through to s2m_onboard_bridge.launch.py, which is
        # where the odom -> base_link ownership switch actually happens. It
        # only takes effect when use_bridges is true, because the EKF belongs
        # to the bridge layer; if the bridges run in another terminal, pass
        # use_ekf there instead.
        DeclareLaunchArgument(
            'use_ekf', default_value='true',
            description='Fuse wheel odometry and IMU with robot_localization '
                        'and let it own /odom and odom -> base_link.'),

        # Wheel joints are continuous, so without a joint state source
        # robot_state_publisher cannot complete the tree and RViz complains.
        # The drive bridge does not publish /joint_states yet, so zeros are
        # used. Wheel angle does not affect the sensor TF chain.
        DeclareLaunchArgument('use_joint_state_publisher', default_value='true'),

        # --- lidar ---
        DeclareLaunchArgument(
            'lidar_port', default_value=default_lidar_port,
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
        DeclareLaunchArgument('event_params', default_value=default_event_params),
        DeclareLaunchArgument(
            'explore_params', default_value=default_explore_params),
        DeclareLaunchArgument(
            'vision_params', default_value=default_vision_params),
        DeclareLaunchArgument('vision_model', default_value=''),
        DeclareLaunchArgument('vision_labels', default_value=''),
        DeclareLaunchArgument(
            'map_id', default_value='',
            description='Mapping-session identifier included in event JSON.'),
        DeclareLaunchArgument(
            'nav_cmd_vel_topic', default_value='/cmd_vel',
            description='Destination for Nav2 velocity output.'),

        # Seconds to wait before starting SLAM and Nav2. The bridges need to
        # open their serial ports and the LiDAR needs to spin up first.
        DeclareLaunchArgument('slam_start_delay', default_value='5.0'),
        DeclareLaunchArgument('event_start_delay', default_value='6.0'),
        DeclareLaunchArgument('nav2_start_delay', default_value='10.0'),
        # Nav2's global costmap needs a few seconds after navigation_launch.py
        # comes up before it has published anything explore_lite can read, so
        # this is later than nav2_start_delay, not relative to it (launch
        # arguments cannot be summed as substitutions here).
        DeclareLaunchArgument('exploration_start_delay', default_value='16.0'),
        DeclareLaunchArgument('vision_start_delay', default_value='7.0'),
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
        launch_arguments={
            'use_ekf': LaunchConfiguration('use_ekf'),
        }.items(),
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
        actions=[GroupAction(actions=[
            SetRemap(
                src='/cmd_vel',
                dst=LaunchConfiguration('nav_cmd_vel_topic')),
            IncludeLaunchDescription(
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
            ),
        ])],
        condition=IfCondition(LaunchConfiguration('use_nav2')),
    )

    event_engine = TimerAction(
        period=LaunchConfiguration('event_start_delay'),
        actions=[Node(
            package='scout2map_event',
            executable='event_engine',
            name='event_engine',
            output='screen',
            emulate_tty=True,
            parameters=[
                LaunchConfiguration('event_params'),
                {'map_id': LaunchConfiguration('map_id')},
            ],
        )],
        condition=IfCondition(LaunchConfiguration('use_event_engine')),
    )

    event_markers = TimerAction(
        period=LaunchConfiguration('event_start_delay'),
        actions=[Node(
            package='scout2map_event',
            executable='event_marker_bridge',
            name='event_marker_bridge',
            output='screen',
            emulate_tty=True,
        )],
        condition=IfCondition(LaunchConfiguration('use_event_markers')),
    )

    exploration = TimerAction(
        period=LaunchConfiguration('exploration_start_delay'),
        actions=[Node(
            package='explore_lite',
            executable='explore',
            name='explore_node',
            output='screen',
            emulate_tty=True,
            parameters=[
                LaunchConfiguration('explore_params'),
                {'use_sim_time': False},
            ],
        )],
        condition=IfCondition(LaunchConfiguration('use_exploration')),
    )

    vision = TimerAction(
        period=LaunchConfiguration('vision_start_delay'),
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(vision_share, 'launch', 'vision.launch.py')
            ),
            launch_arguments={
                'params_file': LaunchConfiguration('vision_params'),
                'model_path': LaunchConfiguration('vision_model'),
                'labels_path': LaunchConfiguration('vision_labels'),
            }.items(),
        )],
        condition=IfCondition(LaunchConfiguration('use_vision')),
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
        event_engine,
        event_markers,
        nav2,
        exploration,
        vision,
        rviz,
    ])
