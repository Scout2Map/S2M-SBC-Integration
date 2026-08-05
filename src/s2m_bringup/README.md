# s2m_bringup

Scout2Map UGV 형상, Gazebo world, SLAM Toolbox와 Nav2를 하나의 시뮬레이션으로
시작하는 ROS 2 Jazzy package입니다.

## 실행

```bash
source ~/scout2map_ws/install/setup.bash
ros2 launch s2m_bringup s2m_slam_sim.launch.py
```

| launch 인자 | 기본값 | 설명 |
|---|---|---|
| `nav2_params` | `config/nav2_lowspec.yaml` | Nav2 parameter 파일 |
| `slam_params` | `config/slam_toolbox.yaml` | SLAM Toolbox parameter 파일 |
| `use_rviz` | `true` | RViz2 실행 여부 |
| `x_pose` | `0.0` | Gazebo spawn x 좌표 |
| `y_pose` | `0.0` | Gazebo spawn y 좌표 |

## 예상 데이터 흐름

```text
Gazebo diff drive -> /odom -> odom -> base_link
Gazebo lidar      -> /scan -> SLAM Toolbox -> map -> odom
Nav2              -> /cmd_vel -> Gazebo diff drive
```

필수 확인 토픽:

```bash
ros2 topic hz /clock
ros2 topic hz /scan
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo map base_link
```

## 제한사항

- world와 robot spawn은 각각 0초와 2초, SLAM/Nav2는 4초에 시작합니다. 이 지연은
  process readiness를 보장하지 않습니다.
- `nav2_lowspec.yaml`은 초기 시뮬레이션 값이며 실차 제동거리와 동역학 검증을 거치지
  않았습니다.
- 저장 지도 localization/AMCL과 실차 센서·EKF를 한 번에 시작하는 launch는 별도로
  구성해야 합니다.
