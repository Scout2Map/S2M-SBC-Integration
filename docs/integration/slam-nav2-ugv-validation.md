# SLAM 및 Nav2 실기기 검증 계획

## 1. 선행 조건

SLAM을 실행하기 전에 다음 데이터 흐름이 각각 단독으로 검증돼야 한다.

- `/scan`: RPLiDAR C1, `sensor_msgs/LaserScan`, 올바른 `frame_id`
- `/wheel/odom`: encoder 기반 wheel odometry
- `/imu/data`: BNO055, ENU와 SI 단위
- `/odometry/filtered`: wheel odom과 IMU를 융합한 EKF 출력
- TF: `map -> odom -> base_link -> rplidar_link/imu_link`
- `/cmd_vel`: 수동 주행과 timeout 정지

BNO055만으로 이동 거리를 계산하지 않는다. 병진 오도메트리에는 wheel encoder가 필요하다.

## 2. TF 소유권

| Transform | 발행 주체 |
|---|---|
| `map -> odom` | mapping 중 Slam Toolbox, navigation 중 AMCL |
| `odom -> base_link` | robot_localization EKF |
| `base_link -> sensor links` | robot_state_publisher |

다음 명령으로 중복 발행과 누락을 검사한다.

```bash
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link rplidar_link
ros2 run tf2_ros tf2_echo base_link imu_link
```

## 3. 실험 단계

### S1. 정지 시험

로봇을 60초 동안 정지하고 `/scan`, `/imu/data`, `/wheel/odom`, `/odometry/filtered`를 기록한다.

- encoder tick이 증가하지 않는다.
- filtered pose가 지속적으로 이동하거나 회전하지 않는다.
- LiDAR 벽이 RViz에서 흔들리거나 이중으로 벌어지지 않는다.
- IMU와 LiDAR frame 방향이 실제 장착 방향과 일치한다.

### S2. 직선과 제자리 회전

- 실측 1 m와 3 m 직선 주행 오차를 기록한다.
- 시계·반시계 방향 360도 회전 오차를 각각 기록한다.
- wheel radius, track width와 encoder scale을 조정한다.
- BNO055 yaw를 EKF에 넣기 전후 결과를 비교한다.

### S3. 작은 폐루프 SLAM

1. 저속으로 작은 사각 경로를 주행한다.
2. 코너와 출입구를 서로 다른 방향에서 재관측한다.
3. 출발점으로 돌아와 loop closure를 기다린다.
4. occupancy map과 serialized pose graph를 모두 저장한다.
5. 같은 경로를 3회 반복한다.

```bash
ros2 topic hz /scan
ros2 topic hz /map
ros2 run tf2_ros tf2_echo map odom
ros2 run nav2_map_server map_saver_cli -f ~/scout2map_data/maps/test_map
```

### S4. 지도 품질 비교

| 지표 | 측정 방법 |
|---|---|
| 축척 오차 | 실측 거리와 map pixel x resolution 비교 |
| 벽 중복 | 동일 벽이 두 줄로 표시된 최대 간격 |
| 직각 보존 | 실제 직각 코너의 지도 각도 |
| 폐루프 보정 | 출발점 복귀 전후 pose와 중복 벽 변화 |
| 반복 재현성 | 동일 경로 3개 지도의 주요 벽 overlay |
| 정지 안정성 | 정지 60초 pose drift |

wheel only, wheel+gyro z, wheel+검증된 orientation 설정을 같은 rosbag으로 비교한다. 설정 외의 입력을 동일하게 유지한다.

### N1. 저장 지도 위치 추정

- 저장한 map과 AMCL을 실행한다.
- RViz에서 초기 pose를 설정한다.
- 로봇을 손으로 이동하지 않고 localization이 안정되는지 확인한다.
- 제자리 회전 후 laser scan과 map 벽이 다시 정렬되는지 확인한다.

### N2. Nav2 반복 주행

1. 장애물이 없는 근거리 목표 3개를 지정한다.
2. 회전이 필요한 목표와 좁은 통로를 추가한다.
3. 동적 장애물로 경로를 막아 재계획과 recovery를 확인한다.
4. cancel과 비상정지를 확인한다.
5. 동일 목표 세트를 10회 반복한다.

초기 완료 기준은 목표 도달 9/10 이상, 충돌 0회, lifecycle node 중단 0회다. 실제 차체 속도와 제동거리가 확정되기 전에는 보수적인 속도를 사용한다.

## 4. 증빙 규칙

시험 ID 예시: `S3_20260801_hw01_cfg02_run03`

각 시험은 다음 파일을 같은 디렉터리에 둔다.

```text
metadata.yaml
commands.txt
rosbag/
map.yaml
map.pgm
posegraph
rviz.png
system_usage.csv
notes.md
```

`metadata.yaml`에는 Git commit, MCU 펌웨어 hash, 센서 장착값, wheel calibration, 파라미터 파일 hash와 알려진 실패를 기록한다. 대용량 rosbag은 Git에 올리지 않고 저장 경로와 SHA-256만 커밋한다.

## 5. 보고서에 사용할 결과

- RViz TF 및 sensor overlay 화면
- 동일 경로 지도 3회 overlay 그림
- wheel only와 wheel+IMU 지도 비교
- Nav2 목표 주행 성공률 표
- AI OFF/ON의 CPU, 메모리, 온도, topic 주기 비교 그래프
- 실패 사례와 수정 전후 비교

측정하지 않은 수치나 수행하지 않은 시험을 완료 결과로 작성하지 않는다.
