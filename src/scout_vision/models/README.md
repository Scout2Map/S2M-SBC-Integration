# Scout Vision — 모델 카드 (s2m_vAI_lite)

`scout_vision` 노드가 사용하는 재난 상황 인식용 YOLOv8n 기반 ONNX 모델이다.
COMS AU142 USB 웹캠 영상에서 위험/구조 관련 객체를 검출한다.

## 버전 이력

| 버전 | 클래스 구성 | 상태 | 비고 |
|---|---|---|---|
| v1 (`train_local.py`) | 6종 — `fire`와 `smoke` 분리 | 폐기 | 성능 부족으로 v2로 대체 |
| v2 (`train_local_v2.py`) | 5종 — `fire`/`smoke`를 `fire_smoke`로 통합 | **채택, 배포** | 아래 "기본 제공 모델"이 이 버전 |

배포 대상은 v2이며, 이 문서의 "파일 목록" 이하는 전부 v2 기준이다. v1은
왜 통합 결정을 내렸는지 근거를 남기기 위해 학습 스크립트와 결과를 함께
기록해 둔다(아래 "v1 실험 기록" 참고). v1의 가중치/ONNX 파일 자체는
저장소에 포함하지 않는다.

## 파일 목록

| 파일 | 용도 |
|---|---|
| `s2m_vAI_lite_640_v2.onnx` | 기본 모델. 입력 640x640, 정확도 우선 |
| `s2m_vAI_lite_320_v2.onnx` | 저전력 대안. 입력 320x320, Pi 5 부하가 문제될 때만 사용 |
| `s2m_vAI_lite_labels_v2.txt` | 클래스 라벨 (5줄, 모델 출력 순서와 동일) |

두 ONNX는 같은 학습 결과(`best.pt`)에서 입력 해상도만 다르게 export한 것으로,
클래스 구성과 정확도 특성은 동일하다.

## 클래스 (5종)

```
0 person
1 fire_smoke
2 exit_indicator
3 gas_tank
4 fire_extinguisher
```

원본 공개 데이터셋은 화재(fire)와 연기(smoke)를 별도 클래스로 제공하지만,
이 모델은 둘을 `fire_smoke` 하나로 합쳐 학습했다. 이벤트 엔진 쪽에서 화재와
연기를 구분해서 처리할 필요가 생기면 재학습이 필요하다.

## 학습 데이터

6개 공개 데이터셋(COCO 포맷)을 위 5개 클래스로 재매핑해서 병합했다.

| 원본 데이터셋 zip | 매핑 규칙 |
|---|---|
| `Yolo-disaster-relief.zip` | 전체 → `person` |
| `exit-sign-Extended.zip` | 전체 → `exit_indicator` |
| `fire-smoke-detection.zip` | 전체 → `fire_smoke` |
| `gas-tank.zip` | 전체 → `gas_tank` |
| `fire-extinguisher.zip` | 전체 → `fire_extinguisher` |
| `fire-and-person-detection.zip` | 카테고리명에 `person`/`human`/`victim` 포함 시 `person`, 그 외는 `fire_smoke` |

병합 스크립트(`train_local_v2.py`)가 각 데이터셋의 `train`/`valid`(또는 `val`,
`test`) split을 읽어 COCO bbox를 YOLO 정규화 좌표로 변환하고, 파일명 앞에
데이터셋 접두어를 붙여(`prefix_filename`) 하나의 `merged_dataset_2/` 아래
`train`/`valid`로 합친다. 매핑되지 않는 카테고리의 어노테이션은 조용히
제외된다(라벨 없이 이미지만 남을 수 있음).

## 학습 설정

| 항목 | 값 |
|---|---|
| 베이스 모델 | YOLOv8n (`yolov8n.pt`) |
| 입력 크기 | 640x640 |
| Epoch | 100 |
| Batch | 16 (VRAM 부족 시 8로 축소) |
| Optimizer | AdamW |
| Augmentation | HSV(h=0.015, s=0.7, v=0.4), scale=0.5, mosaic=1.0, mixup=0.15, close_mosaic=10 |

