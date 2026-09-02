# USB CDC udev 설정

Pico 센서와 주행 MCU가 재연결된 뒤에도 같은 장치명을 사용하도록 udev symlink를
만듭니다.

두 MCU는 서로 다른 VID/PID를 사용하므로 (Pico 2 `2e8a:000a`, STM32F103
`0483:5740`) 기본 규칙은 VID/PID만으로 역할을 구분합니다. 같은 모델을 두 개
연결하는 경우에만 `ATTRS{serial}`을 추가합니다.

`S2M-MCU-BridgeNode`의 `scout2map_bridge/udev/99-scout2map.rules`와 이 저장소의
규칙은 동일한 symlink를 만듭니다. **둘 중 하나만 설치합니다.** 두 파일을 모두
설치하면 같은 장치에 두 규칙이 적용되어 권한이 예측 불가능해집니다. 이 저장소의
규칙은 `dialout` 그룹과 `0660`을 사용하므로 실차 SBC에서는 이쪽을 권장합니다.

## 1. 장치 속성 확인

MCU를 하나씩 연결하고 실제 `/dev/ttyACM*` 또는 `/dev/ttyUSB*` 경로로 확인합니다.

```bash
udevadm info --query=property --name=/dev/ttyACM0 | \
  grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT'
udevadm info --attribute-walk --name=/dev/ttyACM0
```

출력된 `ID_VENDOR_ID`, `ID_MODEL_ID`가 위 값과 일치하는지 확인합니다. 일치하지
않으면 클론 보드이므로 규칙 파일의 값을 실제 값으로 교체합니다.

## 2. 규칙 작성과 설치

`99-scout2map-usb.rules.example`을 복사합니다. VID/PID가 위 확인 결과와 같으면
수정 없이 그대로 사용할 수 있습니다.

```bash
cp scripts/raspberry_pi/udev/99-scout2map-usb.rules.example /tmp/99-scout2map-usb.rules
sudo install -m 0644 /tmp/99-scout2map-usb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
```

케이블을 다시 연결한 뒤 결과를 확인합니다.

```bash
ls -l /dev/scout2map_pico /dev/scout2map_drive
readlink -f /dev/scout2map_pico
readlink -f /dev/scout2map_drive
```

장치 권한은 `dialout` 그룹과 `0660`을 사용합니다. `/dev/tty*`에 `chmod 777`을 적용하지
마십시오. 사용자 계정이 `dialout` 그룹에 없으면 포트를 열 수 없습니다.

```bash
sudo usermod -aG dialout "$USER"
```

그룹 추가 후에는 재로그인 또는 재부팅이 필요합니다.
