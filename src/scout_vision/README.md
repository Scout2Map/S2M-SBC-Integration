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
| 발행 | `/vision/info` | `vision_msgs/VisionInfo` |
| 발행 | `/diagnostics` | `diagnostic_msgs/DiagnosticArray` |

카메라 timestamp와 frame ID는 검출 메시지에 그대로 유지된다. Event Engine은 이
시각의 `map <- base_link` TF를 조회한다. depth가 없으므로 지도 마커는 객체 위치가
아니라 **촬영 당시 로봇 위치**다.

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
