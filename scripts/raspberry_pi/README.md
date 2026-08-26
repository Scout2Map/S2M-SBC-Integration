# 라즈베리파이 5 설치

로봇에 탑재되는 SBC(라즈베리파이 5)와 개발용 노트북을 같은 스크립트로 구성한다.
프로파일만 다르다.

| 프로파일 | 대상 | 설치 내용 |
|---|---|---|
| `onboard` | 로봇의 라즈베리파이 5 | ROS 스택, udev 규칙. Gazebo 없음 |
| `sim` | 개발용 노트북 | ROS 스택, Gazebo Harmonic, RViz. udev 규칙 없음 |

전제 조건은 Ubuntu 24.04(arm64 또는 amd64)와 ROS 2 Jazzy다. 다른 버전에서는
스크립트가 즉시 중단된다.

## 설치

```bash
git clone -b sbc-integration \
  https://github.com/Scout2Map/S2M-SBC-Integration.git ~/sbc-push
cd ~/sbc-push
./scripts/raspberry_pi/install.sh --profile onboard
sudo reboot
```

재부팅은 `dialout` 그룹 적용을 위한 것이다. 이 그룹이 없으면 시리얼 포트가 열리지
않는다.

노트북에서는 다음과 같이 실행한다.

```bash
./scripts/raspberry_pi/install.sh --profile sim
```

### 옵션

| 옵션 | 설명 |
|---|---|
| `--profile onboard\|sim` | 기본값은 `onboard` |
| `--workspace PATH` | colcon 워크스페이스. 기본값은 `~/scout2map_ws` |
| `--repo-dir PATH` | 저장소 경로. 기본값은 자동 탐지 |
| `--parallel-workers N` | colcon 병렬도 제한 |
| `--no-build` | 패키지와 udev만 설치하고 빌드는 생략 |
| `--no-udev` | `onboard`에서도 udev 규칙을 설치하지 않음 |

라즈베리파이 5에서 빌드 중 스왑이 발생하면 병렬도를 줄인다.

```bash
./scripts/raspberry_pi/install.sh --profile onboard --parallel-workers 2
```

## 스크립트가 하는 일

1. Ubuntu 기본 패키지와 로케일 설정
2. ROS 2 apt 저장소 등록
3. `manifests/`의 목록에 따라 ROS 패키지 설치
4. 사용자를 `dialout` 그룹에 추가
5. udev 규칙 설치 (`onboard`만)
6. `src/`의 패키지를 워크스페이스에 심볼릭 링크
7. `dependencies.repos`의 고정 커밋으로 외부 저장소 가져오기
8. `rosdep` 의존성 해결 후 `colcon build`
9. `~/scout2map_env.sh` 생성 및 `.bashrc`에 등록

같은 명령을 다시 실행해도 안전하다. `dependencies.repos`를 수정한 뒤 재실행하면
새 커밋으로 갱신된다.

## 패키지 목록

`manifests/`의 기본 파일과 선택형 Vision 파일이 설치 대상을 정의한다.

| 파일 | 시점 |
|---|---|
| `apt-base.txt` | ROS 저장소 등록 전 시스템 유틸리티 |
| `ros-tools.txt` | colcon, rosdep, vcstool 등 빌드 도구 |
| `ros-onboard.txt` | SLAM, Nav2, URDF, 조종 등 로봇 실행에 필요한 전부 |
| `ros-sim.txt` | Gazebo와 RViz. `sim` 프로파일 전용 |
| `ros-vision.txt` | `create_vision_venv.sh`가 설치하는 카메라·Vision 스택 |

`ros-onboard.txt`의 모든 항목은 `s2m_bringup`의 launch 파일이 실제로 사용한다.
사용하는 노드가 생기기 전까지는 패키지를 추가하지 않는다.

## 외부 저장소

`dependencies.repos`가 커밋 단위로 고정한다.

