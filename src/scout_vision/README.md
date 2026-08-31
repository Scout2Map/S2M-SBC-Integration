# Scout Vision

COMS AU142 USB 웹캠의 ROS 이미지를 YOLOv8 형식 ONNX 모델로 추론하는 독립
래퍼 패키지다. 이 패키지는 표준 `vision_msgs/Detection2DArray`까지만 발행하고,
통합 JSON `/events`와 지도 마커는 `scout2map_event`가 담당한다.

## 모델 계약

- Ultralytics YOLOv8 detection ONNX 단일 출력: `[1, 4 + classes, boxes]`
- RGB, NCHW, 0~1 정규화 및 letterbox 입력
- `labels_path`: 모델 출력 순서와 같은 UTF-8 클래스명(한 줄에 하나)
- 로드된 모델의 SHA-256을 실행 시 `/vision/info`에 발행해 어떤 가중치가 도는지
  런타임에 확인할 수 있다
- `cv2.dnn.readNetFromONNX()`(OpenCV DNN)로 로드하므로 **고정 입력 크기로 export한
  모델만 지원한다.** ONNX export 시 `dynamic=False`가 필수이며, `input_width`/
  `input_height` 파라미터를 export 크기와 정확히 맞춰야 한다.

다른 모델 형식이 확정되면 해당 출력 디코더만 추가한다.

## 기본 제공 모델

`models/`에 재난 상황 인식용 5클래스(`person`, `fire_smoke`, `exit_indicator`,
`gas_tank`, `fire_extinguisher`) YOLOv8n ONNX를 저장소에 포함해 둔다. 학습 데이터,
클래스 매핑, 검증 상태는 [`models/README.md`](models/README.md)를 따른다.

## 토픽

| 방향 | 토픽 | 타입 |
|---|---|---|
| 구독 | `/camera/image_raw` | `sensor_msgs/Image` |
| 발행 | `/vision/detections` | `vision_msgs/Detection2DArray` |
| 발행 | `/vision/snapshots` | `std_msgs/String` (JSON) |
| 발행 | `/vision/info` | `vision_msgs/VisionInfo` |
| 발행 | `/diagnostics` | `diagnostic_msgs/DiagnosticArray` |

카메라 timestamp와 frame ID는 검출 메시지에 그대로 유지된다. Event Engine은 이
시각의 `map <- base_link` TF를 조회한다. depth가 없으므로 지도 마커는 객체 위치가
아니라 **촬영 당시 로봇 위치**다.

### 감지 스냅샷 (`/vision/snapshots`)

한 프레임에 감지가 하나라도 있으면, 각 감지의 bbox를 여백 포함해서 잘라내
(기본 마진 15%) 작게 리사이즈(기본 최대 128px)하고 JPEG로 압축(기본
quality 60)한 뒤 base64로 인코딩해서 이 토픽에 발행한다.

```json
{
  "stamp_sec": 1234, "stamp_nanosec": 5678, "frame_id": "camera_optical_frame",
  "snapshots": [
    { "detection_id": "42:0", "class_id": "person_in_danger", "jpeg_b64": "..." }
  ]
}
```

`detection_id`는 `/vision/detections`의 `Detection2D.id`(`{sequence}:{index}`)와
같은 값이라, `scout2map_event`가 이벤트를 만들 때 같은 id로 스냅샷을 찾아
`/events`의 `extra.snapshot_jpeg_b64`에 그대로 실어보낼 수 있다. 관제 화면에서
"진짜 위험이 맞는지" 사람이 눈으로 확인할 수 있게 해주는 용도로, 특히
`person_in_danger`/`fire`처럼 오탐 비용이 큰 클래스에서 중요하다.

Pi 5 부하가 문제라면 `snapshot_enabled:=false`로 끌 수 있다 — 꺼도
`class_id`/`confidence` 기반 이벤트 자체는 그대로 동작하고, 썸네일만 빠진다.

