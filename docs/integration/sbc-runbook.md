# SBC 기능별 실행 절차

기준 브랜치: sbc-integration

이 문서는 Raspberry Pi 5와 개발 PC에서 Scout2Map SBC 저장소의 각 기능을
재현하는 절차를 정리한다. 명령은 Ubuntu 24.04와 ROS 2 Jazzy 기준이다.

## 1. 최초 설치

저장소를 내려받고 대상 브랜치를 선택한다.

    git clone https://github.com/Scout2Map/S2M-SBC-Integration.git
    cd S2M-SBC-Integration
    git switch sbc-integration

시뮬레이션 개발 PC:

    chmod +x scripts/raspberry_pi/*.sh
    ./scripts/raspberry_pi/install.sh --profile sim

Raspberry Pi 5 실기기:

    chmod +x scripts/raspberry_pi/*.sh
    ./scripts/raspberry_pi/install.sh \
      --profile onboard

RPLIDAR 패키지는 onboard profile에 포함된다. AI 비전 런타임은 설치 후
`scripts/raspberry_pi/create_vision_venv.sh onnx`로 별도 구성한다. 신규 설치의
첫 실행에는 --no-build를 사용하지 않는다.

매 터미널에서 환경을 불러온다.

    source ~/scout2map_env.sh

## 2. 소스 갱신과 빌드

저장소 checkout에서 의존성을 갱신한 뒤 workspace를 빌드한다.

    cd /path/to/S2M-SBC-Integration
    git pull --ff-only origin sbc-integration
    vcs import ~/scout2map_ws/src < dependencies.repos
    rosdep install --from-paths ~/scout2map_ws/src --ignore-src -r -y \
      --rosdistro jazzy
    cd ~/scout2map_ws
    colcon build --symlink-install
    source install/setup.bash

dependencies.repos는 재현 가능한 통합 기준점을 고정한다. 의존 저장소의 최신
커밋을 무조건 가져오지 말고, 변경 내용을 검토한 뒤 기준점을 갱신한다.

## 3. 기능별 실행

| 기능 | 실행 명령 | 핵심 확인 |
|---|---|---|
| 요철·슬립·SLAM/Nav2 | ros2 launch s2m_bringup s2m_slam_sim.launch.py | scan, odom, map, TF |
| headless 시뮬레이션 | ros2 launch s2m_bringup s2m_slam_sim.launch.py headless:=true use_rviz:=false | WSL 또는 CI 실행 |
| 자동 복귀 | ros2 launch s2m_bringup s2m_return_home_sim.launch.py | 상태 전이와 출발점 도착 |
| headless 자동 복귀 | ros2 launch s2m_bringup s2m_return_home_sim.launch.py headless:=true use_rviz:=false | WSL 고장 주입 검증 |
| 가스 위험 지도 | ros2 launch scout_gas sim_with_gas.launch.py | gas와 marker |
| 센서 가상 입력 | ros2 launch scout2map_bridge fake_sensors.launch.py | 센서 토픽 주기 |
| MCU 실입력 | ros2 launch s2m_bringup s2m_onboard_bridge.launch.py | 프레임 파싱, 토픽, static TF |
| 실차 안전 mission | ros2 launch s2m_bringup s2m_slam_real.launch.py use_nav2:=true use_return_home:=true map_id:=mapping_YYYYMMDD | Event Engine, 단일 cmd_vel 게이트, 자동 복귀 |

시뮬레이션의 상세 절차는 simulation-validation-guide.md를 따른다.

## 4. 지도 저장과 재사용

SLAM 중 occupancy map을 저장한다.

    mkdir -p ~/maps
    ros2 run nav2_map_server map_saver_cli -f ~/maps/scout2map

Slam Toolbox pose graph가 필요하면 serialize_map 서비스를 별도로 호출한다.

    ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph "{filename: /home/ubuntu/maps/scout2map_posegraph}"

생성된 yaml과 pgm 또는 pose graph 파일을 함께 보관한다. 지도 기반 자율주행에서는
저장 지도와 AMCL을 사용하고 map to odom, odom to base_link, base_link to lidar_link
프레임이 끊김 없이 이어지는지 먼저 확인한다.

## 5. 센서 브리지 점검

    ros2 topic list
    ros2 topic hz /imu/data
    ros2 topic echo /imu/data --once
    ros2 topic hz /sensors/env_snapshot
    ros2 topic echo /sensors/status --once
    ros2 topic echo /drive/status --once
    ros2 topic echo /drive/link_ok --once

sensors/status는 Pico 센서 브리지 상태이며 주행 제어 STM32의 링크 상태가 아니다.
주행 링크 판정은 drive/status를 drive_link_adapter가 해석해 발행하는
drive/link_ok를 사용한다. 두 토픽을 서로 대체해서는 안 된다.

자동 복귀 mission에서 teleop를 사용할 때에는 안전 게이트 입력으로 remap한다.
`/cmd_val`은 오타이며 실제 표준 토픽은 `/cmd_vel`이다.

    ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
      -r cmd_vel:=/return_home/cmd_vel_input

브리지 단독 바퀴 띄움 시험이 아닌데 `/cmd_vel` 발행자가 두 개 이상이면 시험을
중단하고 발행 주체를 정리한다.

    ros2 topic info /cmd_vel --verbose

토픽과 프레임의 전체 계약은 bridge-interface-contract.md를 따른다.

## 6. 정적 검사

    python3 tools/static_check.py

이 검사는 파일 구성과 launch 구문을 확인한다. Gazebo 동역학, Nav2 경로 수행,
실제 센서 정확도와 모터 안전성은 별도 시험으로 증명해야 한다.
