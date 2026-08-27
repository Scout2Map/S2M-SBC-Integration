# Scout Vision — 모델 카드 (s2m_vAI_lite)

`scout_vision` 노드가 사용하는 재난 상황 인식용 YOLOv8n 기반 ONNX 모델이다.
COMS AU142 USB 웹캠 영상에서 위험/구조 관련 객체를 검출한다.

## 버전 이력

| 버전 | 클래스 구성 | 상태 | 비고 |
|---|---|---|---|
| v1 (`train_local.py`) | 6종 — `fire`와 `smoke` 분리 | 폐기 | 성능 부족으로 v2로 대체 |
| v2 (`train_local_v2.py`) | 5종 — `fire`/`smoke`를 `fire_smoke`로 통합 | 폐기(성능 부족) | `fire_smoke` recall 0.21로 낮아 v3로 대체 |
| v3 (`train_local_v3.py`) | 5종 — v2와 동일, `fire-and-person-detection.zip`만 제외 | 폐기(v4로 대체) | `fire_smoke` recall 0.56까지 개선했으나 v4가 더 낫다 |
| v4 (`train_local_v4.py`) | 6종 — `fire`/`smoke` 재분리, `fire-and-person-detection.zip` 제외 | **최고 성능, 배포 권장, ONNX 인수 대기** | `fire` 0.56 / `smoke` 0.54 recall, 아래 "v4 실험 기록" |
| v5 (`train_local_v5.py`) | 5종 — v2와 동일, `fire-smoke-detection.zip`만 제외 | 폐기(실패, 대조군) | `fire_smoke` recall 0.11로 급락 — 반대 실험으로 v3/v4 가설 검증용 |

> v3에서 확인했던 "`fire-and-person-detection.zip` 제외"라는 처방에, 처음 v3에서는
> 빠졌던 "`fire`/`smoke` 재분리"까지 다시 적용한 버전이 v4다. 지금까지
> 나온 5개 버전 중 `fire`/`smoke` 계열 recall이 가장 높고(0.56/0.54),
> 클래스도 다시 분리되어 있어 이벤트 엔진 쪽에서 화재와 연기를 구분
> 처리할 여지도 남는다. v5는 정반대로 "`fire-smoke-detection.zip`을
> 빼고 `fire-and-person-detection.zip`만 남긴" 대조 실험인데, recall이
> 0.11까지 떨어져서 — `fire-smoke-detection.zip`이 진짜 유효한 데이터,
> `fire-and-person-detection.zip`이 문제였던 데이터라는 그동안의 가설을
> 다시 한번 확인해 줬다.

아래 "파일 목록"·"클래스"·"학습 데이터"·"사용 방법"은 v4 기준으로
갱신했다. 다만 v4의 ONNX/labels 산출물 자체(`s2m_vAI_lite_640_v4.onnx`
등)는 아직 전달받지 못해 실제 저장소에는 아직 v2 파일이 남아 있다 —
파일이 오는 대로 커밋하면 된다. v1·v2·v3·v5의 실험 기록은 이 결정의
근거를 남기기 위해 학습 스크립트·결과와 함께 보관한다(아래 각 버전의
"실험 기록" 참고). 폐기된 버전들의 가중치/ONNX 파일 자체는 저장소에
포함하지 않는다.

## 파일 목록

| 파일 | 용도 |
|---|---|
| `s2m_vAI_lite_640_v4.onnx` | 기본 모델. 입력 640x640, 정확도 우선 |
| `s2m_vAI_lite_320_v4.onnx` | 저전력 대안. 입력 320x320, Pi 5 부하가 문제될 때만 사용 |
| `s2m_vAI_lite_labels_v4.txt` | 클래스 라벨 (6줄, 모델 출력 순서와 동일) |

두 ONNX는 같은 학습 결과(`best.pt`)에서 입력 해상도만 다르게 export한 것으로,
클래스 구성과 정확도 특성은 동일하다. (아직 실제로 저장소에 들어오지 않은
파일명 기준 — 도착 전까지는 v2 파일이 대신 들어 있다.)

