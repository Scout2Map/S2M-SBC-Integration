# SBC OS 서비스 정리 — ROS 스택에 자원 몰아주기 (2026-08-30)

## 배경

SBC(라즈베리파이 5, Ubuntu 24.04 Server + ROS2 Jazzy)에서 ROS 스택과 무관한
OS 레벨 systemd 서비스를 정리해 CPU/메모리/디스크 IO 여유를 SLAM, Nav2,
event_engine, comm_relay 쪽으로 몰아주는 작업이다. ROS 노드나 launch 파일은
건드리지 않는다 — 순수하게 systemd 서비스 레이어만 대상으로 한다.

`scripts/raspberry_pi/`의 `install.sh`/`check_compatibility.sh`가 이미 있는
저장소(`S2M-SBC-Integration`)에 같은 패턴으로 추가할 수 있는 스크립트를
`trim-unused-services.sh`로 만들었다. 아직 저장소에 커밋하지는 않았고, 오빠가
실기에서 먼저 확인해본 뒤 필요하면 `scripts/raspberry_pi/systemd/`에 넣는 걸
제안한다.

## 접근 방식

`systemctl disable --now`만 쓴다. `mask`나 패키지 제거는 하지 않는다 —
나중에 필요해지면 `systemctl enable --now <service>` 한 줄로 되돌릴 수 있어야
하기 때문이다. 스크립트는 기본이 dry-run이고, 건드린 서비스 이름을
`/var/lib/scout2map/trimmed-services.log`에 기록해서 `--restore` 한 번으로
전부 되돌릴 수 있게 했다.

## SAFE 티어 — 바로 꺼도 되는 것

헤드리스 로봇 SBC에 화면, 프린터, 모뎀, snap 패키지, 실사용 중인 온보드
블루투스가 없다는 전제로 고른 목록이다.

| 서비스 | 이유 |
|---|---|
| `cups`, `cups-browsed` | 프린터 없음 |
| `ModemManager` | 셀룰러 모뎀 없음 |
| `bluetooth`, `hciuart` | MCU는 USB CDC로 붙어 있어 온보드 BT/UART 라디오를 쓰지 않음 |
| `triggerhappy` | 전원 버튼 등 물리 입력 이벤트, 헤드리스에선 불필요 |
| `snapd`(+socket, seeded) | snap 패키지 미사용 (`PACKAGE_INVENTORY.md` 기준 전부 apt/소스 빌드) |
| `packagekit` | GUI 패키지 관리자 백엔드, 헤드리스에서 불필요 |
| `switcheroo-control` | 듀얼 GPU 전환, Pi에 해당 없음 |
| `accounts-daemon` | GUI 로그인 관리자용, 헤드리스에서 불필요 |
| `multipathd`(+socket) | SAN 멀티패스, 해당 없음 |

## avahi-daemon — 끄지 않고 오히려 s2m.local로 활용하기로 함

처음엔 SAFE 티어에 넣었었는데, 오빠 판단으로 뺐다. 필드 로봇이라 항상 같은
네트워크/고정 IP에 있는 게 아니라 현장마다 DHCP로 붙는 경우가 많아서, IP를
매번 스캔하거나 외우는 것보다 mDNS로 `s2m.local` 하나만 기억하는 쪽이 실질적으로
더 낫다고 판단했다. 그래서 `trim-unused-services.sh`는 `--apply` 시:

1. avahi-daemon을 SAFE 티어에서 제외 — 끄지 않는다.
2. 오히려 `avahi-daemon`/`avahi-daemon.socket`을 명시적으로
   `enable --now` 해서, 베이스 이미지가 기본으로 꺼둔 경우까지 챙긴다.
3. `hostnamectl set-hostname s2m`으로 호스트 이름을 `s2m`으로 바꿔서
   `s2m.local`이 실제로 이 SBC를 가리키게 만든다 (`/etc/hosts`의
   `127.0.1.1` 줄도 같이 맞춘다).

호스트 이름 변경이 싫으면 `--apply --no-hostname`으로 스킵할 수 있다(이 경우
avahi-daemon enable은 여전히 하되 이름은 안 건드림 — 그러면 기존 호스트
이름 그대로 `<기존이름>.local`이 된다).

**주의**: 호스트 이름 변경은 `--restore`가 추적하지 않는다. 되돌리고
싶으면 `sudo hostnamectl set-hostname <원래이름>`을 직접 실행한다. 또한
SSH 설정 파일이나 스크립트에 예전 호스트 이름/IP를 하드코딩해둔 게 있다면
같이 업데이트해야 한다.

## GUI 티어 — 데스크톱/디스플레이 매니저 (`--with-gui`, 별도 opt-in)

`install.sh --profile onboard`는 `ros-base`(headless ROS 런타임)만 설치하고
`ros-jazzy-desktop`이나 RViz는 `sim` 프로파일 전용이라, ROS 스택 자체는 애초에
GUI를 요구한 적이 없다(`PACKAGE_INVENTORY.md` 확인). 그런데 실물 SBC에 GUI가
떠 있다면, 그건 ROS 패키지가 아니라 SD 카드에 구운 OS 이미지 자체가
"Ubuntu Server"가 아니라 "Ubuntu Desktop" 같은 데스크톱 이미지였을 가능성이
높다는 뜻이다. 이건 저장소 코드로는 확인이 안 되고 실기에서 직접 봐야 한다.

