# UGV 실기 검증 체크리스트

상태: **실기 미수행 — UGV와 확정 핀맵/엔코더 사양 필요**

호스트 정적 검사만으로 확인할 수 없는 MCU·차체·SLAM·marker·자동 복귀 통합 시험을
정리합니다.
결과 칸이 비어 있는 항목은 완료로 간주하지 않는다.

## 사전 입력 체크

| 입력 | 상태 | 필요한 값 |
|---|---|---|
| STM32 보드 | 미확정 | 후보 F103C8T6와 실제 MCU/보드 리비전 일치 여부 확인 필요 |
| encoder | 미확정 | 후보 JGB37-520B의 실제 장착 여부, PPR/CPR, 감속비, A/B 극성 확인 필요 |
| motor driver | 미확정 | 좌우 BTS7960 수량/배선, PWM/enable 핀과 극성 |
| 전원 | 미확정 | BTS 모터전원 6~27V 범위 안의 정격전압, 전류 제한, 퓨즈, 공통 접지 |
| 비상정지 | 미확정 | 물리 차단 위치, reset/재무장 절차 |

## 안전 준비

- 첫 시험은 바퀴를 지면에서 띄우고 차체를 고정한다.
- 전류 제한 가능한 파워 서플라이와 물리 비상정지를 사용한다.
- 한 명은 명령/로그를 담당하고 다른 한 명은 비상정지를 잡는다.
- USB 케이블 분리, MCU reset, SBC process kill을 각각 별도 장애로 시험한다.
- fault clear 전에는 주변·배선·드라이버 온도를 확인한다.
- RPWM/LPWM/R_EN/L_EN 외부 pulldown과 reset 구간 low를 오실로스코프로 확인한다.
- 43A peak 표기를 연속 허용전류로 해석하지 않고 stall current·방열·배선·퓨즈를
  실제 구성에서 검증한다.

## 단계별 시험표

| ID | 시험 | 합격 기준 | 결과 |
|---|---|---|---|
| B0 | MCU off/reset/boot pin 측정 | RPWM/LPWM/R_EN/L_EN low, 의도치 않은 pulse 없음 | 미수행 |
| B1 | 전원 인가/USB 연결/재연결 | 모든 경우 PWM=0, 자동 재시작 없음 | 미수행 |
| B2 | 정상 좌우 저속 명령 | 바퀴 방향이 좌표계와 일치, encoder 부호 일치 | 미수행 |
| B3 | STOP 명령 | 다음 제어 cycle에 목표·PWM 0 | 미수행 |
| B4 | USB cable 분리 | 설정 timeout 이내 목표·PWM 0, timeout 상태 기록 | 미수행 |
| B5 | duplicate/과거 sequence | 명령 폐기, watchdog 갱신 안 됨 | 미수행 |
| B6 | CRC/길이/범위 오류 주입 | 움직임 없음, 오류/fault 상태 관측 가능 | 미수행 |
| B7 | driver fault/E-stop | 즉시 PWM 0, reconnect만으로 fault 해제 안 됨 | 미수행 |
| B8 | 정·역 방향 전환 | 양 PWM 동시 활성 없음, duty 0/dead interval 확인 | 미수행 |
| B9 | stall/부하/열 시험 | 전류 제한·퓨즈 동작, 배선/driver 온도 기록, R_IS/L_IS 의미 확인 | 미수행 |
| C1 | encoder 1회전 환산 | 좌우 CPR과 거리 환산값 기록, 방향 일치 | 미수행 |
| C2 | 폐루프 step 응답 | overshoot/settling/current를 기록하고 안정 발산 없음 | 미수행 |
| R1 | 저속 직선 1m × 3회 | 좌우 편차와 wheel odom 오차 기록 | 미수행 |
| R2 | 제자리 360° 좌/우 × 3회 | yaw/encoder 오차와 재현성 기록 | 미수행 |
| R3 | SLAM 동일 경로 × 3회 | localization loss 없음, loop closure/맵 왜곡/경로 반복 오차 기록, 지도·rosbag·config·commit 보존 | 미수행 |
| M1 | 알려진 위치에서 센서 이벤트 | 센서별 stamp/age와 TF 조회 성공률, marker 위치 오차 기록 | 미수행 |
| M2 | TF 지연·누락 및 지도 변경 | unresolved 재처리 성공, 서로 다른 map_id 좌표 혼합 없음 | 미수행 |
| N1 | 원격 관제망만 단절 | MCU link/localization/Nav2 정상일 때만 시작점 복귀 | 미수행 |
| N2 | 주행 MCU USB CDC 단절 | 복귀 시도 금지, 현 위치 안전 정지 | 미수행 |

M1의 수치 합격선은 지도 해상도와 팀 요구에 맞춰 시험 전에 확정한다. 초기 권장안은
저속 평지에서 0.15m 이하 위치 오차와 TF 조회/재처리 성공률 99% 이상이지만, 이는
실측 전 제안값이며 확정 사양이 아니다.

## 기록 양식

```text
test_id:
date/operator:
firmware_commit:
bridge_commit:
hardware_revision:
protocol_version:
wheel/encoder parameters:
power supply/current limit:
rosbag path + sha256:
observed stop latency:
pass/fail:
notes:
```

## 현재 내릴 수 있는 판정

- 프로토콜 CRC/stream parsing과 watchdog 상태기계는 호스트 단위 테스트 대상이다.
- 실제 USB ISR/ring buffer, PWM 0 전파 시간, encoder scale, PID 안정성은 호스트
  테스트로 증명할 수 없다.
- xacro와 slip world는 bringup에 연결됐지만 Gazebo 실행 결과는 아직 없습니다.
- 자동 복귀는 [시뮬레이션 계획](return-home-simulation-plan.md)만 있고 실행 결과는 없다.
- 실차 SLAM 안정성은 UGV 주행 결과와 rosbag이 없으면 완료 처리하지 않습니다.
