#!/usr/bin/env bash
set -uo pipefail

SENSOR_DEVICE="${SCOUT2MAP_SENSOR_MCU_DEVICE:-/dev/scout2map_pico}"
MOTOR_DEVICE="${SCOUT2MAP_MOTOR_MCU_DEVICE:-/dev/scout2map_drive}"
# s2m_onboard_bridge.launch.py remaps drive/odom and drive/imu onto these by
# default. Override when robot_localization takes ownership of /odom.
ODOM_TOPIC="${SCOUT2MAP_ODOM_TOPIC:-/odom}"
IMU_TOPIC="${SCOUT2MAP_IMU_TOPIC:-/imu/data}"
BASE_FRAME="${SCOUT2MAP_BASE_FRAME:-base_link}"
# Seconds the CLI waits for graph discovery before reporting. Raise it on a
# loaded SBC or a noisy network.
DISCOVERY_SPIN_TIME="${SCOUT2MAP_DISCOVERY_SPIN_TIME:-3}"
REQUIRE_SENSOR=0
REQUIRE_MOTOR=0
FAILURES=0
WARNINGS=0

usage() {
  cat <<'EOF'
Usage: ./check_mcu_interfaces.sh [options]
  --sensor-device PATH  Pico 2 USB CDC device (default: /dev/scout2map_pico)
  --motor-device PATH   Drive MCU USB CDC device (default: /dev/scout2map_drive)
  --odom-topic NAME     Wheel odometry topic (default: /odom)
  --imu-topic NAME      Drive MCU IMU topic (default: /imu/data)
  --spin-time SECONDS   Graph discovery wait (default: 3)
  --require-sensor      Treat missing sensor topics as failures
  --require-motor       Treat missing motor topics as failures
EOF
}

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '[FAIL] %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