## 클래스 (6종)

```
0 person
1 fire
2 smoke
3 exit_indicator
4 gas_tank
5 fire_extinguisher
```

v2/v3에서는 `fire`/`smoke`를 `fire_smoke` 하나로 합쳐 학습했지만, v4에서는
문제의 원인이었던 `fire-and-person-detection.zip`을 데이터에서 뺀 채로 다시
분리했다. 분리 상태에서도 recall이 v3의 통합 모델과 비슷하거나 더 나아서
(아래 "v4 실험 기록"), 화재와 연기를 이벤트 단계에서 구분할 필요가 생겨도
재학습 없이 바로 쓸 수 있다.

## 학습 데이터

`fire-and-person-detection.zip`을 제외한 5개 공개 데이터셋(COCO 포맷)을
위 6개 클래스로 재매핑해서 병합했다.

| 원본 데이터셋 zip | 매핑 규칙 |
|---|---|
| `Yolo-disaster-relief.zip` | 전체 → `person` |
| `exit-sign-Extended.zip` | 전체 → `exit_indicator` |
| `fire-smoke-detection.zip` | 카테고리명에 `smoke` 포함 시 `smoke`, 그 외는 `fire` |
| `gas-tank.zip` | 전체 → `gas_tank` |
| `fire-extinguisher.zip` | 전체 → `fire_extinguisher` |

`fire-and-person-detection.zip`은 v1/v2/v3에서 `fire`/`smoke`(또는
`fire_smoke`)와 `person` 라벨 양쪽에 노이즈를 섞는 것으로 확인되어(v2·v3
실험 기록 참고) v4에서는 아예 빼버렸다.

병합 스크립트(`train_local_v4.py`)가 각 데이터셋의 `train`/`valid`(또는 `val`,
`test`) split을 읽어 COCO bbox를 YOLO 정규화 좌표로 변환하고, 파일명 앞에
데이터셋 접두어를 붙여(`prefix_filename`) 하나의 `merged_dataset_4/` 아래
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
변화·경계 흐림을 데이터 증강으로 보강하기 위함이다(v2에서 도입, `train_local_v4.py`도
동일 설정 유지).

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
  model_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_640_v4.onnx \
  labels_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_labels_v4.txt
```

Pi 5 부하가 문제일 때(SLAM + Nav2 + Event Engine과 동시 구동 시 프레임이 밀리는
경우)만 320 모델로 교체한다. 이때는 `input_width`/`input_height`도 320으로 같이
바꿔야 한다.

```bash
ros2 launch scout_vision vision.launch.py \
  model_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_320_v4.onnx \
  labels_path:=$(ros2 pkg prefix scout_vision)/share/scout_vision/models/s2m_vAI_lite_labels_v4.txt \
  --ros-args -p input_width:=320 -p input_height:=320
