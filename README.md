# S2M SBC Integration

Raspberry Pi 5에서 Scout2Map UGV의 ROS 2 실행 환경을 설치하고, 실차 형상 기반
Gazebo 시뮬레이션과 SLAM/Nav2·가스 위험 지도 기능을 실행하기 위한 통합 프로젝트입니다.

## 구현된 기능

- Ubuntu 24.04와 ROS 2 Jazzy 설치 및 호환성 점검
- 실차 `base_link`·LiDAR·IMU 프레임을 사용하는 Gazebo bringup
- SLAM Toolbox와 Nav2의 저사양 시뮬레이션 설정
- 관제망 단절 시 Nav2 출발점 복귀와 주행 링크·TF 장애 안전 정지 시뮬레이션
- 선택성 가스 센서, 육각형 위험 지도, 이벤트 JSON과 occupancy map 저장
- Pico 센서와 STM32 주행 MCU의 USB CDC 장치, ROS 토픽, TF 프레임 점검
- 주행 브리지 `DriveStatus`를 자동 복귀 정책의 `/drive/link_ok`로 변환
- 임계값 이벤트 엔진(`scout2map_event`) 워크스페이스 통합
- RPLIDAR C1 드라이버 및 선택형 OpenCV/ONNX Runtime 설치
- Python/XML/YAML/Markdown/셸 정적 검사 자동화

## 폴더 구조

```text
S2M-SBC-Integration/
├── .github/workflows/
│   └── static-checks.yml          # 정적 검사 CI
├── docs/integration/
│   ├── bridge-interface-contract.md  # MCU 브리지 토픽·프레임 계약
│   ├── implementation-status.md   # 구현·검증 상태
│   ├── map-marker-coordinate-design.md
│   ├── repository-baseline-2026-08-18.md
│   ├── real-hardware-validation.md
│   ├── return-home-simulation-plan.md
│   ├── sbc-runbook.md
│   ├── simulation-validation-guide.md
│   ├── slam-nav2-ugv-validation.md
│   └── ugv-validation-checklist.md
├── scripts/raspberry_pi/
│   ├── install.sh                 # ROS 2와 워크스페이스 설치
│   ├── check_compatibility.sh     # OS·패키지·장치 점검
│   ├── check_mcu_interfaces.sh    # USB CDC와 ROS 토픽 점검
│   ├── install_rplidar.sh
│   ├── create_vision_venv.sh
│   ├── udev/                      # 안정적인 USB CDC 장치명 설정
│   └── manifests/                 # apt/pip 설치 목록
├── src/
│   ├── s2m_bringup/               # Gazebo + SLAM Toolbox + Nav2
│   └── scout_gas/                 # 가스 센서·위험 지도 시뮬레이션
├── dependencies.repos             # 빌드에 필요한 ROS 소스 목록
├── RELEASE_NOTES.md               # 통합 버전별 변경과 검증 범위
├── LICENSE                        # Apache-2.0
└── tools/static_check.py
```

## 지원 환경

| 항목 | 기준 |
|---|---|
| 운영체제 | Ubuntu 24.04 LTS |
| ROS | ROS 2 Jazzy |
| 실차 SBC | Raspberry Pi 5, arm64 |
| 개발·시뮬레이션 | amd64 또는 arm64 |
| 시뮬레이터 | Gazebo Harmonic + `ros_gz` |

설치 스크립트는 일반 사용자 계정으로 실행해야 하며 필요한 단계에서만 `sudo`를
사용합니다. 루트 사용자로 직접 실행하지 마십시오.

## 설치

```bash
git clone https://github.com/Scout2Map/S2M-SBC-Integration.git
cd S2M-SBC-Integration
chmod +x scripts/raspberry_pi/*.sh
```

### Raspberry Pi 실차 환경

```bash
./scripts/raspberry_pi/install.sh \
  --profile onboard
sudo reboot
```

RPLIDAR 패키지는 onboard profile에 포함됩니다. 카메라와 ONNX Runtime Python 환경은
기본 설치 후 `scripts/raspberry_pi/create_vision_venv.sh onnx`로 별도 구성합니다.

### Gazebo 개발 환경

```bash
./scripts/raspberry_pi/install.sh --profile sim
```

기본 워크스페이스는 `~/scout2map_ws`이며 설치 후 다음 환경 파일이 생성됩니다.

```bash
source ~/scout2map_env.sh
```

다른 위치를 사용하려면 `--workspace /path/to/workspace`를 지정합니다. 패키지만
설치하고 빌드를 생략하려면 `--no-build`를 사용합니다. `--no-build`는 이미
workspace와 overlay가 준비된 개발 환경에서만 사용하며, 신규 설치의 첫 실행에는
사용하지 않습니다.