while (($#)); do
  case "$1" in
    --sensor-device) [[ $# -ge 2 ]] || exit 2; SENSOR_DEVICE="$2"; shift 2 ;;
    --motor-device) [[ $# -ge 2 ]] || exit 2; MOTOR_DEVICE="$2"; shift 2 ;;
    --odom-topic) [[ $# -ge 2 ]] || exit 2; ODOM_TOPIC="$2"; shift 2 ;;
    --imu-topic) [[ $# -ge 2 ]] || exit 2; IMU_TOPIC="$2"; shift 2 ;;
    --spin-time) [[ $# -ge 2 ]] || exit 2; DISCOVERY_SPIN_TIME="$2"; shift 2 ;;
    --require-sensor) REQUIRE_SENSOR=1; shift ;;
    --require-motor) REQUIRE_MOTOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

if [[ -f "${HOME}/scout2map_env.sh" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "${HOME}/scout2map_env.sh"
  set -u
elif [[ -r /opt/ros/jazzy/setup.bash ]]; then
  set +u
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  set -u
fi

check_device() {
  local label="$1"
  local device="$2"
  local required="$3"
  if [[ -z "$device" ]]; then
    ((required)) && fail "$label device was not specified" || warn "$label device was not specified"
  elif [[ -e "$device" ]]; then
    pass "$label device: $device -> $(readlink -f "$device")"
  else
    ((required)) && fail "$label device not found: $device" || warn "$label device not found: $device"
  fi
}

# One discovery pass for the whole run. Calling `ros2 topic type` per topic
# spawns a fresh node each time and each gets only a moment to discover the
# graph, so results come back inconsistent on a busy machine.
TOPIC_SNAPSHOT=''

snapshot_topics() {
  TOPIC_SNAPSHOT="$(ros2 topic list -t --spin-time "$DISCOVERY_SPIN_TIME" 2>/dev/null)"
  if [[ -z "$TOPIC_SNAPSHOT" ]]; then
    warn 'no topics discovered; is a bridge running and ROS_DOMAIN_ID matching?'
  fi
}

check_topic() {
  local topic="$1"
  local expected_type="$2"
  local required="$3"
  local line
  local actual_type
  # `ros2 topic list -t` prints: /topic [pkg/msg/Type]
  line="$(grep -m1 -F -- "$topic [" <<<"$TOPIC_SNAPSHOT")"
  actual_type="${line#*[}"
  actual_type="${actual_type%]}"
  if [[ -z "$line" ]]; then
    ((required)) && fail "missing topic: $topic" || warn "missing topic: $topic"
  elif [[ "$actual_type" == "$expected_type" ]]; then
    pass "topic: $topic ($actual_type)"
  else
    fail "topic type mismatch: $topic expected $expected_type, got $actual_type"
  fi
}

check_frame() {
  local frame="$1"
  local required="$2"
  local output
  if ! command -v ros2 >/dev/null 2>&1; then
    return
  fi
  # tf2_echo never exits on its own, so match on its output instead of $?
  output="$(timeout 5 ros2 run tf2_ros tf2_echo "$BASE_FRAME" "$frame" 2>/dev/null | head -n 40)"
  if grep -q 'Translation' <<<"$output"; then
    pass "TF: $BASE_FRAME -> $frame"
  else
    ((required)) && fail "missing TF: $BASE_FRAME -> $frame" ||
      warn "missing TF: $BASE_FRAME -> $frame"
  fi
}

printf 'Scout2Map MCU interface check\n\n'
command -v ros2 >/dev/null 2>&1 && pass 'command: ros2' || fail 'missing command: ros2'

check_device 'sensor MCU' "$SENSOR_DEVICE" "$REQUIRE_SENSOR"
check_device 'motor MCU' "$MOTOR_DEVICE" "$REQUIRE_MOTOR"

if command -v ros2 >/dev/null 2>&1; then
  ros2 pkg prefix scout2map_bridge >/dev/null 2>&1 && pass 'ROS package: scout2map_bridge' ||
    fail 'scout2map_bridge is not installed or not sourced'
  ros2 pkg prefix scout2map_msgs >/dev/null 2>&1 && pass 'ROS package: scout2map_msgs' ||
    fail 'scout2map_msgs is not installed or not sourced'

  snapshot_topics

  # Sensor fusion MCU contract, scout2map_bridge sensor_bridge node
  check_topic /sensors/env_snapshot scout2map_msgs/msg/EnvSnapshot "$REQUIRE_SENSOR"
  check_topic /sensors/air_quality scout2map_msgs/msg/AirQuality "$REQUIRE_SENSOR"
  check_topic /sensors/status scout2map_msgs/msg/SensorStatus "$REQUIRE_SENSOR"

  # Drive MCU contract, scout2map_bridge drive_bridge node
  check_topic /cmd_vel geometry_msgs/msg/Twist "$REQUIRE_MOTOR"
  check_topic /drive/status scout2map_msgs/msg/DriveStatus "$REQUIRE_MOTOR"
  check_topic "$ODOM_TOPIC" nav_msgs/msg/Odometry "$REQUIRE_MOTOR"
  check_topic "$IMU_TOPIC" sensor_msgs/msg/Imu "$REQUIRE_MOTOR"

  # Published by s2m_bringup drive_link_adapter, not by the bridge itself
  check_topic /drive/link_ok std_msgs/msg/Bool "$REQUIRE_MOTOR"

  # Event engine output, only present when scout2map_event is running
  check_topic /events std_msgs/msg/String 0

  # Frames the bridges stamp onto messages. sensor_fusion and range_link have
  # no URDF link, so s2m_onboard_bridge.launch.py must supply the static TF.
  check_frame sensor_fusion "$REQUIRE_SENSOR"
  check_frame range_link "$REQUIRE_MOTOR"
fi

if [[ -e "$SENSOR_DEVICE" && -e "$MOTOR_DEVICE" &&
      "$(readlink -f "$SENSOR_DEVICE" 2>/dev/null)" == "$(readlink -f "$MOTOR_DEVICE" 2>/dev/null)" ]]; then
  warn 'sensor and motor devices resolve to the same port; confirm that one MCU intentionally handles both roles'
fi

printf '\nResult: %d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
((FAILURES == 0))
