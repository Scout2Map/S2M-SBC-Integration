# MCU 브리지 인터페이스 계약

이 문서는 `S2M-MCU-BridgeNode`가 실제로 발행하는 토픽, 메시지 타입, 프레임을
SBC 쪽에서 소비하는 이름과 나란히 정리한 것이다. 브리지 저장소의
`scout2map_bridge/PROTOCOL.md`와 `scout2map_msgs/README.md`가 원본이며 이 문서는
SBC 통합 관점의 사본이다. 값이 어긋나면 브리지 저장소를 따른다.

기준 버전은 `dependencies.repos`에 고정된 커밋이다.

| 항목 | 값 |
|---|---|
| 저장소 | `https://github.com/Scout2Map/S2M-MCU-BridgeNode.git` |
| 고정 커밋 | `5955d877` |
| 패키지 | `scout2map_bridge`, `scout2map_msgs` |

## 1. 저장소 이름 변경 이력

브리지 저장소는 `S2M-MCU_Bridge_Node`에서 `S2M-MCU-BridgeNode`로 이름이 바뀌었다.
GitHub redirect 덕분에 옛 URL도 clone은 되지만 `vcs import`가 남기는 remote가
옛 이름으로 굳으므로 새 이름을 사용한다.

## 2. 센서 퓨전 MCU (Pico 2)

실행 노드는 `sensor_bridge`이다. `pico_bridge`는 V1.0.0의 이름이며 더 이상 없다.

```bash
ros2 launch scout2map_bridge sensor_bridge.launch.py
```

| 토픽 | 타입 | 비고 |
|---|---|---|
| `/sensors/temperature` | `sensor_msgs/msg/Temperature` | AHT21 |
| `/sensors/humidity` | `sensor_msgs/msg/RelativeHumidity` | AHT21 |
| `/sensors/illuminance` | `sensor_msgs/msg/Illuminance` | BH1750 |
| `/sensors/air_quality` | `scout2map_msgs/msg/AirQuality` | ENS160 |
| `/sensors/particulate` | `scout2map_msgs/msg/Particulate` | PMS7003 |
| `/sensors/env_snapshot` | `scout2map_msgs/msg/EnvSnapshot` | 전 센서 최신값 캐시, 기본 5Hz |
| `/sensors/status` | `scout2map_msgs/msg/SensorStatus` | 링크 상태, 기본 1Hz |
| `/sensors/raw_json` | `std_msgs/msg/String` | `publish_raw_json: true`일 때만 |

V1.0.0에서 바뀐 부분은 다음 두 가지다.

- `/bridge/status`가 `/sensors/status`로 바뀌었다.
- `BridgeStatus`가 `SensorStatus`로 바뀌었고 `framing_overflows` 필드가 추가되었다.

`EnvSnapshot`과 `AirQuality`의 필드는 V1.0.0과 동일하므로 이벤트 엔진 쪽 파싱
로직은 영향을 받지 않는다.

프레임은 `sensor_bridge.yaml`의 `frame_id`이며 기본값은 `sensor_fusion`이다.

## 3. 주행 제어 MCU (STM32F103)

실행 노드는 `drive_bridge`이다. V1.0.0에는 존재하지 않았다.

```bash
ros2 launch scout2map_bridge drive_bridge.launch.py
```

| 브리지 기본 토픽 | 타입 | 이 저장소에서 쓰는 이름 |
|---|---|---|
| `/drive/odom` | `nav_msgs/msg/Odometry` | `/odom` 으로 remap |
| `/drive/imu` | `sensor_msgs/msg/Imu` | `/imu/data` 로 remap |
| `/drive/range` | `sensor_msgs/msg/Range` | 그대로 |
| `/drive/battery` | `sensor_msgs/msg/BatteryState` | 그대로 |
| `/drive/status` | `scout2map_msgs/msg/DriveStatus` | 그대로 |
| `/drive/diagnostics` | `scout2map_msgs/msg/DriveDiagnostics` | 서비스 요청 시에만 발행 |
| `/cmd_vel` (구독) | `geometry_msgs/msg/Twist` | 그대로 |

remap은 `s2m_bringup/launch/s2m_onboard_bridge.launch.py`에서 수행한다. 브리지
저장소는 자신의 이름공간만 책임지고, 시스템 토픽 배치는 이 저장소가 정한다.

