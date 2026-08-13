# 시뮬레이션 검증 가이드

이 절차는 실차 형상, 요철·저마찰 지형, SLAM/Nav2, 통신 단절 자동 복귀를
동일한 기준으로 재현하기 위한 시험서다.

## 1. 사전 조건

- Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic을 사용한다.
- s2m_description과 s2m_bringup을 빌드하고 환경을 source 한다.
- 시뮬레이션 시간 사용 중에도 단절 판정은 steady clock으로 수행한다.
- 자동 복귀는 관제 네트워크 단절만 대상으로 한다.
- 주행 MCU 링크 또는 TF 이상은 복귀가 아니라 SAFE_STOP으로 전이한다.

## 2. 실차 형상과 지형 확인

GUI 환경:

    ros2 launch s2m_bringup s2m_slam_sim.launch.py use_rviz:=false

WSL 또는 GUI가 없는 환경:

    ros2 launch s2m_bringup s2m_slam_sim.launch.py headless:=true use_rviz:=false

확인 항목:

1. TurtleBot3가 아니라 Scout2Map xacro 형상이 생성된다.
2. 월드에 4 x 4 배열의 0.08 m 요철 구간이 보인다.
3. 일반 지면의 마찰계수는 0.8, 저마찰 구간은 0.05로 설정된다.
4. lidar_link, imu_link, base_link, wheel 프레임이 모델과 일치한다.
5. LiDAR가 인식할 수 있는 벽이나 랜드마크가 지도 작성 구간에 존재한다.

증빙은 전체 월드, 요철 통과, 저마찰 구간 진입 장면을 각각 캡처한다.

## 3. SLAM과 Nav2 확인

    ros2 launch s2m_bringup s2m_slam_sim.launch.py use_rviz:=true

WSL에서는 Gazebo와 RViz 창을 띄우지 않고도 동일한 서버 측 검증을 수행할 수 있다.

    ros2 launch s2m_bringup s2m_slam_sim.launch.py headless:=true use_rviz:=false

다른 터미널에서 다음을 확인한다.

    ros2 topic hz /clock
    ros2 topic hz /scan
    ros2 topic hz /odom
    ros2 topic hz /tf
    ros2 topic echo /joint_states --once
    ros2 run tf2_ros tf2_echo map base_link
    ros2 lifecycle get /controller_server
    ros2 lifecycle get /bt_navigator

RViz에서 LaserScan이 장애물과 일치하는지, 이동 중 map이 연속적으로 확장되는지,
Nav2 목표점을 주었을 때 경로가 생성되고 차체가 이동하는지 확인한다.

## 4. 자동 복귀 정상 시나리오

    ros2 launch s2m_bringup s2m_return_home_sim.launch.py

WSL 또는 CI에서는 다음과 같이 실행한다.

    ros2 launch s2m_bringup s2m_return_home_sim.launch.py headless:=true use_rviz:=false

상태 확인:

    ros2 topic echo /return_home/status

기본 설정은 시뮬레이션 시작 8초 뒤 현재 map 좌표를 출발점으로 저장하고 자동
무장한다. NORMAL 상태를 확인한 뒤 RViz의 Nav2 Goal로 출발점에서 충분히 떨어진
위치로 이동시킨다.

관제 네트워크 단절을 주입한다.

    ros2 service call /sim_faults/set_network std_srvs/srv/SetBool "{data: false}"

기대 결과:

1. NORMAL에서 RETURN_REQUESTED로 전이한다.
2. Nav2 NavigateToPose 목표가 저장된 출발 좌표로 전송된다.
3. RETURNING 중 distance_remaining이 감소한다.
4. 허용 오차 안에 도착하면 ARRIVED가 된다.
5. 이동 명령은 안전 게이트를 통과한 하나의 최종 cmd_vel 발행자로 제한된다.

