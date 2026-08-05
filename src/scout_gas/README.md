# scout_gas

scout_gas is the Scout2Map simulated selective gas sensor and hexagonal
risk-map package. It reads the robot pose from map -> base_link,
publishes gas concentration and RViz markers, and stores the accumulated
measurements beside the occupancy map.

## Topics

| Topic | Type | Purpose |
|---|---|---|
| /gas/concentration | std_msgs/Float32 | Selected sensor reading in ppm |
| `/gas/truth/<GAS>` | `std_msgs/Float32` | Simulated ground truth per gas |
| /gas/hex | visualization_msgs/MarkerArray | Hexagonal risk map |
| /gas/sources | visualization_msgs/MarkerArray | Simulated gas-source markers |

The sensor type, sources and thresholds are configured in
config/gas_world.yaml.

## Run

After installing the Raspberry Pi or simulation environment:

    source ~/scout2map_env.sh
    ros2 launch scout_gas sim_with_gas.launch.py

To omit RViz:

    ros2 launch scout_gas sim_with_gas.launch.py use_rviz:=false

The data directory is selected in this order:

1. SCOUT2MAP_DATA_DIR, when set.
2. ~/scout2map_data on Raspberry Pi and other Linux systems.

The default output files are:

- maps/sim_gas_hex.json
- maps/sim_map.pgm
- maps/sim_map.yaml

## Verify

    ros2 topic hz /gas/concentration
    ros2 topic echo /gas/concentration --once
    ros2 topic echo /gas/hex --once
    ls -lh "$SCOUT2MAP_DATA_DIR/maps"
