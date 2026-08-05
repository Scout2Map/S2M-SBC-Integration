# Scout2Map package inventory

기준 환경은 Raspberry Pi 5, Ubuntu 24.04 LTS arm64, ROS 2 Jazzy입니다. 실제 설치
목록은 `manifests/*.txt`, 소스 의존성은 루트 `dependencies.repos`가 관리합니다.

## 기본 SLAM·자율주행

| 구분 | 패키지 | 용도 |
|---|---|---|
| ROS 2 | `ros-jazzy-ros-base` | headless ROS 런타임 |
| Nav2 | `navigation2`, `nav2-bringup` | planner/controller/lifecycle |
| SLAM | `slam-toolbox` | 2D LiDAR 지도와 pose graph |
| 센서 융합 | `robot-localization`, `imu-tools` | wheel odom/IMU EKF와 점검 |
| TF/URDF | `tf2-tools`, `robot-state-publisher`, `xacro` | 실차 프레임 구성 |
| 기록 | `rosbag2`, MCAP | 재현 시험과 성능 분석 |

RPLIDAR C1 드라이버는 `--with-rplidar` 사용 시 Slamtec의 `sllidar_ros2`를 소스로
가져옵니다.

## 저장소 소스 의존성

| 저장소 | 패키지/용도 |
|---|---|
| S2M-Hardware | `s2m_description`, 실차 xacro와 Gazebo slip world |
| S2M-MCU_Bridge_Node | `scout2map_bridge`, `scout2map_msgs`, Pico USB CDC |

검토되지 않은 upstream 변경으로 설치가 달라지지 않도록 커밋 SHA를 고정했습니다.

## 선택 설치

| 목록/옵션 | 설치 조건 |
|---|---|
| `manifests/ros-sim.txt` | Gazebo Harmonic과 RViz 시험 |
| `--with-vision` | ROS 카메라 스택과 ONNX Runtime CPU 환경 |
| `--with-rplidar` | Slamtec ROS 2 드라이버 |

Micro-ROS는 2026-08-05 USB CDC 결정과 맞지 않아 포함하지 않습니다. STM32 drive
bridge는 아직 구현되지 않았으므로 센서 bridge가 모터 제어까지 담당한다고 가정하지
않습니다.

## 완료 판정

```bash
./scripts/raspberry_pi/check_compatibility.sh \
  --profile onboard --with-vision --workspace ~/scout2map_ws
```

필수 항목은 Jazzy 환경, `s2m_bringup`, `s2m_description`, `scout_gas`,
`scout2map_bridge`, `scout2map_msgs`, SLAM Toolbox/Nav2 패키지와 선택한 비전 환경입니다.
