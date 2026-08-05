# 통신 두절 시작점 복귀 시뮬레이션 계획

상태: **설계만 완료, ROS/Gazebo 실행 미수행**

이 기능은 주행 MCU firmware가 아니라 SBC의 상태 감시와 Nav2가 소유한다. 이
문서는 2026-08-05 회의 과제를 안전하게 나누기 위한 integration plan이며, 실제
node와 launch/test는 이 저장소의 향후 navigation 패키지에 구현한다.

## 장애 분류와 동작

| 장애 | 복귀 허용 | 동작 |
|---|---|---|
| 원격 관제 heartbeat loss | 조건부 | MCU link, localization, Nav2가 모두 healthy일 때 저장한 start pose로 이동 |
| 주행 MCU USB CDC loss | 금지 | watchdog 안전 정지, 복귀 goal을 보내지 않음 |
| localization/TF loss | 금지 | 안전 정지, 원격 복구 대기 |
| 장애물로 progress 없음 | 중단 | Nav2 recovery 제한 후 안전 정지 |
| E-stop/driver fault | 금지 | fault latch, 현장 명시적 재무장 필요 |

## 상태기계

```text
BOOT -> START_POSE_CAPTURED -> NORMAL
NORMAL --control network loss--> RETURN_REQUESTED -> RETURNING -> ARRIVED
       --MCU/localization/fault--> SAFE_STOP
RETURNING --MCU/localization/progress fault--> SAFE_STOP
```

start pose는 localization이 안정되고 operator가 mission arm을 승인할 때 한 번
저장한다. 단순 process 시작 시각의 `(0, 0, 0)`을 시작점으로 가정하지 않는다.

## 시뮬레이션 시나리오

| ID | 주입 | 합격 기준 |
|---|---|---|
| S1 | 평지에서 관제 heartbeat 중단 | 새 goal 없이 start pose 복귀, 도착 후 정지 |
| S2 | bump/slip 구간에서 관제 heartbeat 중단 | localization/progress가 healthy일 때만 복귀 지속 |
| S3 | 주행 MCU link loss 모사 | return goal 없음, `/cmd_vel` 0 및 FW watchdog 경로 선택 |
| S4 | `map -> odom` TF 중단 | return goal 취소, 안전 정지 |
| S5 | 복귀 경로 장애물/무진행 | 제한된 recovery 후 취소·안전 정지, 무한 재시도 없음 |
| S6 | 복귀 중 관제 연결 회복 | 자동 mission 재개 없음, operator 명시적 선택 대기 |

각 시험은 start pose, fault 시각, Nav2 result, `/cmd_vel`, TF, odometry를 rosbag으로
기록한다. `S2M-Hardware`의 slip world는 실행 자산일 뿐 위 상태기계를 포함하지
않으므로 별도 node/launch가 필요하다.