라즈베리파이 5에서 빌드 중 스왑이 발생하면 `--parallel-workers 2`로 병렬도를
낮춥니다. `onboard` 프로파일은 udev 규칙을 함께 설치하며, 설치 후 재부팅해야
`dialout` 그룹이 적용됩니다.

설치 옵션과 패키지 목록의 자세한 설명은
[라즈베리파이 5 설치](scripts/raspberry_pi/README.md)를 참고하십시오.

### 수동 개발 빌드

설치 스크립트 없이 기존 Jazzy 환경에서 빌드할 때는 다음 순서를 사용합니다.

```bash
mkdir -p ~/scout2map_ws/src
ln -s "$PWD/src/s2m_bringup" ~/scout2map_ws/src/s2m_bringup
ln -s "$PWD/src/scout_gas" ~/scout2map_ws/src/scout_gas
vcs import ~/scout2map_ws/src < dependencies.repos

source /opt/ros/jazzy/setup.bash
rosdep install --from-paths ~/scout2map_ws/src --ignore-src -r -y \
  --rosdistro jazzy
cd ~/scout2map_ws
colcon build --symlink-install
source install/setup.bash
```

### 실차 실행

URDF, MCU 브리지, LiDAR, SLAM을 한 번에 시작하는 launch를 제공합니다.

```bash
ros2 launch s2m_bringup s2m_slam_real.launch.py
```

계층은 다음 순서로 올라가며, 각 계층은 앞 계층이 발행하는 TF에 의존합니다.

1. `robot_state_publisher` — `base_link -> lidar_link`, `imu_link`, 바퀴 링크
2. `s2m_onboard_bridge` — `odom -> base_link`, `sensor_fusion`, `range_link`
3. `sllidar_ros2` — `lidar_link` 기준 `/scan`
4. `slam_toolbox` — `map -> odom`
5. Nav2 — 위 전부를 소비

Nav2는 기본적으로 꺼져 있습니다. 지도와 TF가 안정된 것을 확인한 뒤
`use_nav2:=true`로 다시 실행합니다.

| launch 인자 | 기본값 | 설명 |
|---|---|---|
| `use_bridges` | `true` | MCU 브리지 실행 |
| `use_lidar` | `true` | RPLiDAR C1 드라이버 실행 |
| `use_slam` | `true` | slam_toolbox 실행 |
| `use_nav2` | `false` | Nav2 실행 |
| `use_event_engine` | `false` | `/events` 이벤트 엔진 실행 |
| `use_rviz` | `false` | RViz 실행 |
| `lidar_port` | `/dev/scout2map_lidar` | udev 규칙 미설치 시 `/dev/ttyUSB0` |
| `lidar_frame` | `lidar_link` | URDF 링크 이름과 반드시 일치해야 함 |
| `slam_params` | `config/slam_toolbox_real.yaml` | 실차 전용 파라미터 |

### 실차 자동 복귀와 안전 게이트

실차 mission에서는 Nav2나 teleop가 주행 브리지의 `/cmd_vel`을 직접 발행하지 않도록
다음 launch를 사용합니다. 시작 시 게이트는 차단 상태이며, 정상 heartbeat, 주행 링크,
TF를 확인한 뒤 출발점을 저장하고 명시적으로 무장해야 합니다.

```bash
ros2 launch s2m_bringup s2m_return_home_real.launch.py \
  map_id:=mapping_20260818 use_rviz:=true
```

```bash
ros2 service call /return_home/capture_start std_srvs/srv/Trigger "{}"
ros2 service call /return_home/arm std_srvs/srv/SetBool "{data: true}"
ros2 topic echo /return_home/status
```

teleop도 안전 게이트 입력으로 remap합니다. 정확한 표준 토픽 이름은 `/cmd_vel`이며
`/cmd_val`은 존재하지 않습니다.

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -r cmd_vel:=/return_home/cmd_vel_input
```

브리지 단독 바퀴 띄움 시험에서는 `/cmd_vel` 직접 발행을 사용할 수 있지만, 자동 복귀
mission에서는 직접 발행하면 게이트를 우회하므로 금지합니다.

실차 EKF(`robot_localization`)와 저장 지도 기반 AMCL bringup은 아직 제공하지
않습니다.

## 시뮬레이션 실행

```bash
source ~/scout2map_env.sh
ros2 launch s2m_bringup s2m_slam_sim.launch.py
```

실행 순서는 다음과 같습니다.

1. slip test world 시작
2. 실차 형상 로봇 spawn 및 Gazebo-ROS bridge 시작
3. SLAM Toolbox와 Nav2 시작
4. `use_rviz:=true`이면 RViz2 시작

초기 위치와 RViz 실행 여부를 바꿀 수 있습니다.

```bash
ros2 launch s2m_bringup s2m_slam_sim.launch.py \
  x_pose:=1.0 y_pose:=0.5 use_rviz:=false