`hsv_s`와 `mixup`을 다른 기본값보다 높게 준 것은 반투명한 연기와 화염의 색
변화·경계 흐림을 데이터 증강으로 보강하기 위함이다(`train_local_v2.py` 주석
기준).

## ONNX Export

```python
trained_model.export(format='onnx', imgsz=[640, 640], dynamic=False, simplify=True, opset=12)
trained_model.export(format='onnx', imgsz=[320, 320], dynamic=False, simplify=True, opset=12)
```

**`dynamic=False`가 필수다.** `scout_vision`의 `vision_node.py`는 ONNX Runtime이
아니라 `cv2.dnn.readNetFromONNX()`(OpenCV DNN)로 모델을 로드하며, 이 백엔드는
고정 입력 크기를 전제로 `setInput()`에 텐서를 넣는다. 동적 입력 shape로 export하면
로드 자체는 되어도 추론 결과가 깨지거나 크래시가 날 수 있다.

같은 이유로 **`config/vision.yaml`의 `input_width`/`input_height`를 실제로 로드하는
ONNX 파일의 export 크기와 정확히 맞춰야 한다.** 640 모델을 쓰면서 320으로 설정하면
letterbox 단계에서 이미지 크기가 달라져 조용히 오검출이 늘어난다(에러는 나지 않는다).

## 성능 / 검증 상태

**아직 COMS AU142 실기기에서의 정확도·FPS·지연 측정은 하지 않았다.** 파이프라인
배선(카메라 → 추론 → `/vision/detections` → Event Engine → `/events`)까지는
`S2M-Event-Engine`, `S2M-SBC-Integration` 양쪽에서 확인되었으나, 이 특정 가중치의
실측 mAP나 Pi 5 위에서의 p50/p95 지연은 별도로 측정해서 이 문서에 채워 넣어야 한다.

```
정확도 (mAP50-95): 미측정
640 모델 추론 지연 (Pi 5, cv2.dnn): 미측정
320 모델 추론 지연 (Pi 5, cv2.dnn): 미측정
```

## 사용 방법

`scout_vision` 패키지의 `config/vision.yaml`과 `launch/vision.launch.py`가 이
폴더의 파일을 패키지 공유 디렉토리 기준 상대 경로로 가리키도록 되어 있다.
직접 실행할 때 경로를 명시하려면 패키지 설치 경로를 기준으로 지정한다.

```bash
ros2 launch scout_vision vision.launch.py \
  model_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_640_v2.onnx \
  labels_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_labels_v2.txt
```

Pi 5 부하가 문제일 때(SLAM + Nav2 + Event Engine과 동시 구동 시 프레임이 밀리는
경우)만 320 모델로 교체한다. 이때는 `input_width`/`input_height`도 320으로 같이
바꿔야 한다.

```bash
ros2 launch scout_vision vision.launch.py \
  model_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_320_v2.onnx \
  labels_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_labels_v2.txt \
  --ros-args -p input_width:=320 -p input_height:=320
```

## v1 실험 기록 — fire/smoke 분리 학습, 왜 통합했는가

v2로 통합하기 전, `fire`와 `smoke`를 별도 클래스로 둔 6클래스 모델을
`train_local.py`로 먼저 학습했다. `person`, `exit_indicator`, `gas_tank`,
`fire_extinguisher`, `fire`, `smoke` 각 클래스 데이터가 모두 1,500장을
넘는 규모였는데도, `fire`/`smoke`의 실사용 성능이 다른 클래스 대비 부족해
결국 v2에서 두 클래스를 `fire_smoke`로 합쳤다.

### v1 학습 곡선 (`results.csv`, 100 epoch)

수치는 **6클래스 전체 평균**이다(YOLO 학습 로그는 클래스별 지표를 CSV에
남기지 않는다). 개별 클래스 값이 아니므로 이 표만으로 "fire/smoke가 몇
점이다"라고 직접 읽을 수는 없지만, 전체 곡선의 정체 양상 자체가 뒤에서
추론하는 원인과 맞물린다.

