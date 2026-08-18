# 구현 상태

## 소스 구현 완료

| 기능 | 구현 내용 | 주요 위치 |
|---|---|---|
| SBC 설치 | Ubuntu 24.04, ROS 2 Jazzy, SLAM/Nav2, 선택형 vision/simulation 설치 | `scripts/raspberry_pi/install.sh` |
| 호환성 검사 | OS·아키텍처·메모리·저장공간·ROS 패키지·USB 장치 검사 | `scripts/raspberry_pi/check_compatibility.sh` |
| 센서 인터페이스 | Pico USB CDC 장치와 snapshot/status 토픽 검사 | `scripts/raspberry_pi/check_mcu_interfaces.sh` |
| UGV 시뮬레이션 | 실차 `base_link` 모델, slip world, SLAM Toolbox, Nav2 연결 | `src/s2m_bringup` |
| 자동 복귀 시뮬레이션 | Nav2 시작점 goal, fault injector, steady-clock watchdog, 단일 cmd_vel 안전 게이트 | `src/s2m_bringup` |
| 실차 안전 mission | Nav2/teleop 게이트 입력, drive link adapter, Event Engine, 수동 무장형 return_home launch | `s2m_return_home_real.launch.py` |
| 가스 위험 지도 | 선택성 센서, 가우시안 농도장, 육각 지도, 이벤트·map 저장 | `src/scout_gas` |
| 자동 검사 | Python/XML/YAML/Markdown/셸 구문 검사 | `tools/static_check.py`, `.github/workflows` |

## 2026-08-13 실행 검증 완료

| 항목 | 확인 결과 |
|---|---|
| ROS 2 workspace 빌드 | WSL Ubuntu 24.04/Jazzy에서 s2m_description과 s2m_bringup 빌드 성공 |
| Gazebo spawn | heightmap world, Scout2Map 형상, /clock, /scan, /odom, /tf 생성 확인 |
| SLAM/Nav2 | SLAM Toolbox와 Nav2 lifecycle 활성 상태 확인 |
| 자동 복귀 | heartbeat 단절 후 저장한 시작점으로 복귀하고 ARRIVED 확인 |
| 안전 정지 | drive link 단절 주입 후 SAFE_STOP 로그 확인 |
| 안전 게이트 | 최종 /cmd_vel 발행자가 cmd_vel_safety_gate 1개임을 확인 |
| 정책 단위 시험 | return_home 정책 시험 5개 통과 |

## 추가 실행 검증이 필요한 항목

| 항목 | 필요한 환경 | 완료 기준 |
|---|---|---|
| slip world | Gazebo Harmonic | 요철/마찰 구간 통과 시 odometry·IMU 변화 기록 |
| 실차 SLAM | UGV + RPLIDAR + odometry | 반복 경로 지도·TF 안정성과 loop closure 기록 |
| Nav2 주행 | UGV | 충돌 없이 동일 목표 세트 10회 중 9회 이상 도달 |
| 주행 MCU 링크 | UGV + drive bridge | `/cmd_vel` 변환, `/odom`, `/drive/link_ok`, watchdog 정지 확인 |
| 지도 이벤트 좌표 | UGV 또는 rosbag | 센서 timestamp 기반 TF 조회와 위치 오차 측정 |
| 자동 복귀 실차 | UGV | 관제망 단절 시 출발점 도착, MCU 링크·TF 단절 시 안전 정지 |
| Event Engine 실차 | UGV + rosbag | `/events` 좌표, 8종 debounce, map_id와 threshold 변경 확인 |
| 추가 고장 주입 | Gazebo | TF 단절, 무진행, 제한 시간 초과에서 SAFE_STOP 확인 |

## 안전 동작 원칙

1. 관제 heartbeat 손실과 주행 MCU USB CDC 손실을 서로 다른 장애로 처리한다.
2. 주행 MCU, localization 또는 TF가 비정상이면 복귀 goal을 만들지 않는다.
3. 실차 파라미터는 시뮬레이션 값 그대로 사용하지 않고 저속 시험부터 조정한다.
4. 수행하지 않은 실행 시험은 소스가 존재하더라도 완료로 표시하지 않는다.
