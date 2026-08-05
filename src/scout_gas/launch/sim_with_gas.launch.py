"""One-shot: SLAM sim (Gazebo + slam_toolbox + Nav2) + the gas sensor.

    ros2 launch scout_gas sim_with_gas.launch.py            # Gazebo GUI + RViz
    ros2 launch scout_gas sim_with_gas.launch.py use_rviz:=False

The gas node tolerates the sim not being ready yet (it simply waits for the
map->base_link transform), so launch ordering is not critical.
"""
import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('s2m_bringup')
    gas_pkg = get_package_share_directory('scout_gas')
    default_cfg = os.path.join(gas_pkg, 'config', 'gas_world.yaml')
    default_data_dir = os.environ.get(
        'SCOUT2MAP_DATA_DIR',
        os.path.join(os.path.expanduser('~'), 'scout2map_data'),
    )

    use_rviz = LaunchConfiguration('use_rviz')
    config_file = LaunchConfiguration('config_file')
    output_path = LaunchConfiguration('output_path')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup, 'launch', 's2m_slam_sim.launch.py')),
        launch_arguments={'use_rviz': use_rviz}.items(),
    )

    gas = Node(
        package='scout_gas', executable='gas_sensor_node', name='gas_sensor_node',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'config_file': config_file,
            'output_path': output_path,
            'hex_size': 0.3,
            'base_frame': 'base_link',
            'map_frame': 'map',
            'update_rate': 5.0,
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_rviz', default_value='True'),
        DeclareLaunchArgument('config_file', default_value=default_cfg),
        DeclareLaunchArgument(
            'output_path',
            default_value=os.path.join(default_data_dir, 'maps', 'sim_gas_hex.json')),
        sim,
        gas,
    ])