시험 초기화:

    ros2 service call /sim_faults/reset std_srvs/srv/Trigger "{}"
    ros2 service call /return_home/reset std_srvs/srv/Trigger "{}"

수동 출발점 저장과 무장은 다음과 같다.

    ros2 service call /return_home/capture_start std_srvs/srv/Trigger "{}"
    ros2 service call /return_home/arm std_srvs/srv/SetBool "{data: true}"

## 5. 안전 정지 시나리오

주행 링크 단절을 주입한다.

    ros2 service call /sim_faults/set_drive_link std_srvs/srv/SetBool "{data: false}"

기대 결과는 SAFE_STOP이다. motion_inhibit가 true가 되고 최종 cmd_vel은 0으로
유지되어야 한다. 이 조건에서는 자동 복귀를 시도하면 안 된다.

    ros2 topic echo /return_home/status
    ros2 topic echo /return_home/motion_inhibit

TF 이상 시험은 robot_state_publisher 또는 odometry 제공 계층을 중지해
map to base_link 변환이 timeout을 넘도록 만든다. 기대 결과 역시 SAFE_STOP이다.

return_home 노드 종료 시험에서는 2.5초 안에 안전 게이트가 watchdog timeout을
감지하고 최종 cmd_vel을 0으로 고정해야 한다. 다른 노드가 /cmd_vel에 직접
발행하면 게이트를 우회하므로 시험 중 publisher 수를 확인한다.

    ros2 topic info /cmd_vel --verbose

## 6. 실패 판정

다음 중 하나라도 발생하면 실패다.

- 네트워크 단절 후 출발점이 아닌 임의 좌표로 이동한다.
- 주행 링크 또는 TF 단절 상태에서 복귀를 계속한다.
- Nav2 출력과 안전 정지 출력이 동시에 최종 cmd_vel을 발행한다.
- Nav2 또는 return_home 노드가 종료됐는데 모터 명령이 계속 전달된다.
- 복귀 거리 감소가 progress timeout 동안 관측되지 않는데 계속 주행한다.
- return timeout 뒤에도 정지하지 않는다.

## 7. 2026-08-13 실행 검증 결과

WSL Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic에서 다음 결과를 확인했다.

| 항목 | 결과 |
|---|---|
| s2m_description, s2m_bringup 빌드 | 성공 |
| return_home 정책 단위 시험 | 5개 모두 통과 |
| heightmap 월드 로드와 실차 형상 spawn | 성공 |
| SLAM Toolbox와 Nav2 lifecycle 활성화 | 성공 |
| 최종 /cmd_vel 발행자 | cmd_vel_safety_gate 1개 |
| 관제 heartbeat 단절 자동 복귀 | NORMAL에서 RETURNING을 거쳐 ARRIVED 확인 |
| 주행 링크 단절 | `safe stop: drive link lost or stale` 로그 확인 |

자동 복귀 시험에서는 시작점에서 이동한 뒤 관제 heartbeat를 중단했다. Nav2가 저장된
시작점으로 복귀했으며 최종 상태는 ARRIVED, 최종 odometry 오차는 약 0.325 m였다.
이는 현재 Nav2 goal tolerance 이내의 결과다. 주행 링크 단절은 SAFE_STOP 전이를
확인했으며, 실제 모터 차단은 STM32 브리지와 실차 watchdog을 연결한 뒤 다시 검증한다.

TF 단절, 무진행, 복귀 제한 시간, 저마찰 구간의 정량 성능 시험은 아직 남아 있다.

## 8. 기록 자료

    ros2 bag record /tf /tf_static /odom /scan /cmd_vel /return_home/status /return_home/start_pose /return_home/motion_inhibit

각 시험에는 월드 캡처, RViz 지도와 경로 캡처, 상태 토픽 로그, rosbag을 남긴다.
headless 시험으로 동작을 먼저 확인한 뒤 최종 보고서에는 GUI 캡처와 정량 표를 추가한다.
