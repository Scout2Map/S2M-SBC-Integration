# 패키지 인벤토리

기준 환경은 Ubuntu 24.04 LTS, ROS 2 Jazzy다. 로봇은 라즈베리파이 5(arm64),
개발용 노트북은 amd64다.

설치 목록은 `manifests/*.txt`, 소스 의존성은 루트 `dependencies.repos`가 관리한다.
이 문서는 그 두 곳의 요약이며, 값이 어긋나면 원본을 따른다.

## apt 패키지

| 매니페스트 | 시점 | 내용 |
|---|---|---|
| `apt-base.txt` | ROS 저장소 등록 전 | 로케일, curl, git, 빌드 도구, `python3-serial` |
| `ros-tools.txt` | ROS 저장소 등록 후 | `ros-dev-tools`, `rosdep`, `colcon`, `vcstool` |
| `ros-onboard.txt` | 두 프로파일 공통 | 아래 표 참조 |
| `ros-sim.txt` | `sim` 프로파일만 | `ros-jazzy-desktop`, RViz, `ros_gz_sim`, `ros_gz_bridge` |
| `ros-vision.txt` | Vision 환경 구성 시 | 카메라, `vision_msgs`, OpenCV와 image transport |

### `ros-onboard.txt`의 구성

| 패키지 | 사용처 |
|---|---|
| `ros-base` | headless ROS 런타임 |
| `navigation2`, `nav2-bringup` | `s2m_slam_real.launch.py`의 `use_nav2:=true` |
| `slam-toolbox` | 실시간 2D 매핑, `map -> odom` 발행 |
| `robot-state-publisher`, `joint-state-publisher`, `xacro` | URDF에서 `base_link -> lidar_link` 등 TF 생성 |
| `tf2-tools`, `tf2-ros` | `tf2_echo`, `view_frames`, static transform publisher |
| `teleop-twist-keyboard` | 수동 주행 시험 |
| `rosbag2`, `rosbag2-storage-mcap` | 재현 시험과 성능 분석 |

모든 항목은 `s2m_bringup`의 launch 파일이 실제로 사용한다. 사용하는 노드가 생기기
전까지 패키지를 추가하지 않는다.

## 소스 패키지

`dependencies.repos`가 커밋 단위로 고정한다.

| 저장소 | 패키지 | 용도 |
|---|---|---|
| `S2M-Hardware` | `s2m_description` | 실차 xacro, Gazebo slip world |
| `S2M-MCU-BridgeNode` | `scout2map_bridge`, `scout2map_msgs` | Pico/STM32 USB CDC 브리지와 메시지 정의 |
| `S2M-Event-Engine` | `scout2map_event` | 임계값 이벤트 판별과 지도 좌표 결합 |
| `sllidar_ros2` | `sllidar_ros2` | RPLiDAR C1 드라이버 |
| `m-explore-ros2` | `explore_lite`, `explore_lite_msgs`, `multirobot_map_merge`(미사용) | 프론티어 자율 탐색, `use_exploration:=true` |

이 저장소 자체가 제공하는 패키지는 `s2m_bringup`, `scout_gas`, `scout_vision`이며 워크스페이스에
심볼릭 링크로 연결된다.

## 설치하지 않는 것

| 항목 | 이유 |
|---|---|
| Micro-ROS | MCU 연결은 USB CDC 브리지를 사용한다 |
| ONNX Runtime 전역 설치 | 기본 추론은 OpenCV DNN을 쓰며 비교 시험용 Runtime은 전용 venv에만 설치한다 |
| `robot_localization` | 실차 EKF가 아직 구성되지 않았다. 도입 시 추가한다 |
| Gazebo (`onboard`) | 로봇에서 시뮬레이터를 실행하지 않는다 |

`robot_localization`을 도입하면 `drive_bridge`의 `publish_tf`를 `false`로 바꾸어
`odom -> base_link` 발행 주체를 하나로 유지해야 한다. 이때 필요한 패키지 목록은
`manifests/reference/ros-slam-future-ekf.txt`에 참고용으로 남아 있다 (install.sh는
이 파일을 읽지 않는다).

## 완료 판정

```bash
./scripts/raspberry_pi/check_compatibility.sh --profile onboard
```

필수 항목은 Ubuntu 24.04, ROS 2 Jazzy, 워크스페이스 빌드 산출물, 그리고
`s2m_bringup`, `s2m_description`, `scout_gas`, `scout_vision`, `scout2map_bridge`,
`scout2map_msgs`, `scout2map_event`, `slam_toolbox`, `nav2_bringup`,
`explore_lite`이다.

`onboard`에서는 세 장치 심볼릭 링크와 `dialout` 그룹 소속도 함께 확인한다.