| epoch | precision | recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| 20 | 0.650 | 0.554 | 0.592 | 0.392 |
| 40 | 0.725 | 0.595 | 0.638 | 0.445 |
| 60 | 0.744 | 0.617 | 0.657 | 0.468 |
| 80 | 0.725 | 0.635 | 0.669 | 0.480 |
| 100 (최종) | 0.702 | 0.661 | 0.666 | 0.484 |

epoch 60 이후로 mAP50-95가 0.468 → 0.480 → 0.484로 사실상 **평탄화(plateau)**
됐다. 100 epoch까지 채웠는데도 개선폭이 급격히 줄어드는 것은 데이터/증강
쪽 한계에 부딪혔다는 신호로 읽는 편이 합리적이다 — 에폭을 더 늘린다고
해결될 가능성은 낮다. 또한 precision이 epoch 60(0.744)을 정점으로 오히려
epoch 100(0.702)에서 낮아지고 recall만 계속 오르는 것은, 학습 후반부에
모델이 "덜 확신하는 대신 더 많이 잡는" 쪽으로 이동했다는 뜻이며 — 클래스
간 경계가 애매한 데이터가 섞여 있을 때 흔히 보이는 패턴이다.

### v1 confusion matrix (검증셋, 클래스별 recall)

학습 후 validation confusion matrix(정규화, 열 기준 = true class)를 직접
뽑아 확인했다. `models/v1_confusion_matrix.png`로 함께 보관한다.

| True 클래스 | 맞게 예측 | background로 놓침(미검출) | 기타 오분류 |
|---|---|---|---|
| `person` | 0.73 | 0.26 | ~0 (반올림 오차) |
| `fire` | **0.23** | **0.77** | 0 |
| `smoke` | **0.19** | **0.81** | 0 |
| `exit_indicator` | 0.94 | 0.06 | 0 |
| `gas_tank` | 0.93 | 0.06 | ~0.01 (반올림 오차) |
| `fire_extinguisher` | 0.91 | 0.08 | 0.01(→`person`으로 오분류) |

숫자로 보면 fire/smoke recall(0.23 / 0.19)이 나머지 클래스(0.73~0.94)와
거의 4배 가까이 차이 난다. **그런데 이 표에서 가장 중요한 건 `fire`
행과 `smoke` 열, `smoke` 행과 `fire` 열이 교차하는 칸이 사실상 0에
가깝다는 점이다** — 즉 모델이 fire를 smoke로, smoke를 fire로
헷갈려서 틀린 게 아니다. 두 클래스 모두 압도적으로 **background로
빠졌다(아예 검출을 못 했다).** 클래스끼리 혼동하는 것과 아예 놓치는
것은 원인이 다르므로, 아래 원인 목록도 이 결과에 맞춰 정리한다.

### 왜 데이터가 1,500장씩 있어도 fire/smoke만 부족했는가

confusion matrix가 보여주는 실패 모드는 "클래스 간 혼동"이 아니라
"애초에 confidence가 threshold를 못 넘겨서 미검출 처리됨"이다. 아래
요인들이 전부 confidence를 낮추는 방향으로 작용했을 가능성이 높다.

1. **연기·화염은 라벨 경계 자체가 불명확하다.** `person`, `gas_tank`,
   `fire_extinguisher`, `exit_indicator`는 형태가 고정된 강체(rigid
   object)라 "여기부터 여기까지가 객체"라는 bbox 경계가 명확하다. 반면
   연기는 반투명하고 경계가 서서히 흐려지며, 화염은 흔들리는 비정형
   형태라 사람이 라벨링해도 bbox가 데이터셋마다, 심지어 같은 데이터셋
   안에서도 일관되지 않기 쉽다. 라벨 경계가 들쭉날쭉하면 모델은 애매한
   위치에서 낮은 confidence만 내도록 학습되고, 이게 쌓이면 confidence
   threshold 미만으로 걸러져 confusion matrix에는 "background"로 잡힌다
   — 다른 클래스로 잘못 판단하는 것보다 이쪽이 더 흔한 실패 형태다.