그래서 SAFE/CONDITIONAL과 묶지 않고 `--with-gui`라는 별도 플래그로 뺐다.
`--apply --with-gui`를 주면:

1. `gdm3`/`gdm`/`lightdm`/`sddm`/`lxdm`/`xdm`/`wdm` — 흔한 디스플레이
   매니저들을 훑어서 설치돼 있는 것만 끈다(안 깔려 있으면 자동 스킵, 다른
   티어와 동일한 방식).
2. 기본 부팅 타겟이 `graphical.target`이면 `multi-user.target`으로 바꾼다
   — 다음 재부팅부터 로그인 화면 없이 바로 텍스트 콘솔로 뜬다. 이미
   `multi-user.target`(즉 원래도 헤드리스 이미지)이면 아무것도 안 건드림.

**되돌리기**: `--restore`가 부팅 타겟도 같이 되돌린다(서비스 상태 파일과는
별개로 `/var/lib/scout2map/previous-boot-target`에 기록). 급하게 모니터를
꽂아서 GUI로 뭔가 확인해야 할 때는 되돌리지 않아도 그때만
`sudo systemctl start gdm3`(설치된 디스플레이 매니저 이름으로) 또는
`sudo systemctl isolate graphical.target`으로 그 세션만 띄울 수 있다 —
`--restore`를 매번 돌릴 필요는 없다.

## CONDITIONAL 티어 — 확인 후 끌 것

`--with-conditional` 플래그로 따로 분리했다. 잘못 끄면 실제로 문제가 생길 수
있어서 SAFE 티어와 한 번에 묶지 않았다.

- `unattended-upgrades` + `apt-daily-upgrade.timer`: 자동 업데이트가 임무
  도중에 조용히 설치되고 재부팅까지 이어질 수 있다. 끄는 걸 권장하지만,
  껐다는 걸 잊으면 보안 패치가 안 들어가니 대신 수동으로 주기적으로
  `apt update && apt upgrade`를 해줘야 한다.
- `NetworkManager-wait-online` / `systemd-networkd-wait-online`: 부팅 시간을
  늘리기만 하고(네트워크 자체는 어차피 올라옴) 실제 서비스 기동을
  느리게 하므로 꺼도 안전한 경우가 대부분이지만, 어떤 게 실제로 이 SBC의
  네트워크를 올리는지(`NetworkManager` vs `systemd-networkd`) 확인 후 그
  wait-online만 끄는 게 안전하다.

## 절대 건드리지 않는 것

`ssh`, `systemd-networkd`(또는 실제로 쓰는 `NetworkManager`), `wpa_supplicant`,
`systemd-udevd`(MCU/LiDAR의 `/dev/scout2map_*` 심볼릭 링크가 여기 의존),
`polkit`, `systemd-timesyncd` — 이것들은 ROS2 DDS 통신, SSH 원격 접속, 시리얼
장치 인식, 시간 동기화(로그 타임스탬프)에 직접 필요하다.

## 사용법 (실기에서)

```bash
# 1. 뭐가 바뀔지만 먼저 본다 (아무것도 안 바뀜)
./trim-unused-services.sh

# 2. SAFE 티어 적용
./trim-unused-services.sh --apply

# 3. 한동안 지켜보고 문제 없으면 CONDITIONAL까지
./trim-unused-services.sh --apply --with-conditional

# 4. GUI(데스크톱 이미지였을 경우)까지 끄고 싶으면
./trim-unused-services.sh --apply --with-conditional --with-gui

# 5. 뭔가 이상하면 전부 되돌리기 (서비스 + 부팅 타겟)
./trim-unused-services.sh --restore
```

적용 후 확인:

```bash
free -h
systemctl list-units --state=running | wc -l
```

## 다음에 할 일

- 오빠가 실기에서 dry-run 결과 확인 → 실제로 뭐가 켜져 있는지 (SBC마다
  이미지에 따라 SAFE 티어 항목 자체가 아예 안 깔려있을 수도 있음, 스크립트는
  설치 안 된 유닛은 자동으로 건너뜀)
- 문제 없으면 `scripts/raspberry_pi/systemd/trim-unused-services.sh`로
  저장소에 커밋하고, `README.md`에 opt-in 항목으로 링크 추가 (bringup
  systemd 유닛처럼 "선택 사항, install.sh가 자동으로 안 건드림" 패턴 유지)
- `--apply` 실행 후 다른 머신에서 `ssh <계정>@s2m.local` 접속이 실제로
  되는지 확인 (같은 로컬 네트워크에서만 동작하는 mDNS라 라우터를 넘어가는
  네트워크 구성이면 안 될 수 있음)
- 기존에 다른 이름/IP로 저장해둔 SSH config, 스크립트, 북마크가 있으면
  `s2m.local`로 갱신
- `--with-gui` dry-run으로 실기에 디스플레이 매니저가 실제로 깔려 있는지부터
  확인 — 없으면(원래 Ubuntu Server 이미지였으면) 이 티어는 아무 효과가 없다
