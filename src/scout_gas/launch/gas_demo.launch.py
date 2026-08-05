"""Launch the simulated gas sensor (hexagonal gas-risk map).

Run this after the Scout2Map simulation is up, e.g.:
    ros2 launch scout_gas gas_demo.launch.py
"""
import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('scout_gas')
    default_cfg = os.path.join(pkg, 'config', 'gas_world.yaml')
    default_data_dir = os.environ.get(
        'SCOUT2MAP_DATA_DIR',
        os.path.join(os.path.expanduser('~'), 'scout2map_data'),
    )

    config_file = LaunchConfiguration('config_file')
    output_path = LaunchConfiguration('output_path')
    hex_size = LaunchConfiguration('hex_size')

    return LaunchDescription([
        DeclareLaunchArgument('config_file', default_value=default_cfg,
                              description='Plain-YAML gas world (sources + thresholds)'),
        DeclareLaunchArgument(
            'output_path',
            default_value=os.path.join(default_data_dir, 'maps', 'sim_gas_hex.json'),
            description='Where to save the hex gas map + events'),
        DeclareLaunchArgument('hex_size', default_value='0.3',
                              description='Hexagon circumradius in meters'),
        Node(
            package='scout_gas',
            executable='gas_sensor_node',
            name='gas_sensor_node',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'config_file': config_file,
                'output_path': output_path,
                'hex_size': hex_size,
                'base_frame': 'base_link',
                'map_frame': 'map',
                'update_rate': 5.0,
            }],
        ),
    ])
