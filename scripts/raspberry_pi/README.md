# Raspberry Pi 5 설치 안내

기준 환경은 Ubuntu 24.04 LTS 64-bit(arm64)와 ROS 2 Jazzy입니다. 설치 스크립트는
실차용 `onboard`와 Gazebo/RViz가 포함된 `sim` 프로필을 제공합니다.

## 1. 장비 확인

```bash
cat /etc/os-release
dpkg --print-architecture
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS,MODEL
df -h /
ip -br address
ping -c 3 github.com
```

Ubuntu 24.04, `arm64`, 전달받은 SSD가 루트 파일시스템인지 확인하고 업데이트합니다.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

## 2. 저장소와 워크스페이스 설치

```bash
cd ~
git clone https://github.com/Scout2Map/S2M-SBC-Integration.git
cd S2M-SBC-Integration
chmod +x scripts/raspberry_pi/*.sh

./scripts/raspberry_pi/install.sh \
  --profile onboard \
  --with-vision \
  --with-rplidar
sudo reboot
```

스크립트는 `~/scout2map_ws`를 만들고 이 저장소의 패키지를 연결합니다. 이어서 루트
`dependencies.repos`에 고정된 S2M-Hardware와 S2M-MCU_Bridge_Node를 `vcs import`로
가져와 빌드합니다. 셸 환경은 `~/scout2map_env.sh`에 기록됩니다.

Pi에서 Gazebo/RViz까지 시험할 때만 `--profile sim`을 사용합니다.

```bash
./scripts/raspberry_pi/install.sh --profile sim
```

## 3. 설치 후 검사

```bash
~/S2M-SBC-Integration/scripts/raspberry_pi/check_compatibility.sh \
  --profile onboard \
  --with-vision \
  --workspace ~/scout2map_ws

source ~/scout2map_env.sh
ros2 pkg prefix s2m_bringup
ros2 pkg prefix s2m_description
ros2 pkg prefix scout2map_bridge
ros2 pkg prefix scout2map_msgs
ros2 pkg prefix scout_gas
```

연결 전 `/dev/tty*`, `/dev/i2c-*`, `/dev/video*` 경고는 정상입니다. ROS 패키지나
워크스페이스의 `FAIL`은 해결해야 합니다.

## 4. USB CDC 브리지 확인

2026-08-05 통합 결정은 Micro-ROS/UART가 아니라 센서 Pico와 주행 STM32 각각의
bare-metal USB CDC 링크입니다. 실제 장치의 VID/PID/serial을 확인해 udev 규칙으로
`/dev/scout2map_pico`, `/dev/scout2map_drive` 같은 안정된 이름을 만듭니다.

```bash
udevadm info --query=property --name=/dev/ttyACM0
source ~/scout2map_env.sh
ros2 launch scout2map_bridge pico_bridge.launch.py

./scripts/raspberry_pi/check_mcu_interfaces.sh \
  --sensor-device /dev/scout2map_pico \
  --motor-device /dev/scout2map_drive \
  --require-sensor
```

현재 참조 bridge 커밋은 Pico 센서만 구현합니다. STM32 drive bridge가 추가되고
`/cmd_vel`과 `/wheel/odom` 계약이 확정된 뒤에 `--require-motor`를 합격 조건으로
사용합니다.

## 5. RPLIDAR C1

```bash
source ~/scout2map_env.sh
ros2 launch sllidar_ros2 sllidar_c1_launch.py
ros2 topic hz /scan
ros2 topic echo /scan --once
```

Slamtec 저장소 버전에 따라 launch 파일명이 다를 수 있으므로 설치된
`share/sllidar_ros2/launch` 목록을 확인합니다.

## 6. AI 추론 런타임

`--with-vision`은 ROS 이미지 패키지와 별도 Python 가상환경의 OpenCV/ONNX Runtime
CPU 기준선을 설치합니다. 모델과 NPU가 정해지지 않았으므로 PyTorch, Ultralytics,
Hailo 런타임은 기본 설치에 포함하지 않습니다.

```bash
./scripts/raspberry_pi/create_vision_venv.sh onnx
source ~/scout2map_venvs/vision/bin/activate
```

## 7. 실기 acceptance

최종적으로 RPLIDAR 주기, 센서 stamp/age, `map -> odom -> base_link`, USB CDC
watchdog 정지, Nav2 주행 성공률을 UGV에서 검증해야 합니다. 절차와 기록 양식은
[`docs/integration`](../../docs/integration/README.md)에 있습니다.
