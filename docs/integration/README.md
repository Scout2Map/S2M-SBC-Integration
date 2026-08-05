# SBC 통합 기술 문서

| 문서 | 내용 |
|---|---|
| [구현 상태](implementation-status.md) | 소스 구현 범위와 실행 환경에서 남은 검증 |
| [지도 마커 좌표 설계](map-marker-coordinate-design.md) | 센서 cache age를 고려한 이벤트 좌표 결정 |
| [자동 복귀 시뮬레이션](return-home-simulation-plan.md) | 관제망 단절과 주행 링크 단절을 분리한 상태기계 |
| [SLAM/Nav2 실차 검증](slam-nav2-ugv-validation.md) | 센서·TF·지도·Nav2 검증 순서와 증빙 |
| [UGV 검증 체크리스트](ugv-validation-checklist.md) | 실제 장비에서 수행할 통합 acceptance 항목 |

`구현 완료`는 소스와 정적 검사가 준비됐다는 뜻이며, `실기 검증 필요` 항목은 ROS 2,
Gazebo 또는 UGV 실행 결과가 확보되기 전까지 완료로 간주하지 않습니다.
