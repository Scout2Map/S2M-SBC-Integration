# Scout2Map 저장소 기준점

확인일: 2026-08-18

| 저장소 | 최신 main 또는 기본 브랜치 | SBC 고정 기준 | 판단 |
|---|---|---|---|
| S2M-SBC-Integration | sbc-integration 976a03f | 현재 브랜치 | Event/Bridge/실차 SLAM 반영 완료 |
| S2M-Event-Engine | d7c95fb | 7013a22 | 이벤트 계약은 반영, 8월 18일 예측 기능은 보류 |
| S2M-Hardware | 41c2435 | c3d55f3 | 최신 변경은 Battery Cover 기구 파일뿐임 |
| S2M-MCU-BridgeNode | 5955d87 | 5955d87 | sensor_bridge, drive_bridge, skid 보정 계약 반영 |
| S2M-FW-DrivingControl | eb10627 | 별도 flash | USB CDC, BNO055, 전압·거리 센서까지 갱신 |
| S2M-FW-SensorFusion | c0659f6 | 별도 flash | 8월 13일 이후 변경 없음 |
| S2M-Web-Monitoring | 8ce152e | 별도 배포 | main 변경 없음 |

## 8월 13일 이후 주요 변경

MCU Bridge는 `pico_bridge`를 `sensor_bridge`로 변경하고 STM32 `drive_bridge`를 추가했다.
주행 입력은 `/cmd_vel`, 출력은 `/drive/odom`, `/drive/imu`, `/drive/status`다. SBC launch가
이를 `/odom`, `/imu/data`로 remap한다. `/cmd_val`이라는 토픽은 없으며 팀 공유 문장의
오타로 판단한다.

DrivingControl은 USB CDC framing과 telemetry, BNO055, ADC 전압 측정, VL53L0X 거리 센서,
명령 timeout과 watchdog을 구현했다. 최신 Bridge는 `skid_factor` 보정 명령을 제공하지만
기본값 `1.0`은 미측정 값이므로 실차 보정 전 슬립 이벤트를 활성화하면 안 된다.

Event Engine은 8종 이벤트, `/events` 통합 JSON, 지도 좌표, debounce와 임계값 DB를
7013a22에서 구현했다. d7c95fb에는 sensor history와 온도 선형 예측이 추가됐지만 다음
문제가 남아 있어 SBC pin을 바로 올리지 않는다.

- NumPy와 scikit-learn 의존성이 package.xml과 setup.py에 선언되지 않았다.
- prediction node가 기본 launch에 포함되지 않았다.
- SensorHistoryDB.get_recent_data가 잘못 들여쓰기되어 인스턴스 메서드가 아니다.
- DB 보존 기간, 최대 크기, ROS timestamp와 validity 저장 정책이 없다.

Event Engine에서 위 항목을 수정하고 ROS 그래프·DB 동시 접근 시험을 통과한 커밋이
나오면 `dependencies.repos`를 d7c95fb 이후의 검증 SHA로 갱신한다.

## SBC에서 이번에 보완한 범위

- 실차 Nav2 출력을 안전 게이트 입력으로 remap할 수 있게 했다.
- `s2m_return_home_real.launch.py`로 Event Engine, return_home, drive link adapter와
  단일 최종 `/cmd_vel` 경로를 연결했다.
- 실차 자동 복귀는 자동 무장하지 않고 정상 heartbeat·주행 링크·TF 확인 후 operator가
  출발점 저장과 무장을 수행하게 했다.
- telemetry freshness와 완전한 왕복 링크 품질을 구분하고 skid 보정 절차를 문서화했다.
