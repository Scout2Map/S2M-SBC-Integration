# MCU 브리지 재정합 변경 요약

이 문서는 커밋 메시지와 PR 설명을 쓰기 위한 임시 요약이다. 반영이 끝나면 삭제해도
된다.

## 배경

`dependencies.repos`가 `S2M-MCU-BridgeNode`의 V1.0.0(`f373787`)에 고정되어 있었다.
그 이후 브리지 저장소는 이름이 바뀌고 주행 브리지가 추가되면서 노드, launch,
메시지, 토픽 이름이 모두 달라졌다. 이 저장소의 문서와 점검 스크립트는 존재하지
않는 이름을 가리키고 있었다.

## 발견한 불일치

| 구분 | 이 저장소가 참조하던 것 | 브리지의 실제 이름 |
|---|---|---|
| 저장소 URL | `S2M-MCU_Bridge_Node` | `S2M-MCU-BridgeNode` |
| launch | `pico_bridge.launch.py` | `sensor_bridge.launch.py` |
| 상태 메시지 | `BridgeStatus` | `SensorStatus` |
| 상태 토픽 | `/bridge/status` | `/sensors/status` |
| 휠 오도메트리 | `/wheel/odom` | `/drive/odom` |
| IMU | `/imu/data` | `/drive/imu` |
| 주행 링크 | `/drive/link_ok` (Bool) | 없음, `/drive/status`의 필드 |
| 프레임 | `sensor_fusion`, `range_link` | URDF에 링크 없음 |

`EnvSnapshot`과 `AirQuality`의 필드 정의는 V1.0.0과 동일하다. 이 두 메시지를
파싱하는 하위 소비자는 영향을 받지 않는다.

가장 중요한 두 가지는 다음과 같다.

1. `return_home`이 구독하는 `/drive/link_ok`를 아무도 발행하지 않는다. 실차에서
   자동 복귀 노드가 `drive_seen == false` 상태로 고정된다. 시뮬레이션에서는
   `sim_fault_injector`가 Bool을 발행하므로 드러나지 않았다.
2. 브리지가 메시지 header에 찍는 `sensor_fusion`, `range_link` 프레임이 URDF에
   없다. TF 변환이 실패하므로 환경 이벤트를 지도 좌표에 배치할 수 없다.

## 변경 내용

### 신규 파일

- `src/s2m_bringup/scripts/drive_link_adapter.py`
  `DriveStatus`를 `/drive/link_ok`(`std_msgs/msg/Bool`)로 축약한다. 링크 자체뿐
  아니라 `estop_latched`, `fault_stall`, `cmd_timeout`, `batt_dead`도 반영한다.
  `batt_critical`은 기본적으로 복귀를 막지 않는다.
- `src/s2m_bringup/config/drive_link_adapter.yaml`
- `src/s2m_bringup/launch/s2m_onboard_bridge.launch.py`
  실차 브리지 두 개와 어댑터를 함께 시작하고, `drive/odom`과 `drive/imu`를
  `/odom`, `/imu/data`로 remap하며, 누락 프레임의 static TF를 발행한다.
- `docs/integration/bridge-interface-contract.md`
  브리지 토픽·메시지·프레임의 단일 참조표.

### 수정 파일

- `dependencies.repos`: 저장소 이름 수정, 브리지 핀을 `5955d877`로, Hardware 핀을
  `c3d55f3a`로 갱신, `S2M-Event-Engine` 추가
- `tools/static_check.py`: 커밋 핀 개수 고정(2개) 검사를 URL 개수와 일치하는지
  검사하도록 일반화
- `scripts/raspberry_pi/check_compatibility.sh`: `scout2map_event` 패키지 확인 추가
- `scripts/raspberry_pi/check_mcu_interfaces.sh`: 토픽 계약 전면 교체, TF 검사와
  `--odom-topic` / `--imu-topic` 옵션 추가
- `scripts/raspberry_pi/udev/99-scout2map-usb.rules.example`: placeholder를 실제
  VID/PID로 교체
- `scripts/raspberry_pi/udev/README.md`: 규칙 파일 중복 설치 경고, `dialout` 안내
- `scripts/raspberry_pi/README.md`, `README.md`, `src/s2m_bringup/README.md`
- `src/s2m_bringup/CMakeLists.txt`, `package.xml`
- `docs/integration/` 아래 `README.md`, `sbc-runbook.md`,
  `real-hardware-validation.md`, `slam-nav2-ugv-validation.md`,
  `implementation-status.md`, `repository-baseline-2026-08-13.md`
- `scripts/raspberry_pi/PACKAGE_INVENTORY.md`

## 남은 작업

- `s2m_onboard_bridge.launch.py`의 static TF 오프셋은 측정값이 아니다. 실차에서
  측정한 뒤 교체하거나, `s2m_description` xacro에 `sensor_fusion`과 `range_link`
  링크를 추가하고 `publish_sensor_frames:=false`로 전환한다.
- `robot_localization` 도입 시 `odom_topic:=/drive/odom`으로 되돌리고
  `drive_bridge`의 `publish_tf`를 `false`로 바꾼다.
- `scout_gas`는 시뮬레이션 가우시안 모델만 사용하며 `/sensors/env_snapshot`을
  구독하지 않는다. 실센서 기반 위험 지도는 별도 작업이 필요하다.
- 주행 이벤트 3종과 관제망 통신 이벤트 2종은 아직 어느 노드도 발행하지 않는다.

## 검증

```bash
python3 tools/static_check.py
bash -n scripts/raspberry_pi/*.sh
python3 -m py_compile src/s2m_bringup/scripts/drive_link_adapter.py
```

ROS 노드 실행, TF 연결, 실차 동작은 검증하지 않았다.
