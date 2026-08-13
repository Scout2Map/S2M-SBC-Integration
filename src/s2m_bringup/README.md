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
| `headless` | `false` | Gazebo GUI 없이 서버 모드 실행 |
| `x_pose` | `0.0` | Gazebo spawn x 좌표 |
| `y_pose` | `0.0` | Gazebo spawn y 좌표 |

WSL 또는 CI에서는 다음과 같이 실행합니다.

```bash
ros2 launch s2m_bringup s2m_slam_sim.launch.py \
  headless:=true use_rviz:=false
```

## 자동 복귀 시뮬레이션

```bash
ros2 launch s2m_bringup s2m_return_home_sim.launch.py
```

headless 검증은 `headless:=true use_rviz:=false`를 추가합니다.

이 launch는 Nav2의 속도 출력을 `/return_home/cmd_vel_input`으로 remap하고,
`cmd_vel_safety_gate`만 최종 `/cmd_vel`을 발행하도록 구성합니다.

```bash
ros2 topic echo /return_home/status
ros2 service call /sim_faults/set_network std_srvs/srv/SetBool "{data: false}"
```

관제 heartbeat가 끊기고 drive link와 TF가 정상이면 저장한 시작 좌표를
NavigateToPose goal로 전송합니다. drive link 또는 TF가 끊기면 SAFE_STOP입니다.
watchdog은 simulation clock이 멈춰도 동작하도록 steady clock을 사용합니다.

```bash
ros2 service call /sim_faults/set_drive_link std_srvs/srv/SetBool "{data: false}"
ros2 service call /sim_faults/reset std_srvs/srv/Trigger "{}"
ros2 service call /return_home/reset std_srvs/srv/Trigger "{}"
```

실차 drive link 토픽과 onboard localization은 아직 별도 구현이 필요합니다.

## 예상 데이터 흐름

```text
Gazebo diff drive -> /odom -> odom -> base_link
Gazebo lidar      -> /scan -> SLAM Toolbox -> map -> odom
Nav2              -> /return_home/cmd_vel_input
return_home gate  -> /cmd_vel -> Gazebo diff drive
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