**전체 프레임 스냅샷 (신규):** 위 크롭은 감지된 물체만 잘라내서 "이게 로봇
앞 어디쯤에 있는지" 맥락이 안 보인다는 문제가 있었다. `snapshot_full_frame_enabled`
(기본 `true`)가 켜져 있으면, 같은 payload에 `frame_jpeg_b64` 필드가 하나 더
붙는다 - 그 프레임에서 감지된 모든 박스를 그려 넣은 전체 카메라 이미지를
`snapshot_full_frame_max_width`(기본 480px)로 리사이즈, `snapshot_full_frame_jpeg_quality`
(기본 55)로 압축한 것이다. 크롭 목록(`snapshots`)은 그대로 유지되므로
`scout2map_event`의 `detection_id` 매칭 로직은 영향 없다.

```json
{
  "stamp_sec": 1234, "stamp_nanosec": 5678, "frame_id": "camera_optical_frame",
  "snapshots": [
    { "detection_id": "42:0", "class_id": "person_in_danger", "jpeg_b64": "..." }
  ],
  "frame_jpeg_b64": "..."
}
```

이 토픽은 `/vision/detections`보다 **먼저** 발행한다. 크롭·리사이즈·JPEG
인코딩·base64가 실제로 시간이 걸리는 작업이라, 순서를 반대로 하면(감지 먼저)
`scout2map_event` 쪽에서 감지 이벤트를 처리할 시점에 아직 스냅샷이 나가지도
않은 상태라 거의 항상 매칭에 실패한다 — `scout2map_event`의
`vision_snapshot_wait_s`(짧게 대기 후 발행)와 짝을 이루는 설계다.

## 실행

기본 카메라 설정은 Pi 5 부하 측정을 위해 640x480 10 FPS이며, AU142의 FHD 최대
해상도는 성능 검증 후 올린다.

`model_path`/`labels_path`를 생략하면 저장소에 포함된 기본 모델
(`models/s2m_vAI_lite_640_v2.onnx`, `models/s2m_vAI_lite_labels_v2.txt`)을
패키지 공유 디렉토리에서 자동으로 찾는다.

```bash
ros2 launch scout_vision vision.launch.py
```

Pi 5 부하가 문제일 때만 저전력 320 모델로 바꾼다. 이때는 `input_width`/
`input_height`도 함께 320으로 바꿔야 한다.

```bash
ros2 launch scout_vision vision.launch.py \
  model_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_320_v2.onnx \
  labels_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_labels_v2.txt \
  --ros-args -p input_width:=320 -p input_height:=320
```

**추론 지연이 클 때:** `max_fps`는 스로틀일 뿐 실제 `forward()` 소요 시간을
줄여주지 않는다 - Pi 5에서 640 모델 기준 프레임당 ~1000ms가 걸리면 `max_fps`를
5든 15든 체감 차이가 없다(어차피 그 이상 못 돈다). 320 모델로 바꾸는 게
가장 확실하고, `dnn_num_threads`(기본 0 = OpenCV 기본 동작 유지)를 Pi의 코어
수(예: 4)로 명시해보는 것도 공짜로 시도해볼 만하다:

```bash
ros2 launch scout_vision vision.launch.py --ros-args -p dnn_num_threads:=4
```

다른 모델로 완전히 교체하려면 임의의 경로를 넘기면 된다.

```bash
ros2 launch scout_vision vision.launch.py \
  model_path:=/opt/scout2map/models/custom.onnx \
  labels_path:=/opt/scout2map/models/custom_labels.txt
```

통합 실행은 다음과 같다.

```bash
ros2 launch s2m_bringup s2m_slam_real.launch.py \
  use_event_engine:=true use_vision:=true
```

모델/클래스 파일 누락, 잘못된 출력 형식, stale camera frame은 navigation을
중단시키지 않고 `/diagnostics` 오류 또는 경고로 격리한다.