```

WSL, SSH 또는 CI처럼 GUI가 없는 환경에서는 서버 모드로 실행합니다.

```bash
ros2 launch s2m_bringup s2m_slam_sim.launch.py \
  headless:=true use_rviz:=false
```

시뮬레이션 시작 지연은 프로세스 준비 시간을 보장하는 readiness check가 아니므로
느린 장비에서는 spawn 또는 Nav2 시작 시각을 추가 조정해야 할 수 있습니다.

## 자동 복귀 시뮬레이션

`s2m_return_home_sim.launch.py`는 SLAM/Nav2, fault injector와 단일 `cmd_vel`
안전 게이트를 함께 시작합니다.

```bash
ros2 launch s2m_bringup s2m_return_home_sim.launch.py
```

headless 실행은 다음과 같습니다.

```bash
ros2 launch s2m_bringup s2m_return_home_sim.launch.py \
  headless:=true use_rviz:=false
```

관제 heartbeat 단절을 주입합니다.

```bash
ros2 service call /sim_faults/set_network std_srvs/srv/SetBool "{data: false}"
```

정상 조건에서는 저장한 시작 좌표로 Nav2 복귀를 수행합니다. 주행 링크 단절은
자동 복귀 대상이 아니며 안전 정지로 전이합니다.

```bash
ros2 service call /sim_faults/set_drive_link std_srvs/srv/SetBool "{data: false}"
ros2 topic echo /return_home/status
```

2026-08-13 WSL/Jazzy/Gazebo 환경에서 관제 heartbeat 단절 후 `ARRIVED`까지 복귀하고,
주행 링크 단절 시 `SAFE_STOP`으로 전이하는 것을 확인했습니다. 이는 시뮬레이션 결과이며
실차 모터 차단과 STM32 watchdog 검증을 대체하지 않습니다.

상세 상태 전이, 초기화, TF fault, rosbag 기록 절차는
[시뮬레이션 검증 가이드](docs/integration/simulation-validation-guide.md)를
따릅니다. 현재 launch는 Gazebo 검증용이며 실제 UGV에 연결하기 전에
[실기기 통합 시험](docs/integration/real-hardware-validation.md)의 활성화 조건을
모두 충족해야 합니다.

## 가스 위험 지도 실행

시뮬레이션과 가스 센서 노드를 함께 실행합니다.

```bash
ros2 launch scout_gas sim_with_gas.launch.py
```

이미 시뮬레이션이 실행 중이면 가스 노드만 시작할 수 있습니다.

```bash
ros2 launch scout_gas gas_demo.launch.py
```

기본 출력은 `~/scout2map_data/maps`에 저장됩니다.

- `sim_gas_hex.json`: 육각 셀별 최대 농도와 임계값 이벤트
- `sim_map.pgm`, `sim_map.yaml`: 가장 최근 occupancy map

출력 위치는 `SCOUT2MAP_DATA_DIR` 또는 launch의 `output_path`로 변경합니다. 가스 농도
모델은 기능 검증용 가우시안 모델이며 실제 센서 보정값이나 물리 확산 모델로 사용하면
안 됩니다.

## MCU 브리지 실행과 확인

두 MCU 모두 재연결 후에도 유지되는 udev 장치명 `/dev/scout2map_pico`,
`/dev/scout2map_drive` 사용을 권장합니다. 장치명 생성 절차는
[udev 안내](scripts/raspberry_pi/udev/README.md)를 따릅니다.

```bash
source ~/scout2map_env.sh
ros2 launch s2m_bringup s2m_onboard_bridge.launch.py

./scripts/raspberry_pi/check_mcu_interfaces.sh \
  --sensor-device /dev/scout2map_pico \
  --motor-device /dev/scout2map_drive \
  --require-sensor --require-motor
