# 브릿지 센서 이벤트의 지도 마커 좌표 — 임시 통합 결정

이 문서는 2026-08-05 회의의 좌표 연결 질문에 대한 SBC 통합 결정 기록이다.
최종 메시지 schema는 `S2M-MCU_Bridge_Node`, 좌표 변환·marker 구현은 이 저장소의
향후 event/map ROS 패키지가 소유한다. 이 결정은 MCU wire protocol 자체가 아니다.

## 현재 메시지에서 바로 결정할 수 없는 점

현재 `S2M-MCU_Bridge_Node@f373787`의 `EnvSnapshot.header.stamp`는 snapshot을
발행한 ROS 시각이다. 각 센서는 서로 다른 시각에 수신된 cache 값이고 실제 나이는
`ambient_age_s`, `illuminance_age_s`, `air_quality_age_s`,
`particulate_age_s`에 들어간다. 유효 cache도 센서별로 수초까지 오래될 수 있다.

따라서 snapshot stamp만으로 `map <- base_link`를 조회하면 “이벤트 센서값이
채취된 위치”가 아니라 더 늦은 snapshot 발행 위치를 얻는다. 기존 브릿지 문서의
10~30ms 추정은 개별 USB line 전송 지연에 관한 값이며 cache age에는 적용되지 않는다.

## 권장 최종 결정

`EnvSnapshot`에 센서 그룹별 acquisition 또는 bridge-receive stamp를 추가한 뒤,
**실제로 이벤트를 발생시킨 센서 그룹의 stamp에서 `base_link` 원점을 `map`으로
변환**한다.

```text
triggering sensor sample stamp
          |
          v
TF lookup: map <- base_link at sample stamp
          |
          v
event {sample_stamp, map_id, x, y, yaw, source_frame, source_sequence}
```

환경 센서 묶음의 장착 위치 차이는 현재 지도 해상도에서 의미가 작으므로 마커 대표
위치는 `base_link`를 사용하고, 원래 `header.frame_id`는 source metadata로 보존한다.

## 메시지 변경 전 임시 fallback

1. 이벤트를 발생시킨 센서 그룹을 먼저 결정하고 해당 `*_valid`가 true인지 확인한다.
2. `estimated_sample_stamp = snapshot.header.stamp - relevant_age_s`로 근사한다.
3. `tf2_ros.Buffer.lookup_transform("map", "base_link", estimated_sample_stamp,
   timeout)`을 사용한다.
4. TF가 없으면 최신 pose로 조용히 대체하지 않고 `coordinate_status=unresolved`로
   적재해 재처리한다.
5. 지도/pose graph UUID 또는 hash를 `map_id`로 함께 저장해 서로 다른 지도를
   같은 좌표 평면으로 섞지 않는다.
6. UI가 TF를 다시 추정하지 않고 map 좌표를 확정한 ROS node만 marker를 발행한다.

이 fallback은 `age_s` 양자화와 ROS/MCU clock 차이를 포함한 근사다. 센서별 stamp
schema, map-marker node, rosbag 정확도 시험이 끝나기 전에는 좌표 과제를 완료로
표시하지 않는다.