```

> 위 파일명은 v4 기준이다. v4 ONNX가 도착하기 전까지 저장소에는 아직
> `_v2` 파일이 있으므로, 실제로 지금 당장 실행한다면 파일명을 `_v2`로
> 바꿔서 써야 한다.

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
서로를 억제하는 문제도 사라진다.

다만 실제로 v2를 학습해서 확인해 보니 통합만으로는 이 문제가 완전히
풀리지 않았다 — 아래 "v2 실험 기록" 참고. 그 결과를 바탕으로 다시
`fire`/`smoke`를 분리하되(v3), 이번엔 원인 후보로 지목했던 데이터셋
하나를 빼고 재시도하기로 했다.

## v2 실험 기록 — 통합 후에도 남은 문제, 그리고 재분리(v3) 결정

v2 배포 후 validation confusion matrix를 다시 뽑아 확인했다.
`models/v2_confusion_matrix.png`로 함께 보관한다.

| True 클래스 | 맞게 예측 | background로 놓침(미검출) | background가 이 클래스로 오검출된 비율 |
|---|---|---|---|
| `person` | 0.73 | 0.27 | 0.21 |
| `fire_smoke` | **0.21** | **0.79** | **0.56** |
| `exit_indicator` | 0.96 | 0.04 | 0.02 |
| `gas_tank` | 0.93 | 0.07 | 0.17 |
| `fire_extinguisher` | 0.93 | 0.07 | 0.04 |

두 가지가 눈에 띈다.

첫째, **`fire_smoke` recall이 0.21로, v1에서 개별 클래스였던 fire(0.23)/
smoke(0.19)와 사실상 같다.** 클래스를 합치면 인스턴스 수가 늘어나
confidence가 올라갈 거라는 가설은 맞지 않았다 — 여전히 79%가
background로 놓쳐진다. 즉 앞서 정리한 5가지 원인(라벨 경계 불명확,
fire/smoke 동시 등장으로 인한 NMS 억제, 이종 데이터셋 혼합, 약한 증강,
큰 스케일 편차) 중 적어도 일부는 클래스 통합으로는 해소되지 않는
문제였다는 뜻이다.

둘째, **v1에서는 보지 못했던 새로운 문제가 나왔다.** `fire_smoke`는
실제로는 background인 장면의 **56%를 fire_smoke로 오검출**한다(다른
클래스는 전부 2~21%). 즉 v2의 `fire_smoke`는 놓치기도 잘 놓치고(recall
0.21), 아닌데 있다고도 잘 우긴다(background 오검출 0.56) — recall과
precision 양쪽 다 불안정한 상태다. 이 조합은 애매한 라벨 경계나 낮은
confidence만으로는 잘 설명되지 않고, **학습 데이터 자체에 fire_smoke가
아닌 장면이 fire_smoke로 라벨링된 오염된 샘플이 섞여 있을 가능성**을
더 강하게 시사한다.

v1 분석에서 이미 지목했던 원인 3번(출처가 다른 두 데이터셋 혼합)을
다시 보면, `fire-and-person-detection.zip`은 카테고리명에 `smoke`
문자열이 있는지만으로 `fire`/`smoke`를 가르는 휴리스틱 매핑을 쓴다
(`train_local.py`/`train_local_v2.py` 공통). 이 데이터셋 자체가
원래 fire/smoke 검출용이 아니라 "화재+사람"을 함께 다루는 데이터셋이라,
매핑 과정에서 실제로는 애매하거나 배경에 가까운 장면이 `fire_smoke`로
잘못 들어갔을 가능성이 `fire-smoke-detection.zip`(전용 데이터셋, 전체를
그대로 매핑)보다 높다. background 오검출 0.56이라는 수치는 이 가설과
방향이 일치한다.

그래서 v3에서는 `fire-and-person-detection.zip`을 학습 데이터에서
제외하고 `fire-smoke-detection.zip` 단일 출처로만 `fire_smoke`를
학습해 보기로 했다. 클래스는 다시 나누지 않고 5종 통합을 그대로 두어,
"데이터셋 제외" 하나만 바꿔서 그 효과를 단독으로 확인하는 실험이다.
결과는 아래 "v3 실험 기록" 참고.

## v3 실험 기록 — `fire-and-person-detection.zip` 제외 후 결과

`train_local_v3.py`는 v2와 클래스 구성(5종, `fire_smoke` 통합)은
동일하고, `ZIP_FILES`/`DATASET_RULES`에서 `fire-and-person-detection.zip`
한 항목만 뺐다. 나머지 학습 설정(epoch, augmentation 등)은 v2와 같다.
학습 후 validation confusion matrix는 `models/v3_confusion_matrix.png`로
함께 보관한다.

| True 클래스 | 맞게 예측 | background로 놓침(미검출) | background가 이 클래스로 오검출된 비율 |
|---|---|---|---|
| `person` | 0.90 | 0.10 | 0.07 |
| `fire_smoke` | **0.56** | **0.44** | 0.55 |
| `exit_indicator` | 0.94 | 0.06 | 0.02 |
| `gas_tank` | 0.92 | 0.08 | 0.26 |
| `fire_extinguisher` | 0.92 | 0.07 | 0.10 |

### fire_smoke recall 변화 (v1 → v2 → v3)

| 버전 | 클래스 구성 | fire/smoke recall |
|---|---|---|
| v1 | 분리 | `fire` 0.23 / `smoke` 0.19 |
| v2 | 통합(`fire_smoke`), 6개 데이터셋 전부 사용 | 0.21 |
| v3 | 통합(`fire_smoke`), `fire-and-person-detection.zip` 제외 | **0.56** |

`fire-and-person-detection.zip` 하나를 뺐을 뿐인데 recall이 0.21 →
0.56으로 뛰었다 — v2 분석에서 이 데이터셋을 원인으로 지목했던 가설이
맞았다는 뜻이다. 흥미롭게도 `person` recall도 0.73 → 0.90으로 함께
올랐는데, `fire-and-person-detection.zip`이 카테고리명 휴리스틱으로
`person`도 같이 매핑하던 출처였으므로, 이 데이터셋이 `fire_smoke`뿐
아니라 `person` 라벨의 일관성도 깎고 있었던 것으로 보인다.

다만 완전히 해결된 건 아니다. `fire_smoke`는 여전히 다른 클래스
(exit_indicator/gas_tank/fire_extinguisher 0.92~0.94)보다 recall이
낮고(0.56), background 오검출률도 0.55로 v2(0.56)와 거의 그대로다 —
놓치는 비율은 크게 줄었지만 "아닌데 있다고 우기는" 문제는 남아 있다.
또한 `gas_tank`의 background 오검출률이 0.17 → 0.26으로 오히려
늘었는데, 데이터셋 하나를 빼면서 전체 학습 데이터 분포·배치 구성이
바뀐 부수 효과로 보이며 원인은 별도로 확인이 필요하다.

종합하면 v3는 v1/v2보다 `fire_smoke` 성능이 크게 나아졌지만, (a) 여전히
44%는 놓치고 55%는 배경에서 오검출한다는 점, (b) gas_tank 오검출이 늘어난
부수 효과가 남아 있다는 점 때문에 배포를 확정하기엔 아쉬웠다. 그래서 같은
데이터셋 제외 조건에서 `fire`/`smoke`를 다시 분리해 본 것이 v4다 — 아래
"v4 실험 기록" 참고. 결론적으로 v3는 v4로 대체됐다.

## v4 실험 기록 — `fire-and-person-detection.zip` 제외 + 재분리, 지금까지 최고

`train_local_v4.py`는 v3와 같은 데이터셋 구성(`fire-and-person-detection.zip`
제외)에서, 클래스만 v1처럼 `fire`/`smoke`로 다시 나눈 버전이다(6종). 매핑
규칙도 `fire-smoke-detection.zip`의 카테고리명에 `smoke`가 있으면 `smoke`,
없으면 `fire`로 v1과 동일하게 유지했다. 학습 설정(epoch, augmentation)은
v2/v3와 같다. confusion matrix는 `models/v4_confusion_matrix.png`로 함께
보관한다.

| True 클래스 | 맞게 예측 | background로 놓침(미검출) | 기타 오분류 | background가 이 클래스로 오검출된 비율 |
|---|---|---|---|---|
| `person` | **1.00** | 0.00 | 0 | 0.06 |
| `fire` | **0.56** | 0.44 | 0 | 0.31 |
| `smoke` | **0.54** | 0.45 | 0.01(→`fire`) | 0.28 |
| `exit_indicator` | 0.98 | 0.02 | 0 | 0.04 |
| `gas_tank` | 0.92 | 0.08 | 0 | 0.24 |
| `fire_extinguisher` | 0.92 | 0.08 | 0 | 0.06 |

핵심은 이거다 — **클래스를 다시 나눴는데도 recall이 v3(통합, 0.56)보다
떨어지지 않았다.** `fire` 0.56, `smoke` 0.54로 v3의 `fire_smoke` 0.56과
거의 같은 수준이다. v1에서 분리 학습이 나빴던 건("fire" 0.23 / "smoke"
0.19) 분리 자체가 문제가 아니라 `fire-and-person-detection.zip`의 노이즈가
문제였다는 걸 이걸로 다시 한번 확인한 셈이다. `fire`↔`smoke` 교차 오분류도
0.01(smoke→fire)뿐이라 v1 때와 마찬가지로 서로 헷갈리는 문제는 애초에
크지 않았다.

덤으로 `person` recall이 1.00까지 올랐다(v3 0.90, v2 0.73). `person`을
공급하던 두 출처(`Yolo-disaster-relief.zip`, `fire-and-person-detection.zip`)
중 후자를 빼고 나니 오히려 라벨이 더 깨끗해진 것으로 보인다. 다만 recall
1.00·miss 0.00은 다른 클래스 대비 지나치게 완벽해 보이는 수치라, 검증셋
규모가 작거나 `Yolo-disaster-relief.zip` 자체가 비교적 쉬운 이미지로만
구성됐을 가능성도 있다 — 실기기 영상으로 별도 확인이 필요하다.

남은 약점은 v3와 비슷하다. `fire`/`smoke` 둘 다 background 오검출률이
0.28~0.31로 여전히 낮지 않고, `gas_tank`의 background 오검출도 0.24로
v3(0.26)와 비슷한 수준으로 남아 있다. 이 두 가지는 `fire-and-person-detection.zip`
제외만으로는 안 풀리는 별개 이슈로 보이며, 실기기 검증 후 필요하면 추가
데이터 정제나 augmentation 조정이 필요할 수 있다.

**지금까지 나온 다섯 버전 중 `fire`/`smoke` recall이 가장 높고, 클래스도
분리돼 있어 활용도가 더 넓다 — 이 문서는 v4를 배포 후보로 추천한다.**

## v5 실험 기록 — 반대 실험: `fire-smoke-detection.zip` 대신 제외

v3/v4의 가설이 "`fire-and-person-detection.zip`이 문제"였다면, 반대로
그 데이터셋만 남기고 `fire-smoke-detection.zip`을 빼면 어떻게 되는지
확인한 것이 `train_local_v5.py`다. 클래스 구성은 v2/v3와 같은 5종
(`fire_smoke` 통합)이고, `ZIP_FILES`에서 `fire-smoke-detection.zip`만
빠졌다. confusion matrix는 `models/v5_confusion_matrix.png`로 보관한다.

| True 클래스 | 맞게 예측 | background로 놓침(미검출) | background가 이 클래스로 오검출된 비율 |
|---|---|---|---|
| `person` | 0.76 | 0.24 | 0.33 |
| `fire_smoke` | **0.11** | **0.89** | 0.38 |
| `exit_indicator` | 0.96 | 0.04 | 0.03 |
| `gas_tank` | 0.93 | 0.06 | 0.19 |
| `fire_extinguisher` | 0.93 | 0.06 | 0.06 |

결과는 명확하다. `fire_smoke` recall이 **0.11**로 지금까지 나온 값 중
가장 낮다 — v2(0.21)보다도, v1의 개별 `fire`(0.23)/`smoke`(0.19)보다도
나쁘다. 즉 `fire-and-person-detection.zip`만으로는 `fire_smoke`를 제대로
학습시키기에 데이터가 부족하거나 품질이 낮다는 뜻이고, 반대로 지금까지
"문제의 절반"으로만 지목했던 `fire-smoke-detection.zip`이 사실 fire/smoke
학습에서 **가장 중요한, 품질 좋은 데이터 소스**였다는 게 이 대조 실험으로
드러났다. `person` recall도 0.76으로 v3(0.90)/v4(1.00)보다 낮은데, 이건
v2와 마찬가지로 `fire-and-person-detection.zip`이 여전히 `person`도 같이
공급하고 있기 때문이다(v2 person recall 0.73과 비슷한 수준).

v5는 배포 후보가 아니라 **v3/v4에서 세운 가설을 반대 방향에서 검증하기
위한 대조군**이다. 결과가 예상대로 나빠졌다는 것 자체가, `fire-and-person-detection.zip`
제외라는 v3/v4의 처방이 옳은 방향이었음을 뒷받침한다.

## 재학습

학습 스크립트는 이 저장소가 아니라 별도 학습 환경(GPU 머신)에서 실행한다.
`fire-and-person-detection.zip`을 뺀 원본 zip 5개를 `Scout2map-Dataset/`
아래 두고 `train_local_v4.py`(v4, 배포 권장)를 실행하면
`workspace/runs_4/scout_disaster_v4/weights/`에 `best.pt`와 두
ONNX(`s2m_vAI_lite_640_v4.onnx`, `s2m_vAI_lite_320_v4.onnx`)가, `workspace/`에
라벨 파일(`s2m_vAI_lite_labels_v4.txt`)이 생성된다. 결과물 3개를 이 폴더에
복사해 넣고 커밋하면 된다. v4도 v3처럼 `fire-and-person-detection.zip`을
쓰지 않으므로 `Scout2map-Dataset/`에 그 zip이 없어도(또는 있어도 무시됨)
실행된다.

`train_local.py`(v1), `train_local_v2.py`(v2), `train_local_v3.py`(v3),
`train_local_v5.py`(v5)는 모두 폐기된 버전으로, 위 실험 기록을 재현하거나
비교할 때만 참고한다. 다섯 스크립트는 `MERGED_DIR`(`merged_dataset`~
`merged_dataset_5`)와 `project`(`runs`~`runs_5`), 출력 파일명(버전 접미사
`_v2`~`_v5`)이 모두 달라 같은 `workspace/`에서 연달아 돌려도 서로 덮어쓰지
않는다.

### 학습 스크립트 자체는 어디에 두나

`models/`는 ONNX 산출물 전용으로 두고, 학습 스크립트와 실험 로그는 옆에
`training/` 폴더를 새로 만들어 넣는 걸 추천한다.

```
src/scout_vision/
├── models/                     ← 배포용 ONNX + 라벨 + 이 카드
└── training/                   ← 학습 재현용 (colcon 빌드/설치 대상 아님)
    ├── train_local.py          # v1, fire/smoke 분리 (참고용, 폐기됨)
    ├── train_local_v2.py       # v2, 6개 데이터셋 전부 사용 (참고용, 폐기됨)
    ├── train_local_v3.py       # v3, fire-and-person-detection.zip 제외 (참고용, 폐기됨)
    ├── train_local_v4.py       # v4, v3 + fire/smoke 재분리 (배포 권장)
    ├── train_local_v5.py       # v5, fire-smoke-detection.zip 제외 대조군 (참고용, 폐기됨)
    └── v1_results.csv          # v1 학습 곡선 원본 (위 표의 출처)
```

`v1_confusion_matrix.png` ~ `v5_confusion_matrix.png`는 `models/`에 함께
보관해 두어 각 버전의 실험 기록과 나란히 확인할 수 있게 한다.

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
default_model = os.path.join(share, 'models', 's2m_vAI_lite_640_v4.onnx')
default_labels = os.path.join(share, 'models', 's2m_vAI_lite_labels_v4.txt')
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
model_path: "install/scout_vision/share/scout_vision/models/s2m_vAI_lite_640_v4.onnx"
labels_path: "install/scout_vision/share/scout_vision/models/s2m_vAI_lite_labels_v4.txt"
```

세 곳을 다 고친 뒤 `colcon build --packages-select scout_vision`으로
재빌드하면 `ros2 launch scout_vision vision.launch.py`를 인자 없이 실행해도
기본 640 모델이 자동으로 로드된다.
