# 작업


검토 기준 커밋:

- `J3vn0/scout2map` `raspberry-pi-setup`: `181f81b`
- `Scout2Map/S2M-Hardware` `main`: `720ea6b`
- `Scout2Map/S2M-MCU_Bridge_Node` `main`: `f373787`
- `Scout2Map/S2M-FW-DrivingControl` 시작점: `3bb5bfe`
- `Scout2Map/S2M-SBC-Integration`: 기존 SBC 작업의 정식 이관 대상

## 2026-07-31

| 할 일 | 근거 | 확인 결과 | 처리 |
|---|---|---|---|
| SLAM·통신 소스 GitHub 업로드 | p.2, p.4 | `raspberry-pi-setup`의 Pi 설치, SLAM/Nav2 시뮬레이션, 검증 문서를 확인 | **정식 저장소 이관 완료**. 이 저장소에서 실차 모델 기준으로 정리 |
| MCU 제어·통신 자료 정리·공유 | p.2, pp.3–4 | 과거 문서는 Micro-ROS/UART 전제 | **최신 통합 결정 반영**. SBC 점검은 USB CDC 기준, 세부 wire protocol/펌웨어는 FW 저장소 소유 |
| 실차 SLAM 소프트웨어 검증 | p.3 | 문서/체크리스트만 있고 하드웨어 주행 결과·rosbag 없음 | **미완료, UGV 필요** |
| 네트워크 단절 시 시작점 복귀 프로토콜 | p.4 | 보고서에 요구사항만 명시됐다고 기록 | **요구사항 문서만 완료**, 구현/검증은 미완료 |

## 2026-08-05

| 할 일 | 근거 | 확인 결과 | 처리 |
|---|---|---|---|
| 브릿지 데이터의 지도 마커 좌표 연결 결정 | pp.1–2 | snapshot stamp가 cache 센서 시각과 다름 | **부분 완료**. 센서별 stamp 기준 설계와 임시 fallback 결정, schema/node/UGV 검증 미완료 |
| waffle을 실차 xacro로 교체 | pp.1–2 | `S2M-Hardware/UGV_description`에 실차 치수 기반 draft xacro와 spawn launch 존재 | **소스 통합 완료, 실행 미검증**. `s2m_bringup`이 실차 모델/world를 사용하며 TurtleBot3 의존성 제거. 빌드·스폰·동역학 보정은 UGV/Gazebo 환경에서 확인 필요 |
| heightmap+friction 요철·슬립 spike/world | pp.1–2 | `slip_test.world.sdf`, `bump_field.png`, launch 존재 | **부분 완료**. 에셋 구현 완료, Gazebo runtime spike와 slip-event 판별 검증 미완료 |
| 통신 두절 시 시작점 자동 복귀 시뮬레이션 | pp.1–2 | 구현/실행 근거 없음 | **미완료**. 장애 종류를 분리한 [시뮬레이션 계획](return-home-simulation-plan.md)만 작성 |

## 통신 두절을 두 종류로 나눈 이유

1. **SBC ↔ 주행 MCU USB CDC 두절**: MCU에 새 목표가 도착하지 않으므로 이동 자체가
   불가능하거나 위험하다. watchdog으로 즉시 정지하는 것이 맞다.
2. **UGV ↔ 원격 관제망 두절**: SBC, localization, Nav2, 모터 링크가 모두 정상일 때만
   온보드 시작점 복귀를 고려할 수 있다.

두 장애를 하나의 “통신 두절”로 묶어 자동 복귀시키면 모터 제어 링크가 불안정한
상태에서도 움직이려 할 수 있다. 시뮬레이션과 실기 acceptance도 두 경우를 분리한다.