서비스는 다음 네 개이며 모두 `std_srvs/srv/Trigger`이다.

- `/drive/estop`
- `/drive/clear_fault`
- `/drive/reset_odom`
- `/drive/request_diagnostics`

### `/drive/link_ok`는 브리지가 발행하지 않는다

자동 복귀 정책은 `std_msgs/msg/Bool` 타입의 `/drive/link_ok`를 구독한다. 브리지는
이 토픽을 발행하지 않고 대신 `DriveStatus.link_ok`와 여러 fault 비트를 발행한다.

이를 잇는 것이 `s2m_bringup`의 `drive_link_adapter` 노드이다. 다음 조건 중 하나라도
성립하면 `false`를 발행한다.

- `DriveStatus`가 `status_timeout_sec` 동안 도착하지 않음
- `link_ok == false`
- `estop_latched`, `fault_stall`, `cmd_timeout`, `batt_dead` 중 하나가 참

`batt_critical`은 기본적으로 복귀를 막지 않는다. 전력이 부족한 상태로 제자리에
멈추는 것보다 출발점까지 돌아오는 편이 낫기 때문이다.

현재 `DriveStatus.link_ok`는 시리얼 포트가 열려 있고 최근 유효 telemetry frame이
`link_timeout_s` 이내에 수신됐는지를 뜻한다. CRC 오류 수와 PING/PONG 왕복 성공은
상태 판정에 아직 포함되지 않는다. 따라서 문서에서 이를 완전한 왕복 통신 품질로
표현하면 안 된다.

### skid 보정과 슬립 신호

최신 브리지는 `skid_factor`, `yaw_rate_encoder_radps`, `yaw_rate_imu_radps`,
`slip_ratio`, `slip_signal_valid`를 제공한다. `skid_factor` 기본값 `1.0`은 미측정 상태다.

```bash
ros2 run scout2map_bridge skid_calib
```

실차 바닥에서 teleop로 양방향 제자리 회전을 20~30초 수행하고 출력된 값을
`drive_bridge.yaml`에 반영한다. 이 보정 전에는 Event Engine의
`enable_drive_events: false`를 유지한다. 이 계수는 슬립 판정 신호 보정용이며 현재
펌웨어의 속도 명령 변환이나 `/drive/odom` 적분에는 적용되지 않는다.

## 4. TF 프레임

| 프레임 | 정의 위치 | 상태 |
|---|---|---|
| `base_link` | `s2m_description` xacro | 정의됨 |
| `lidar_link` | `s2m_description` xacro | 정의됨 |
| `imu_link` | `s2m_description` xacro | 정의됨 |
| `odom` | `drive_bridge`가 `odom -> base_link` 발행 | 정의됨 |
| `sensor_fusion` | 없음 | `s2m_onboard_bridge.launch.py`의 static TF로 보충 |
| `range_link` | 없음 | `s2m_onboard_bridge.launch.py`의 static TF로 보충 |

`sensor_fusion`과 `range_link`는 브리지가 메시지 header에 찍지만 URDF에 대응 링크가
없다. static TF를 발행하지 않으면 해당 메시지를 지도 좌표로 변환할 수 없고, 결과적으로
이벤트 마커를 배치할 수 없다.

launch의 기본 오프셋은 **측정값이 아니다.** 실차에서 측정한 뒤 교체한다.

```bash
ros2 launch s2m_bringup s2m_onboard_bridge.launch.py \
  sensor_fusion_x:=-0.048 sensor_fusion_z:=0.112
```

장기적으로는 `s2m_description` xacro에 두 링크를 추가하고 이 static TF를
`publish_sensor_frames:=false`로 끄는 것이 옳다.

## 5. TF 소유권

`odom -> base_link`는 한 노드만 발행해야 한다.

| 구성 | `odom -> base_link` 발행 주체 | `drive_bridge`의 `publish_tf` |
|---|---|---|
| 실차, EKF 없음 | `drive_bridge` | `true` (기본값) |
| 실차, `robot_localization` 사용 | `ekf_node` | `false` 로 변경 필요 |
| Gazebo 시뮬레이션 | `diff_drive` 플러그인 | 브리지를 실행하지 않음 |

시뮬레이션과 실차 브리지를 동시에 실행하지 않는다. `/odom`, `/imu/data`, `/cmd_vel`,
`odom -> base_link`가 모두 충돌한다.

