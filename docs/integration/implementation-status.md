# 구현 상태

## 소스 구현 완료

| 기능 | 구현 내용 | 주요 위치 |
|---|---|---|
| SBC 설치 | Ubuntu 24.04, ROS 2 Jazzy, SLAM/Nav2, 선택형 vision/simulation 설치 | `scripts/raspberry_pi/install.sh` |
| 호환성 검사 | OS·아키텍처·메모리·저장공간·ROS 패키지·USB 장치 검사 | `scripts/raspberry_pi/check_compatibility.sh` |
| 센서 인터페이스 | Pico USB CDC 장치와 snapshot/status 토픽 검사 | `scripts/raspberry_pi/check_mcu_interfaces.sh` |
| UGV 시뮬레이션 | 실차 `base_link` 모델, slip world, SLAM Toolbox, Nav2 연결 | `src/s2m_bringup` |
| 가스 위험 지도 | 선택성 센서, 가우시안 농도장, 육각 지도, 이벤트·map 저장 | `src/scout_gas` |
| 자동 검사 | Python/XML/YAML/Markdown/셸 구문 검사 | `tools/static_check.py`, `.github/workflows` |

## 실행 검증이 필요한 항목

| 항목 | 필요한 환경 | 완료 기준 |
|---|---|---|
| 전체 workspace 빌드 | Ubuntu 24.04 + ROS 2 Jazzy | 의존 패키지를 포함한 `colcon build` 성공 |
| Gazebo spawn | Gazebo Harmonic | world, robot, `/clock`, `/scan`, `/odom`, `/tf` 정상 |
| slip world | Gazebo Harmonic | 요철/마찰 구간 통과 시 odometry·IMU 변화 기록 |
| 실차 SLAM | UGV + RPLIDAR + odometry | 반복 경로 지도·TF 안정성과 loop closure 기록 |
| Nav2 주행 | UGV | 충돌 없이 동일 목표 세트 10회 중 9회 이상 도달 |
| 주행 MCU 링크 | UGV + drive bridge | `/cmd_vel` 변환, `/wheel/odom`, watchdog 정지 확인 |
| 지도 이벤트 좌표 | UGV 또는 rosbag | 센서 timestamp 기반 TF 조회와 위치 오차 측정 |
| 자동 복귀 | Gazebo 후 UGV | 관제망 단절만 조건부 복귀, MCU 링크 단절은 안전 정지 |

## 안전 동작 원칙

1. 관제 heartbeat 손실과 주행 MCU USB CDC 손실을 서로 다른 장애로 처리합니다.
2. 주행 MCU, localization 또는 TF가 비정상이면 복귀 goal을 만들지 않습니다.
3. 실차 파라미터는 시뮬레이션 값 그대로 사용하지 않고 저속 시험부터 조정합니다.
4. 수행하지 않은 실행 시험은 소스가 존재하더라도 완료로 표시하지 않습니다.