2. **fire와 smoke가 같은 이미지 안에서 겹쳐 나타나 개별 bbox 신뢰도를
   깎는다.** 실제 화재 이미지는 화염 위/주변에 연기가 함께 있는 경우가
   대부분이라 두 객체의 bbox가 서로 겹친다. NMS 관점에서 겹친 저신뢰도
   박스들은 서로를 억제하며 사라지기 쉽고, confusion matrix에 fire↔smoke
   교차 오분류로 남기보다 둘 다 아예 안 잡힌 것으로 보고된다. v1의 매핑
   규칙(`'smoke' if 'smoke' in name.lower() else 'fire'`)도 카테고리
   이름에 `smoke` 문자열이 있는지만으로 이진 분류하는 휴리스틱이라, 두
   현상이 함께 찍힌 이미지의 라벨이 애초에 깔끔하게 갈리지 않았을 가능성이
   크다.
3. **출처가 다른 두 데이터셋을 그대로 합쳤다.** `fire-smoke-detection.zip`과
   `fire-and-person-detection.zip` 양쪽에서 fire/smoke 라벨을 가져오는데,
   두 데이터셋은 촬영 환경·화재 규모·카메라 거리가 서로 다른 별도 출처다.
   반면 `person`(`Yolo-disaster-relief`), `gas_tank`, `fire_extinguisher`,
   `exit_indicator`는 각각 단일 출처 데이터셋에서만 가져와 도메인이
   일관됐다. fire/smoke만 두 도메인이 섞이면서 모델이 일반화해야 할 시각적
   변이가 실질적으로 더 컸고, 이는 검증셋에서 낮은 confidence로 이어지기
   쉽다.
4. **v1의 증강 설정이 반투명 객체에 약했다.** v1은 `hsv_v=0.4`와
   `mosaic=1.0`만 사용했다. v2에서는 `hsv_s=0.7`(채도 증강 강화)과
   `mixup=0.15`가 추가됐는데, v2 스크립트 주석에도 "mixup augmentation for
   semi-transparent smoke"라고 명시된 것처럼 이건 정확히 연기 같은 반투명
   객체의 색상·투과도 변화를 흉내내기 위한 것이다. v1에는 이 보강이
   없었으므로, 학습 중 보지 못한 색상·투과도 변형이 검증/실사용 시
   confidence 하락으로 직결됐을 수 있다.
5. **스케일 편차가 유독 크다.** 화재/연기는 화면 전체를 채우는 큰 화재부터
   작은 불씨까지 크기 편차가 극단적인 반면, gas_tank·fire_extinguisher는
   상대적으로 균일한 크기·형태를 가진 물체다. 같은 장수의 데이터라도
   커버해야 하는 시각적 분산이 훨씬 넓고, 극단적인 스케일의 인스턴스일수록
   낮은 confidence로 예측되기 쉽다.

종합하면 fire/smoke의 문제는 "서로 헷갈리는 것"이 아니라 **"확신을 갖고
검출하지 못하는 것"**이었다 — confusion matrix가 이를 명확히 보여준다.
v2에서 `fire`와 `smoke`를 `fire_smoke`로 합친 결정은 이 진단과도 맞는다.
클래스를 하나로 합치면 같은 학습 인스턴스 수로 더 많은(중복 라벨링된)
샘플을 모아 confidence를 끌어올릴 수 있고, NMS 단계에서 fire·smoke가
서로를 억제하는 문제도 사라진다. 다만 이 통합은 fire와 smoke를 이벤트
단계에서 구분해야 할 필요(예: 화염만 있고 연기는 없는 초기 단계 감지)가
생기면 다시 갈라야 하는데, 그때는 클래스를 나누기 전에 먼저 (a) 라벨
경계 일관성 검수, (b) v2 수준의 증강 적용, (c) 가능하면 fire-only /
smoke-only로 촬영된 단일 도메인 데이터 확보부터 해야 v1과 같은 실패를
반복하지 않는다.

## 재학습

학습 스크립트는 이 저장소가 아니라 별도 학습 환경(GPU 머신)에서 실행한다.
원본 zip 6개를 `Scout2map-Dataset/` 아래 두고 `train_local_v2.py`(v2, 배포용)를
실행하면 `workspace/runs_2/scout_disaster_v2/weights/`에 `best.pt`와 두 ONNX가,
`workspace/`에 라벨 파일이 생성된다. 결과물 3개(640 onnx, 320 onnx, labels)를
이 폴더에 복사해 넣고 커밋하면 된다.