실차 자동 복귀 mission에서는 `s2m_slam_real.launch.py`를
`use_nav2:=true use_return_home:=true`로 실행한다. Nav2 출력과
teleop 출력을 `/return_home/cmd_vel_input`으로 보내고 `cmd_vel_safety_gate` 하나만 최종
`/cmd_vel`을 발행해야 한다. `/cmd_vel` 직접 teleop는 브리지 단독 벤치 시험에만 쓴다.

## 6. 이벤트 엔진 소비 계약

**이벤트 발행 주체는 `S2M-Event-Engine`(`scout2map_event`) 하나다.** 이 저장소의 어떤
노드도 `/events`를 발행하지 않는다. 위험 판정 로직을 추가할 일이 생기면 이 저장소가
아니라 이벤트 엔진에 넣는다.

| 방향 | 토픽 | 타입 | 이 저장소에서의 출처 |
|---|---|---|---|
| 구독 | `/sensors/env_snapshot` | `scout2map_msgs/msg/EnvSnapshot` | `sensor_bridge` |
| 구독 | `/drive/status` | `scout2map_msgs/msg/DriveStatus` | `drive_bridge` |
| 구독 | `/imu/data` | `sensor_msgs/msg/Imu` | `drive_bridge` (remap) |
| 구독 | `/cmd_vel` | `geometry_msgs/msg/Twist` | Nav2 또는 조종 노드 |
| 구독 | `/control/heartbeat` | `std_msgs/msg/Empty` | 관제 서버 |
| 구독 | `/threshold/set` | `std_msgs/msg/String` | React 관제 UI |
| 발행 | `/events` | `std_msgs/msg/String` (JSON) | 이벤트 엔진 단독 |
| 발행 | `/event/*` | `std_msgs/msg/String` | 이벤트 엔진 단독 |

QoS는 양쪽 모두 RELIABLE, `KEEP_LAST`, depth 10이므로 정합한다. `EnvSnapshot`의 필드는
V1.0.0과 동일하므로 브리지 갱신의 영향을 받지 않는다.

이벤트 엔진은 `map -> base_link` TF를 조회해 좌표를 붙인다. 따라서 SLAM 또는 AMCL이
실행 중이 아니면 모든 이벤트가 `coordinate_status: "unresolved"`로 나간다. 이는 오류가
아니라 설계된 동작이다.

### return_home과의 책임 분담

`return_home`도 `/control/heartbeat`를 구독하지만 발행 책임과는 무관하다.

| 노드 | heartbeat 사용 목적 | 산출물 |
|---|---|---|
| `scout2map_event` | 통신 이벤트 마커 판정 | `/events` |
| `return_home` | 자동 복귀 또는 안전 정지 결정 | `/return_home/status`, Nav2 goal |

안전 인터록은 이벤트 엔진이 죽어 있어도 동작해야 하므로 `return_home`이 heartbeat를
직접 감시하는 구조를 유지한다. 다만 두 timeout이 따로 관리되므로, 이벤트 엔진의
`COMM_DEGRADED` 임계값(기본 1.5초)을 `return_home`의 `heartbeat_timeout_sec`
(기본 3.0초)보다 작게 유지한다. 그래야 자동 복귀가 걸리기 전에 운영자가 품질 저하를
먼저 본다.

### 링크 3종 구분

| 신호 | 의미 | 처리 |
|---|---|---|
| `EnvSnapshot.link_ok` | Pico 센서 MCU 링크 | 이벤트 `SENSOR_LINK_LOSS` |
| `/drive/link_ok` | STM32 주행 MCU 링크 | 이벤트 아님, 즉시 안전 정지 |
| `/control/heartbeat` | 관제망 | 이벤트 `COMM_DEGRADED` / `COMM_LOST` |

주행 링크 단절은 마커를 찍을 상황이 아니라 즉시 멈춰야 하는 상황이므로 이벤트로
만들지 않는다.

## 7. 정합성 점검

```bash
./scripts/raspberry_pi/check_mcu_interfaces.sh \
  --sensor-device /dev/scout2map_pico \
  --motor-device /dev/scout2map_drive \
  --require-sensor --require-motor
```

이 스크립트가 검사하는 항목이 곧 위 표의 실행 가능한 형태이다. 브리지 저장소를
업데이트했다면 `dependencies.repos`의 커밋 핀과 이 문서, 스크립트를 함께 갱신한다.
