# S2M SBC Integration

Scout2Map UGV의 Raspberry Pi 5 소프트웨어 통합 저장소입니다. ROS 2 Jazzy
bringup, SLAM/Nav2 설정, 가스 위험 지도 시뮬레이션, 설치·점검 도구와 통합 검증
문서를 관리합니다.

## 저장소 책임

| 영역 | 이 저장소의 역할 |
|---|---|
| SBC 환경 | Ubuntu 24.04/ROS 2 Jazzy 설치와 호환성 검사 |
| 시뮬레이션 | 실차 `s2m_description` 모델, slip world, SLAM Toolbox, Nav2 연결 |
| 센서 연동 | Pico USB CDC 브리지 패키지 가져오기와 ROS 토픽 검사 |
| 데이터 | `map -> base_link` 기준 가스 위험 지도 시뮬레이션 |
| 검증 | 회의 과제 상태, 실차 SLAM/Nav2 및 자동 복귀 시험 계획 |

펌웨어 C 코드와 STM32 모터 제어는
[S2M-FW-DrivingControl](https://github.com/Scout2Map/S2M-FW-DrivingControl),
URDF/Xacro와 Gazebo 자산은
[S2M-Hardware](https://github.com/Scout2Map/S2M-Hardware), Pico 센서 브리지는
[S2M-MCU_Bridge_Node](https://github.com/Scout2Map/S2M-MCU_Bridge_Node)가 소유합니다.
두 ROS 의존 저장소는 [`dependencies.repos`](dependencies.repos)에 검토한 커밋으로
고정했습니다.

## 빠른 시작

```bash
git clone https://github.com/Scout2Map/S2M-SBC-Integration.git
cd S2M-SBC-Integration
chmod +x scripts/raspberry_pi/*.sh

# Raspberry Pi 실차 환경
./scripts/raspberry_pi/install.sh --profile onboard --with-rplidar

# Ubuntu 24.04 개발 PC의 Gazebo 환경
./scripts/raspberry_pi/install.sh --profile sim
source ~/scout2map_env.sh
ros2 launch s2m_bringup s2m_slam_sim.launch.py
```

가스 지도 노드까지 함께 실행하려면 다음 launch를 사용합니다.

```bash
ros2 launch scout_gas sim_with_gas.launch.py
```

설치 절차와 옵션은 [Raspberry Pi 안내](scripts/raspberry_pi/README.md), 시험이 필요한
항목은 [통합 문서](docs/integration/README.md)를 참고합니다.

## 현재 검증 범위

- Python launch 구문, XML/YAML 파싱, 셸 구문은 저장소에서 정적으로 검사합니다.
- `S2M-Hardware`의 실차 모델로 TurtleBot3/waffle 의존성을 제거했습니다.
- Pico 센서 브리지는 현재 USB CDC JSON-lines 구현과 토픽 계약을 따릅니다.
- STM32 drive bridge, Gazebo 동역학, 실제 UGV 주행·SLAM·복귀 시험은 아직 필요합니다.

완료되지 않은 실기 항목을 소스 존재만으로 완료 처리하지 않습니다.
