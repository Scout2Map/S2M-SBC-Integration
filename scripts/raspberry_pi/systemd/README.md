# 부팅 시 자동 실행 (선택)

`install.sh`는 ROS 스택을 설치만 하고, 실행은 `ros2 launch ...`를 손으로 치는
전제다. 로봇이 켜지면 SSH 없이 바로 스택이 올라오길 원하면
`scout2map-bringup.service.example`을 systemd 서비스로 등록한다.

**기본값은 설치 안 함이다.** `install.sh`가 이 파일을 자동으로 건드리지 않는다 —
로봇이 부팅만 해도 뭔가 알아서 움직이길 원치 않는 사람도 있을 것이기 때문이다.
다만 이 서비스 자체는 주행을 자동으로 시작시키지 않는다:
`ExecStart`는 `s2m_slam_real.launch.py`를 `use_nav2:=true use_return_home:=true`로
실행하는데 — 이게 실제로 매일 쓰는 명령이다 — ROS 그래프만 올릴 뿐 `cmd_vel_safety_gate`는
`/return_home/capture_start` + `/return_home/arm`을 명시적으로 호출하기 전까지
계속 차단 상태다(최상위 README의 "실차 자동 복귀와 안전 게이트" 참고). 즉 이
서비스를 켜둬도 로봇이 부팅만으로 스스로 움직이지는 않는다 — 그저 관제 웹(웹
관제는 `scout2map_comm`이 같은 launch에 포함돼 있어서 함께 뜬다)에 접속했을 때
이미 SLAM/Nav2/이벤트가 다 올라와 있는 상태로 시작하는 것뿐이다.

평소에 `map_id`, `use_vision` 같은 다른 플래그도 같이 붙여서 실행한다면
`ExecStart` 줄에 그것도 추가해야 한다 — 이 서비스는 SLAM+Nav2+복귀+comm_relay가
뜨는 데 필요한 최소 플래그만 넣어뒀다.

## 설치

```bash
sudo cp scout2map-bringup.service.example \
  /etc/systemd/system/scout2map-bringup.service
sudo $EDITOR /etc/systemd/system/scout2map-bringup.service   # User=/HOME= 값을 실제 계정으로 수정
sudo systemctl daemon-reload
sudo systemctl enable --now scout2map-bringup.service
```

## 확인·중지

```bash
journalctl -u scout2map-bringup.service -f     # 로그 실시간 확인
sudo systemctl stop scout2map-bringup.service  # 잠깐 끄고 ros2 launch를 손으로 실행하고 싶을 때
sudo systemctl disable scout2map-bringup.service  # 부팅 자동 실행 자체를 끔
```

## 주의

- `User`/`HOME`을 `install.sh`를 실행한 실제 계정으로 바꿔야 한다(기본값 `pi`는
  예시일 뿐).
- udev 심볼릭 링크(`/dev/scout2map_*`)가 뜨기 전에 launch가 시작되지 않도록
  `ExecStartPre=/bin/sleep 5`로 살짝 지연을 준다 — 그래도 USB 허브 구성에 따라
  더 필요하면 값을 늘린다.
- 서비스가 죽으면 5초 후 자동 재시작(`Restart=on-failure`)한다. 의도적으로 끄고
  싶을 때는 `systemctl stop`을 쓰지 `pkill`로 죽이지 않는다(재시작돼 버린다).
