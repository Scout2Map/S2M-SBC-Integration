# Release Notes

## V1.0.5 - 2026-08-18

### 변경

- `s2m_return_home_real.launch.py`를 추가해 실차 Nav2와 teleop 명령이 단일
  `cmd_vel_safety_gate`를 통과하도록 구성했다.
- `s2m_slam_real.launch.py`에 Nav2 출력 토픽 remap, Event Engine 조건부 실행,
  mapping session `map_id` 인자를 추가했다.
- 실차 자동 복귀는 자동 출발점 저장과 자동 무장을 끄고 operator 확인 후 서비스로
  활성화하도록 분리했다.
- 제거된 설치 옵션 문서를 수정하고, 이름이 바뀐 MCU Bridge 원격 저장소를 기존
  workspace에서 자동 이관하도록 설치 스크립트를 보완했다.
- MCU 토픽 검사를 정확한 토픽 이름으로 일치시키고 미구현 `robot_localization`을
  필수 검사 대상에서 제외했다.
- Nav2 costmap의 `robot_radius`를 문서와 동일한 0.22 m로 맞추고 LiDAR udev 링크가
  없을 때 `/dev/ttyUSB0`을 실제 기본값으로 선택하게 했다.
- `/cmd_val`은 오타이며 프로젝트의 주행 명령 계약은 `/cmd_vel`임을 명시했다.
- Bridge V2.1.0의 `skid_factor` 보정 절차와 `DriveStatus.link_ok`의 실제 의미를
  문서화했다.

### 검증

- WSL Ubuntu 24.04, ROS 2 Jazzy에서 6개 패키지 통합 빌드 성공
- `s2m_slam_real.launch.py`, `s2m_return_home_real.launch.py` 인자 해석 성공
- return_home 정책 단위 시험 5개 통과
- 장치 비활성 smoke launch에서 최종 `/cmd_vel` 발행자 1개 확인
- Python/XML/YAML/Markdown 정적 검사와 설치 스크립트 Bash 구문 검사 통과

### 보류

Event Engine V1.1.0의 sensor history와 온도 예측은 Python 의존성 선언, DB API,
보존 정책과 실 ROS 검증이 완료된 후 통합한다. 현재 `dependencies.repos`는 이벤트
계약이 검증된 `7013a22`를 유지한다.
