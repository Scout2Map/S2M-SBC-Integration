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

실차 drive link 토픽은 `drive_link_adapter`가 제공합니다. onboard localization은
아직 별도 구현이 필요합니다.

## 실차 MCU 브리지

```bash
ros2 launch s2m_bringup s2m_onboard_bridge.launch.py
```

`scout2map_bridge`의 `sensor_bridge`와 `drive_bridge`를 시작하고, 이 저장소의
Nav2/SLAM 설정이 읽는 이름으로 토픽을 정리합니다.

| launch 인자 | 기본값 | 설명 |
|---|---|---|
| `use_sensor_bridge` | `true` | Pico 2 센서 브리지 실행 여부 |
| `use_drive_bridge` | `true` | STM32 주행 브리지 실행 여부 |
| `use_drive_link_adapter` | `true` | `DriveStatus` -> `/drive/link_ok` 변환 |
| `use_ekf` | `true` | `robot_localization`에 `/odom`과 TF를 넘김 |
| `odom_topic` | `use_ekf` 따라감 | `drive/odom` remap 대상 |
| `imu_topic` | `/imu/data` | `drive/imu` remap 대상 |
| `publish_sensor_frames` | `true` | `sensor_fusion`, `range_link` static TF |
| `sensor_fusion_x/y/z` | `-0.050 / 0.000 / 0.110` | 측정값 아님, 실차에서 교체 |
| `range_link_x/y/z` | `0.132 / 0.000 / 0.050` | 측정값 아님, 실차에서 교체 |

`s2m_slam_sim.launch.py`와 동시에 실행하면 `/odom`, `/imu/data`, `/cmd_vel`과
`odom -> base_link` TF가 충돌합니다. 둘 중 하나만 실행합니다.

### EKF (robot_localization)

기본값이 `true`이며 `s2m_ekf.launch.py`가 함께 올라와 `odom -> base_link`의 발행 주체가
바뀝니다. `robot_localization`이 설치돼 있지 않거나 브리지 단독으로 확인할 때만
`use_ekf:=false`로 되돌립니다. `odom_topic`과 `drive_bridge`의 `publish_tf`는 launch가 자동으로 맞추므로
따로 지정하지 않습니다.

| `use_ekf` | `odom_topic` | `drive_bridge.publish_tf` | `odom -> base_link` |
|---|---|---|---|
| `false` | `/odom` | `true` | `drive_bridge` |
| `true` | `/drive/odom` | `false` | `ekf_filter_node` |

EKF 출력이 `/odom`으로 리맵되므로 `nav2_lowspec.yaml`과 `slam_toolbox_real.yaml`은
수정할 필요가 없습니다.

융합하는 상태는 휠 오도메트리의 `vx`, IMU의 `yaw`와 `vyaw` 세 개뿐입니다. 휠 pose를
받지 않는 이유는 `/drive/odom` 한 메시지 안에 헤딩 출처가 둘(엔코더 적분 위치, IMU
쿼터니언 방향) 섞여 있어 IMU yaw가 이중으로 계상되기 때문입니다. 휠 `vyaw`는
`skid_factor` 만큼 과대하고, IMU 가속도는 브리지에서 yaw 오프셋이 이중 적용되어 있어
둘 다 제외했습니다. 근거와 튜닝 지점은 `config/ekf.yaml`의 주석에 있습니다.

TF 이관 없이 기존 `/odom`과 나란히 비교하려면 EKF만 따로 띄웁니다.

```bash
ros2 launch s2m_bringup s2m_ekf.launch.py \
  ekf_odom_topic:=/odometry/filtered ekf_publish_tf:=false \
  wheel_odom_topic:=/odom
```

### drive_link_adapter

`return_home`은 `std_msgs/msg/Bool` 타입의 `/drive/link_ok`를 구독하지만 브리지는
`scout2map_msgs/msg/DriveStatus`를 발행합니다. 이 노드가 둘을 잇습니다. 다음 조건 중
하나라도 성립하면 `false`를 발행합니다.

- `DriveStatus`가 `status_timeout_sec` 동안 도착하지 않음
- `link_ok == false`
- `estop_latched`, `fault_stall`, `cmd_timeout`, `batt_dead` 중 하나가 참

`batt_critical`은 기본적으로 복귀를 막지 않습니다. 파라미터는
`config/drive_link_adapter.yaml`에 있습니다.

## 실차 자동 복귀 mission

```bash
ros2 launch s2m_bringup s2m_return_home_real.launch.py \
  map_id:=mapping_20260818
```

이 launch는 실차 SLAM/Nav2, Event Engine, return_home과 안전 게이트를 함께 시작합니다.
Nav2 출력은 `/return_home/cmd_vel_input`으로 remap되며 `cmd_vel_safety_gate`만 최종
`/cmd_vel`을 발행합니다. 실차 설정은 `auto_capture_start`와 `auto_arm`이 모두
`false`이므로 정상 heartbeat, `/drive/link_ok`, `map -> base_link`를 확인한 뒤 다음
서비스를 호출합니다.

```bash
ros2 service call /return_home/capture_start std_srvs/srv/Trigger "{}"
ros2 service call /return_home/arm std_srvs/srv/SetBool "{data: true}"
```

teleop도 직접 `/cmd_vel`을 발행하지 않고 게이트 입력으로 remap합니다.

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -r cmd_vel:=/return_home/cmd_vel_input
```

## 예상 데이터 흐름

```text
Gazebo diff drive -> /odom -> odom -> base_link
Gazebo lidar      -> /scan -> SLAM Toolbox -> map -> odom
Nav2              -> /return_home/cmd_vel_input
return_home gate  -> /cmd_vel -> Gazebo diff drive

Real drive bridge -> /drive/odom -> /odom -> odom -> base_link
Real Nav2/teleop   -> /return_home/cmd_vel_input
return_home gate  -> /cmd_vel -> STM32 drive bridge
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
- `DriveStatus.link_ok`는 telemetry freshness를 나타내며 CRC 오류율과 PING/PONG 왕복
  성공까지 종합한 품질 지표는 아닙니다.
- `s2m_onboard_bridge.launch.py`의 static TF 오프셋은 측정값이 아닙니다. 이벤트
  마커 좌표를 신뢰하기 전에 실측값으로 교체해야 합니다.