```

`s2m_onboard_bridge.launch.py`는 세 가지를 함께 처리합니다.

- `scout2map_bridge`의 `sensor_bridge`와 `drive_bridge`를 시작합니다.
- `drive/odom`과 `drive/imu`를 이 저장소의 Nav2/SLAM 설정이 읽는 `/odom`,
  `/imu/data`로 remap합니다.
- URDF에 링크가 없는 `sensor_fusion`, `range_link` 프레임의 static TF를
  발행합니다.
- `drive_link_adapter`를 실행해 `DriveStatus`를 자동 복귀 정책이 구독하는
  `/drive/link_ok`(`std_msgs/msg/Bool`)로 변환합니다.

검사에서 확인하는 주요 토픽은 다음과 같습니다.

| 토픽 | 타입 | 발행 주체 |
|---|---|---|
| `/sensors/env_snapshot` | `scout2map_msgs/msg/EnvSnapshot` | `sensor_bridge` |
| `/sensors/status` | `scout2map_msgs/msg/SensorStatus` | `sensor_bridge` |
| `/odom` | `nav_msgs/msg/Odometry` | `drive_bridge` (remap) |
| `/imu/data` | `sensor_msgs/msg/Imu` | `drive_bridge` (remap) |
| `/drive/status` | `scout2map_msgs/msg/DriveStatus` | `drive_bridge` |
| `/drive/link_ok` | `std_msgs/msg/Bool` | `drive_link_adapter` |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Nav2 또는 조종 노드 |
| `/events` | `std_msgs/msg/String` | `scout2map_event` (선택) |

전체 계약과 V1.0.0 대비 변경 이력은
[MCU 브리지 인터페이스 계약](docs/integration/bridge-interface-contract.md)에
정리되어 있습니다. 주행 링크가 끊긴 상태에서 자동 복귀를 시도하지 말고 watchdog
안전 정지를 우선해야 합니다.

최신 브리지는 `skid_factor` 보정을 요구합니다. 실차 바닥에서 양방향 제자리 회전 후
다음 명령으로 값을 측정하고 `drive_bridge.yaml`에 반영하기 전에는 Event Engine의
`enable_drive_events`를 `false`로 유지합니다.

```bash
ros2 run scout2map_bridge skid_calib
```

static TF의 기본 오프셋은 측정값이 아닙니다. 실차에서 측정한 뒤 launch 인자로
교체하거나 `s2m_description` xacro에 링크를 추가하십시오.

## 설치 상태 확인

```bash
./scripts/raspberry_pi/check_compatibility.sh \
  --profile onboard \
  --workspace ~/scout2map_ws
```

Gazebo 환경이면 `--profile sim`을 사용합니다. 센서가 연결되지 않은 상태의
`/dev/tty*`, `/dev/video*`, `/dev/i2c-*` 경고는 정상일 수
있지만 ROS 패키지나 workspace overlay의 `FAIL`은 해결해야 합니다.

## 개발 검사

```bash
python3 tools/static_check.py
bash -n scripts/raspberry_pi/*.sh
```

정적 검사는 Python launch 구문, package XML, YAML, 문서 링크와 오래된 runtime 참조를
검사합니다. 실제 ROS 노드 실행, TF, Gazebo 동역학과 UGV 안전성까지 증명하지는 않습니다.

## 주의사항

- `nav2_lowspec.yaml`의 속도·가속도·goal tolerance는 초기 시뮬레이션 값입니다. 실차
  주행 전에 차체 질량, 제동거리와 모터 응답에 맞춰 낮은 속도부터 다시 조정하십시오.
- `robot_radius: 0.22`는 보수적인 원형 footprint입니다. 장착물까지 포함한 실제 외곽을
  측정한 뒤 polygon footprint 사용 여부를 결정하십시오.
- 센서 snapshot의 header 시간은 개별 센서 취득 시각과 다를 수 있습니다. 지도 이벤트는
  관련 센서의 `age_s` 또는 센서별 timestamp를 사용해야 합니다.
- 관제망 단절과 SBC-주행 MCU 링크 단절을 구분하십시오. 전자는 조건부 복귀가 가능하지만
  후자는 즉시 안전 정지 대상입니다.
- `/drive/link_ok`는 현재 MCU telemetry freshness와 fault 상태를 나타냅니다. CRC 오류율과
  PING/PONG 왕복 상태까지 반영하는 완전한 링크 품질 지표는 아직 아닙니다.
- 실차 첫 시험은 바퀴를 띄우고 물리 비상정지와 전류 제한 전원을 준비한 상태에서
  수행하십시오.
- 시뮬레이션 launch와 `s2m_onboard_bridge.launch.py`를 동시에 실행하지 마십시오.
  `/odom`, `/imu/data`, `/cmd_vel`과 `odom -> base_link` TF가 모두 충돌합니다.
- `robot_localization`을 도입하면 `drive_bridge`의 `publish_tf`를 `false`로 바꾸어
  `odom -> base_link` 발행 주체를 하나로 유지하십시오.

구현 상태와 실차 검증 순서는 [통합 문서](docs/integration/README.md)에 정리되어 있습니다.
이번 통합 변경은 [릴리스 노트](RELEASE_NOTES.md)에서 확인할 수 있습니다.
