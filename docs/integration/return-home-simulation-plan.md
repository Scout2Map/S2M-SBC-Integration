# 관제망 단절·배터리 위험 시작점 복귀 시뮬레이션 계획

상태: **관제망 단절 자동 복귀는 Gazebo 검증 완료. 배터리 CRITICAL 트리거는
정책 단위 시험만 통과, Gazebo/실차 검증 대기**

SBC 상태 감시와 Nav2를 이용해 관제망 단절 또는 배터리 CRITICAL 상태일 때
시작점으로 복귀하는 노드와 시뮬레이션 fault injector를 구현했다. 관제망 단절
경로는 2026-08-13 ROS 2 Jazzy와 Gazebo Harmonic에서 빌드, 실차 형상 spawn, Nav2
활성화와 시작점 복귀까지 확인했다. 배터리 CRITICAL 트리거는 2026-08-31에
추가한 것으로, `return_home_policy.py`의 순수 함수 단위 시험(`decide()`)만
통과한 상태다 — `rclpy`/Gazebo가 없는 환경에서 작업해 `drive_link_adapter`·
`sim_fault_injector`의 실제 노드 기동과 `/sim_faults/set_battery_critical`
서비스 호출을 통한 end-to-end 시나리오는 아직 재현하지 못했다. 아래 S7
시나리오로 실행 검증이 필요하다.

## 구현 자산

- src/s2m_bringup/scripts/return_home_node.py
- src/s2m_bringup/scripts/return_home_policy.py
- src/s2m_bringup/scripts/drive_link_adapter.py — 실차: `DriveStatus.batt_critical`을
  `/drive/battery_critical`(Bool)로 분리 발행
- src/s2m_bringup/scripts/cmd_vel_safety_gate.py
- src/s2m_bringup/scripts/sim_fault_injector.py — 시뮬레이션: 동일 계약의
  `/drive/battery_critical` 발행 + `/sim_faults/set_battery_critical` 주입 서비스
- src/s2m_bringup/launch/s2m_return_home_sim.launch.py
- src/s2m_bringup/config/return_home_sim.yaml
- src/s2m_bringup/config/return_home_real.yaml
- src/s2m_bringup/config/drive_link_adapter.yaml
- src/s2m_bringup/test/test_return_home_policy.py

watchdog은 simulation clock 정지의 영향을 받지 않도록 steady clock을 사용한다.
실행 절차는 simulation-validation-guide.md에 정리했다.

## 장애 분류와 동작

| 장애 | 복귀 허용 | 동작 |
|---|---|---|
| 원격 관제 heartbeat loss | 조건부 | MCU link, localization, Nav2가 모두 healthy일 때 저장한 start pose로 이동 |
| 배터리 CRITICAL (팩 9.9V 이하, batt_dead 아님) | 조건부 | MCU link, localization, Nav2가 모두 healthy일 때 저장한 start pose로 이동 — heartbeat loss와 동일한 전제조건 사용 |
| 주행 MCU USB CDC loss | 금지 | watchdog 안전 정지, 복귀 goal을 보내지 않음 |
| localization/TF loss | 금지 | 안전 정지, 원격 복구 대기 |
| 장애물로 progress 없음 | 중단 | Nav2 recovery 제한 후 안전 정지 |
| E-stop/driver fault | 금지 | fault latch, 현장 명시적 재무장 필요 |
| 배터리 DEAD (펌웨어가 이미 구동 차단) | 금지 | 복귀 시도 안 함 — 이미 주행 자체가 불가능한 상태 |

가스(ENS160 위험 판정)는 여전히 트리거가 아니다. `event_engine`의 `HIGH_GAS`
이벤트는 지도 마커만 생성하며 `return_home`은 이 이벤트를 구독하지 않는다.

## 상태기계

```text
BOOT -> START_POSE_CAPTURED -> NORMAL
NORMAL --control network loss / battery critical--> RETURN_REQUESTED -> RETURNING -> ARRIVED
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
| S7 | 평지에서 `/sim_faults/set_battery_critical`로 배터리 CRITICAL 주입 (heartbeat/drive link는 정상 유지) | 새 goal 없이 start pose 복귀, 도착 후 정지. `/return_home/status`의 `reason`이 `"battery critical"`로 찍히는지 함께 확인 |

각 시험은 start pose, fault 시각, Nav2 result, `/cmd_vel`, TF, odometry를 rosbag으로
기록한다. `S2M-Hardware`의 slip world는 실행 자산일 뿐 위 상태기계를 포함하지
않으므로 별도 node/launch가 필요하다.

## 확인한 결과와 남은 시험

관제 heartbeat 단절 시험은 `NORMAL -> RETURN_REQUESTED -> RETURNING -> ARRIVED` 전이를
완료했다. 저장한 시작점은 map 좌표계에서 기록됐고 최종 odometry 위치는 시작점에서
약 0.325 m 이내였다. 주행 링크 단절 주입은 `safe stop: drive link lost or stale` 전이를
확인했다.

S2, S4, S5, S6의 전체 실행과 실차 모터 차단은 아직 완료하지 않았다. 특히 SAFE_STOP의
소프트웨어 상태 전이만으로 실차 안전성을 주장하면 안 되며, STM32 USB CDC 브리지,
300 ms 명령 timeout, 하드웨어 비상 정지를 함께 시험해야 한다.

**S7(배터리 CRITICAL 트리거)은 아직 실행하지 않았다.** `return_home_policy.decide()`의
새 분기(`battery_critical`)는 호스트 단위 시험 10개로 검증했지만, 이건 순수 함수
시험이라 `drive_link_adapter`가 실제 `DriveStatus.batt_critical`을
`/drive/battery_critical`로 올바르게 옮기는지, `sim_fault_injector`의 신규 서비스가
Gazebo에서 실제로 동작하는지는 확인하지 못했다 — 이 세션에 `rclpy`가 없어 노드를
띄울 수 없었다. 실차/시뮬레이션 어느 쪽이든 S7을 먼저 돌려보고 결과를 이 문서에
반영해야 한다.