`train_local.py`(v1, fire/smoke 분리)는 위 실험 기록을 재현하거나 다시 분리
학습을 시도할 때만 참고한다. 결과물 경로가 `workspace/runs/scout_disaster_multi/`
로 v2와 다르고, 파일명에도 버전 접미사가 없다(`s2m_vAI_lite_640.onnx` 등) —
두 스크립트를 같은 `workspace/`에서 연달아 돌려도 서로 덮어쓰지 않는다.

### 학습 스크립트 자체는 어디에 두나

`models/`는 ONNX 산출물 전용으로 두고, 학습 스크립트와 v1 실험 로그는 옆에
`training/` 폴더를 새로 만들어 넣는 걸 추천한다.

```
src/scout_vision/
├── models/                     ← 배포용 ONNX + 라벨 + 이 카드
└── training/                   ← 학습 재현용 (colcon 빌드/설치 대상 아님)
    ├── train_local.py          # v1, fire/smoke 분리 (참고용, 폐기됨)
    ├── train_local_v2.py       # v2, 배포 모델을 만드는 스크립트
    └── v1_results.csv          # v1 학습 곡선 원본 (위 표의 출처)
```

`training/`은 ROS2 패키지 빌드 산출물이 아니라 순수 참고 자료이므로
`setup.py`의 `data_files`에 넣을 필요가 없다 — git에 소스로만 존재하면
충분하다(`colcon build`가 이 폴더를 건드리지 않는다).

## 이 폴더를 실제로 쓰려면 필요한 코드 변경 3곳

모델 파일을 여기 두는 것만으로는 자동 인식되지 않는다. `scout_vision`은
ROS2 colcon 패키지라 소스의 `models/`가 설치 결과물(`install/share/scout_vision/`)
로 그대로 복사되지 않으며, launch 파일의 기본 경로도 현재는 빈 문자열이다.
아래 세 파일을 함께 고쳐야 `ros2 launch scout_vision vision.launch.py`를
인자 없이 실행했을 때 이 폴더의 기본 모델을 자동으로 찾는다.

### 1. `setup.py` — models/를 설치 결과물에 포함

```python
data_files=[
    ('share/ament_index/resource_index/packages',
     ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml', 'README.md']),
    (os.path.join('share', package_name, 'launch'),
     glob('launch/*.launch.py')),
    (os.path.join('share', package_name, 'config'),
     glob('config/*.yaml')),
    (os.path.join('share', package_name, 'models'),
     glob('models/*.onnx') + glob('models/*.txt')),   # 추가
],
```

### 2. `launch/vision.launch.py` — 기본 경로를 패키지 공유 디렉토리 기준으로 계산

```python
default_model = os.path.join(share, 'models', 's2m_vAI_lite_640_v2.onnx')
default_labels = os.path.join(share, 'models', 's2m_vAI_lite_labels_v2.txt')
...
DeclareLaunchArgument('model_path', default_value=default_model),
DeclareLaunchArgument('labels_path', default_value=default_labels),
```

현재는 두 인자 모두 `default_value=''`로 되어 있어, 인자를 생략하면
`vision_node`가 "model file not found: <empty>"로 `/diagnostics`에 ERROR를
낸다.

### 3. `config/vision.yaml` — 문서용 기본값도 함께 갱신

`model_path`/`labels_path`는 launch 인자가 최종적으로 덮어쓰므로 동작에는
영향이 없지만, yaml만 보고 오해하지 않도록 존재하지 않는 예시 경로 대신
이 폴더의 실제 파일명으로 바꿔 둔다.

```yaml
model_path: "install/scout_vision/share/scout_vision/models/s2m_vAI_lite_640_v2.onnx"
labels_path: "install/scout_vision/share/scout_vision/models/s2m_vAI_lite_labels_v2.txt"
```

세 곳을 다 고친 뒤 `colcon build --packages-select scout_vision`으로
재빌드하면 `ros2 launch scout_vision vision.launch.py`를 인자 없이 실행해도
기본 640 모델이 자동으로 로드된다.
