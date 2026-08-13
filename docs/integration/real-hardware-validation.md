# 실기기 통합 시험 항목

## 1. 현재 통합 기준

- Raspberry Pi 5 8GB와 NVMe SSD를 SBC로 사용한다.
- RPLiDAR C1은 scan, BNO055는 imu/data를 제공해야 한다.
- 센서 Pico는 USB CDC 기반 mcu_bridge를 사용한다.
- STM32 주행 제어 펌웨어는 엔코더 폐루프, 오도메트리, BTS7960 출력,
  300 ms 명령 timeout과 약 400 ms watchdog을 구현한 상태다.
- STM32 USB CDC 바이너리 프로토콜과 SBC 주행 브리지는 아직 통합 완료로
  간주하면 안 된다.

## 2. 전원과 배선

1. 모터 전원과 SBC 5 V 전원을 분리 측정하고 공통 GND를 확인한다.
2. 정지, 무부하 회전, 급가감속에서 Raspberry Pi 5 저전압 경고를 확인한다.
3. UBEC 출력 전압과 최대 부하 시 강하를 기록한다.
4. USB 장치가 재연결되어도 고정된 udev 이름을 사용하는지 확인한다.
5. 비상 정지 시 모터 출력이 하드웨어 수준에서 차단되는지 확인한다.

## 3. MCU와 모터 단독 시험

DrivingControl 저장소:

    make test
    make
    make flash

바퀴를 지면에서 띄운 상태로 좌우 방향, 엔코더 부호, 속도 제한, 명령 timeout을
검증한다. 이후 저속 직진과 제자리 회전으로 wheel radius, wheel separation,
encoder counts 값을 보정한다.

## 4. ROS 토픽 계약

| 데이터 | 권장 토픽 | 프레임 또는 단위 |
|---|---|---|
| LiDAR | /scan | lidar_link, m |
| IMU | /imu/data | imu_link, SI |
| 휠 오도메트리 | /wheel/odom | odom to base_link |
| 융합 오도메트리 | /odom | odom to base_link |
| 모터 명령 | /cmd_vel | m/s, rad/s |
| 관제 heartbeat | /control/heartbeat | SBC 단절 판정 |
| 주행 링크 상태 | /drive/link_ok | STM32 연결 상태 |
| 센서 브리지 상태 | /bridge/status | Pico 상태 전용 |

bridge/status를 주행 링크 상태로 재사용하면 안 된다. STM32 브리지는 수신 시각,
CRC 오류, heartbeat 또는 응답 timeout을 종합해 drive/link_ok를 발행해야 한다.

현재 Hardware xacro는 lidar_link와 imu_link를 정의한다. 실제 RPLiDAR 또는 센서
launch의 frame_id를 동일하게 맞추고 Gazebo 센서의 프레임도 명시적으로 검증한다.

## 5. TF와 위치 추정

    ros2 run tf2_ros tf2_echo odom base_link
    ros2 run tf2_ros tf2_echo base_link lidar_link
    ros2 run tf2_ros tf2_echo base_link imu_link

SLAM 단계에서는 map to odom을 slam_toolbox가, odom to base_link를 오도메트리
계층이 한 번만 발행해야 한다. 동일 TF를 두 노드가 중복 발행하지 않는지 확인한다.

## 6. SLAM과 Nav2 실차 시험

1. 수동 저속 주행으로 scan과 odom 시간 동기, 방향, 축을 확인한다.
2. 직선과 사각 경로를 주행해 지도 폐곡선 오차를 기록한다.
3. 지도를 저장하고 AMCL 위치 추정에서 초기 자세와 재지역화를 확인한다.
4. Nav2 목표 수행 시 장애물 정지, 경로 재계획, 제동 거리를 기록한다.
5. 저마찰 바닥에서 휠 오도메트리와 IMU yaw 차이를 비교해 슬립 기준을 정한다.

현재 저장소에는 실차 EKF, STM32 구동 브리지, AMCL 기반 onboard bringup이
완성되어 있지 않다. 이 세 계층을 구현하고 토픽 remap과 TF 소유권을 확정해야
실차 SLAM/Nav2 완료로 판단할 수 있다.

## 7. 자동 복귀 활성화 조건

실차 자동 복귀는 다음 항목이 모두 완료된 후 활성화한다.

- SBC에서 STM32로 가는 단일 최종 cmd_vel 게이트가 있다.
- drive/link_ok가 실제 왕복 통신 상태를 반영한다.
- 저장 지도와 AMCL에서 시작 좌표를 안정적으로 복원한다.
- 출발점까지 경로가 없거나 진행이 멈추면 제한 시간 안에 정지한다.
- 관제망 단절과 SBC 자체 장애를 구분한다.
- 물리 비상 정지와 MCU watchdog이 자동 복귀보다 높은 우선순위를 갖는다.
