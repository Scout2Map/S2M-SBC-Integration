# SBC 통합 기술 문서

| 문서 | 내용 |
|---|---|
| [MCU 브리지 인터페이스 계약](bridge-interface-contract.md) | 브리지 토픽·메시지·프레임과 SBC 소비 이름 |
| [SBC 실행 절차](sbc-runbook.md) | 설치·빌드·기능별 명령과 지도 저장 |
| [시뮬레이션 검증](simulation-validation-guide.md) | 요철·슬립·SLAM/Nav2·자동 복귀 재현 절차 |
| [구현 상태](implementation-status.md) | 소스 구현 범위와 실행 환경에서 남은 검증 |
| [지도 마커 좌표 설계](map-marker-coordinate-design.md) | 센서 cache age를 고려한 이벤트 좌표 결정 |
| [자동 복귀 시뮬레이션](return-home-simulation-plan.md) | 관제망 단절과 주행 링크 단절을 분리한 상태기계 |
| [SLAM/Nav2 실차 검증](slam-nav2-ugv-validation.md) | 센서·TF·지도·Nav2 검증 순서와 증빙 |
| [UGV 검증 체크리스트](ugv-validation-checklist.md) | 실제 장비에서 수행할 통합 acceptance 항목 |
| [실기기 통합 시험](real-hardware-validation.md) | 전원·MCU·토픽·TF·자동 복귀 활성화 조건 |
| [저장소 기준점](repository-baseline-2026-08-18.md) | 조직 저장소 최신 상태와 통합 판단 |

`구현 완료`, `Gazebo 검증 완료`, `실기 검증 필요`를 구분한다. Gazebo 검증 결과는
실제 UGV의 전원, 센서 정확도, 모터 제동과 MCU watchdog 검증을 대체하지 않는다.
