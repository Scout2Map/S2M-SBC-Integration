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

## 소스 패키지

| 구성 | 패키지/용도 |
|---|---|
| S2M-Hardware | `s2m_description`, 실차 xacro와 Gazebo slip world |
| S2M-MCU-BridgeNode | `scout2map_bridge`, `scout2map_msgs`, Pico/STM32 USB CDC |

## 선택 설치

| 목록/옵션 | 설치 조건 |
|---|---|
| `manifests/ros-sim.txt` | Gazebo Harmonic과 RViz 시험 |
| `--with-vision` | ROS 카메라 스택과 ONNX Runtime CPU 환경 |
| `--with-rplidar` | Slamtec ROS 2 드라이버 |

MCU 연결은 USB CDC bridge를 사용하므로 Micro-ROS는 기본 설치에 포함하지 않습니다.
주행 bridge가 준비되기 전에는 센서 bridge가 모터 제어까지 담당한다고 가정하지
않습니다.

## 완료 판정

```bash
./scripts/raspberry_pi/check_compatibility.sh \
  --profile onboard --with-vision --workspace ~/scout2map_ws
```

필수 항목은 Jazzy 환경, `s2m_bringup`, `s2m_description`, `scout_gas`,
`scout2map_bridge`, `scout2map_msgs`, SLAM Toolbox/Nav2 패키지와 선택한 비전 환경입니다.
