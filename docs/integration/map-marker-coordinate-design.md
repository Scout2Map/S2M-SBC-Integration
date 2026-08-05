# 센서 이벤트의 지도 마커 좌표 설계

환경 센서 이벤트가 발생한 위치를 SLAM 지도 좌표로 변환하기 위한 설계입니다. 센서
값의 취득 시각과 snapshot 발행 시각이 다를 수 있으므로 timestamp와 TF 처리 규칙을
명확히 구분합니다.

## 현재 메시지에서 바로 결정할 수 없는 점

현재 `EnvSnapshot.header.stamp`는 snapshot을 발행한 ROS 시각입니다. 각 센서는 서로
다른 시각에 수신된 cache 값이고 실제 나이는
`ambient_age_s`, `illuminance_age_s`, `air_quality_age_s`,
`particulate_age_s`에 들어간다. 유효 cache도 센서별로 수초까지 오래될 수 있다.

따라서 snapshot stamp만으로 `map <- base_link`를 조회하면 이벤트 센서값이 취득된
위치가 아니라 더 늦은 snapshot 발행 위치를 얻을 수 있습니다.

## 권장 처리

`EnvSnapshot`에 센서 그룹별 acquisition 또는 bridge-receive stamp를 추가하고,
실제로 이벤트를 발생시킨 센서 그룹의 stamp에서 `base_link` 원점을 `map`으로
변환합니다.

```text
triggering sensor sample stamp
          |
          v
TF lookup: map <- base_link at sample stamp
          |
          v
event {sample_stamp, map_id, x, y, yaw, source_frame, source_sequence}
```

환경 센서 묶음의 장착 위치 차이가 지도 해상도보다 작다면 마커 대표 위치는
`base_link`를 사용하고, 원래 `header.frame_id`는 source metadata로 보존합니다.

## 센서별 stamp 추가 전 fallback

1. 이벤트를 발생시킨 센서 그룹을 먼저 결정하고 해당 `*_valid`가 true인지 확인한다.
2. `estimated_sample_stamp = snapshot.header.stamp - relevant_age_s`로 근사한다.
3. `tf2_ros.Buffer.lookup_transform("map", "base_link", estimated_sample_stamp,
   timeout)`을 사용한다.
4. TF가 없으면 최신 pose로 조용히 대체하지 않고 `coordinate_status=unresolved`로
   적재해 재처리한다.
5. 지도/pose graph UUID 또는 hash를 `map_id`로 함께 저장해 서로 다른 지도를
   같은 좌표 평면으로 섞지 않는다.
6. UI가 TF를 다시 추정하지 않고 map 좌표를 확정한 ROS node만 marker를 발행한다.

이 fallback은 `age_s` 양자화와 ROS/MCU clock 차이를 포함한 근사입니다. 센서별
stamp, map-marker node와 rosbag 정확도 시험이 끝나기 전에는 위치 정확도가 검증된
것으로 간주하지 않습니다.