| 저장소 | 제공 패키지 |
|---|---|
| `S2M-Hardware` | `s2m_description` (URDF, 시뮬레이션 자산) |
| `S2M-MCU-BridgeNode` | `scout2map_bridge`, `scout2map_msgs` |
| `S2M-Event-Engine` | `scout2map_event` |
| `sllidar_ros2` | RPLiDAR C1 드라이버 |

저장소 자체의 `scout_vision`은 기본 빌드에 포함되지만 `use_vision`은 기본적으로
꺼져 있다. 실차에서 실행하기 전에 모델과 클래스 파일을 준비한다.

저장소를 갱신했다면 `dependencies.repos`의 커밋 핀도 함께 옮긴다. 핀이 옛 커밋을
가리키면 `vcs import`가 옛 코드를 가져오며, 이는 빌드 성공 여부로는 드러나지 않는다.

## udev 규칙

세 장치가 모두 시리얼 포트로 잡히므로 연결 순서에 따라 번호가 바뀐다. 규칙을
설치하면 고정 이름이 생긴다.

| 심볼릭 링크 | 장치 |
|---|---|
| `/dev/scout2map_pico` | 센서 퓨전 MCU (Pico 2, USB CDC) |
| `/dev/scout2map_drive` | 주행 제어 MCU (STM32F103, USB CDC) |
| `/dev/scout2map_lidar` | RPLiDAR C1 (CP210x) |

설치 후 장치를 다시 연결하고 확인한다.

```bash
ls -l /dev/scout2map_pico /dev/scout2map_drive /dev/scout2map_lidar
```

빠진 것이 있으면 실제 VID/PID를 규칙 파일과 대조한다.

```bash
udevadm info --query=property --name=/dev/ttyACM0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID'
```

자세한 내용은 [udev 안내](udev/README.md)를 참고한다.

`S2M-MCU-BridgeNode`도 MCU용 규칙 파일을 포함한다. **둘 중 하나만 설치한다.**
두 규칙이 같은 장치에 적용되면 권한이 예측 불가능해진다.

## 설치 확인

```bash
source ~/scout2map_env.sh
./scripts/raspberry_pi/check_compatibility.sh --profile onboard
```

OS, ROS 배포판, 필수 패키지, 장치 심볼릭 링크, `dialout` 그룹, 라즈베리파이의
전원 및 발열 플래그를 점검한다.

브리지를 실행한 뒤에는 토픽과 TF 계약을 확인한다.

```bash
ros2 launch s2m_bringup s2m_onboard_bridge.launch.py

./scripts/raspberry_pi/check_mcu_interfaces.sh \
  --sensor-device /dev/scout2map_pico \
  --motor-device /dev/scout2map_drive \
  --require-sensor --require-motor
```

## 실행

```bash
ros2 launch s2m_bringup s2m_slam_real.launch.py
```

단계별 검증 절차는
[실차 검증 체크리스트](../../docs/integration/real-hardware-validation.md)를 따른다.

## 환경 변수

`~/scout2map_env.sh`가 생성되고 `.bashrc`에서 자동으로 읽힌다.

| 변수 | 값 |
|---|---|
| `ROS_DOMAIN_ID` | `42` |
| `SCOUT2MAP_REPO` | 저장소 경로 |
| `SCOUT2MAP_WS` | 워크스페이스 경로 |

로봇과 노트북이 같은 네트워크에 있고 `ROS_DOMAIN_ID`가 같으면 노트북에서 RViz로
로봇의 토픽을 볼 수 있다. 두 대를 분리하려면 한쪽의 값을 바꾼다.

## 비전 스택

카메라 및 ONNX 관련 설치는 제거했다. 해당 노드가 아직 구현되지 않았고, 설치만
해두면 실제로 동작하는지 확인할 방법이 없기 때문이다. Vision AI 노드를 구현하는
시점에 필요한 패키지만 다시 추가한다.
