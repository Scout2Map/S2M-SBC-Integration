# USB CDC udev 설정

Pico 센서와 주행 MCU가 재연결된 뒤에도 같은 장치명을 사용하도록 VID, PID와 serial을
모두 사용해 udev symlink를 만듭니다.

## 1. 장치 속성 확인

MCU를 하나씩 연결하고 실제 `/dev/ttyACM*` 또는 `/dev/ttyUSB*` 경로로 확인합니다.

```bash
udevadm info --query=property --name=/dev/ttyACM0 | \
  grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT'
udevadm info --attribute-walk --name=/dev/ttyACM0
```

두 MCU가 같은 VID/PID를 사용할 수 있으므로 serial 없이 장치 역할을 구분하지 마십시오.

## 2. 규칙 작성과 설치

`99-scout2map-usb.rules.example`을 복사한 뒤 placeholder를 실제 값으로 바꿉니다.

```bash
cp scripts/raspberry_pi/udev/99-scout2map-usb.rules.example /tmp/99-scout2map-usb.rules
nano /tmp/99-scout2map-usb.rules
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
마십시오.
