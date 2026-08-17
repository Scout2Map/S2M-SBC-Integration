# Scout2Map 저장소 기준점

확인일: 2026-08-13

| 저장소 | 확인한 최신 커밋 | 통합 판단 |
|---|---|---|
| S2M-SBC-Integration | main ac238ed / sbc-integration 20e2e79 | main은 최소 골격, 통합 작업 기준은 sbc-integration |
| S2M-Hardware | c3d55f3 | 최신 변경은 기구 CAD이며 시뮬레이션 기준은 720ea6b 유지 |
| S2M-MCU_Bridge_Node | f373787 | Pico 가상 발행기와 USB CDC 브리지 |

| S2M-FW-SensorFusion | c0659f6 | 센서 융합 펌웨어 v1.2 기준 |
| S2M-FW-DrivingControl | 07a8ee9 | 엔코더 폐루프와 watchdog 구현, SBC USB 프로토콜은 후속 통합 |
| S2M-Web-Monitoring | 8ce152e | 웹 모니터링 초안, 이벤트 계약 확정 필요 |

dependencies.repos의 커밋 고정은 통합 빌드 재현성을 위한 것이다. Hardware 최신
커밋은 STL과 Fusion 360 파일 추가이므로, Gazebo 자산이 바뀌지 않은 현재에는
기존 시뮬레이션 기준점을 유지한다.

자동 복귀 구현에서 사용하는 `/control/heartbeat`와 `/drive/link_ok`는 현재 실제 MCU
브리지가 제공하는 확정 계약이 아니다. 전자는 관제 연결 감시, 후자는 STM32 주행
링크 상태로 분리해 후속 브리지 구현에서 연결해야 한다.

## 갱신: MCU 브리지 재정합

확인일: 2026-08-17

| 저장소 | 갱신 커밋 | 변경 내용 |
|---|---|---|
| S2M-MCU-BridgeNode | f373787 -> 5955d87 | 저장소 이름 변경, `drive_bridge` 추가, `BridgeStatus` -> `SensorStatus` |
| S2M-Hardware | 720ea6b -> c3d55f3 | 기구 CAD만 변경, `UGV_description` 내용은 동일 |

브리지가 V1.0.0에서 크게 바뀌면서 이 저장소의 launch 이름, 상태 토픽, 오도메트리
토픽 참조가 모두 실재하지 않는 이름을 가리키고 있었다. 위 커밋으로 핀을 옮기고
문서와 점검 스크립트를 실제 계약에 맞추었다.

`/drive/link_ok`는 여전히 브리지가 직접 발행하지 않는다. `DriveStatus`를 해석해
이 토픽을 만드는 `drive_link_adapter`를 `s2m_bringup`에 추가해 계약을 잇는다.
상세 내용은 bridge-interface-contract.md를 따른다.

원격 저장소 조회 결과 위 커밋은 2026-08-13 기준 각 저장소의 최신 HEAD다. 이후 조직
저장소 변경을 통합할 때에는 `dependencies.repos`의 고정 커밋과 이 표를 함께 갱신한다.
