# S2M SBC Integration

Raspberry Pi 5에서 Scout2Map UGV의 ROS 2 실행 환경을 설치하고, 실차 형상 기반
Gazebo 시뮬레이션과 SLAM/Nav2·가스 위험 지도 기능을 실행하기 위한 통합 프로젝트입니다.

## 구현된 기능

- Ubuntu 24.04와 ROS 2 Jazzy 설치 및 호환성 점검
- 실차 `base_link`·LiDAR·IMU 프레임을 사용하는 Gazebo bringup
- SLAM Toolbox와 Nav2의 저사양 시뮬레이션 설정
- 관제망 단절 시 Nav2 출발점 복귀와 주행 링크·TF 장애 안전 정지 시뮬레이션
- 선택성 가스 센서, 육각형 위험 지도, 이벤트 JSON과 occupancy map 저장
- Pico 센서 USB CDC 장치와 ROS 토픽 상태 점검
- RPLIDAR C1 드라이버 및 선택형 OpenCV/ONNX Runtime 설치
- Python/XML/YAML/Markdown/셸 정적 검사 자동화

## 폴더 구조

```text
S2M-SBC-Integration/
├── .github/workflows/
│   └── static-checks.yml          # 정적 검사 CI
├── docs/integration/
│   ├── implementation-status.md   # 구현·검증 상태
│   ├── map-marker-coordinate-design.md
│   ├── repository-baseline-2026-08-13.md
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
  --profile onboard \
  --with-rplidar
sudo reboot
```

카메라와 ONNX Runtime CPU 환경도 필요하면 `--with-vision`을 추가합니다.

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

현재 통합 launch는 Gazebo 시뮬레이션용입니다. 실차에서는 LiDAR, Pico bridge,
wheel odometry, IMU/EKF와 Nav2를 순서대로 구성해야 하며 이를 한 번에 시작하는 onboard
launch는 아직 제공하지 않습니다.

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

## Pico USB CDC 확인

Pico에는 재연결 후에도 유지되는 udev 장치명 `/dev/scout2map_pico` 사용을 권장합니다.
장치명 생성 절차는 [udev 안내](scripts/raspberry_pi/udev/README.md)를 따릅니다.

```bash
source ~/scout2map_env.sh
ros2 launch scout2map_bridge pico_bridge.launch.py

./scripts/raspberry_pi/check_mcu_interfaces.sh \
  --sensor-device /dev/scout2map_pico \
  --require-sensor
```

센서 검사에서 확인하는 주요 토픽은 다음과 같습니다.

| 토픽 | 타입 |
|---|---|
| `/sensors/env_snapshot` | `scout2map_msgs/msg/EnvSnapshot` |
| `/bridge/status` | `scout2map_msgs/msg/BridgeStatus` |

주행 MCU 연동이 준비된 환경에서는 `/dev/scout2map_drive`, `/cmd_vel`,
`/wheel/odom`을 연결한 뒤 `--require-motor`를 추가합니다. 주행 링크가 끊긴 상태에서
자동 복귀를 시도하지 말고 watchdog 안전 정지를 우선해야 합니다.

## 설치 상태 확인

```bash
./scripts/raspberry_pi/check_compatibility.sh \
  --profile onboard \
  --workspace ~/scout2map_ws
```

비전 옵션을 설치했다면 `--with-vision`, Gazebo 환경이면 `--profile sim`을 사용합니다.
센서가 연결되지 않은 상태의 `/dev/tty*`, `/dev/video*`, `/dev/i2c-*` 경고는 정상일 수
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
- 실차 첫 시험은 바퀴를 띄우고 물리 비상정지와 전류 제한 전원을 준비한 상태에서
  수행하십시오.

구현 상태와 실차 검증 순서는 [통합 문서](docs/integration/README.md)에 정리되어 있습니다.
