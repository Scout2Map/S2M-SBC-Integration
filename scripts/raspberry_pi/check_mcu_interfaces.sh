#!/usr/bin/env bash
set -uo pipefail

SENSOR_DEVICE="${SCOUT2MAP_SENSOR_MCU_DEVICE:-/dev/scout2map_pico}"
MOTOR_DEVICE="${SCOUT2MAP_MOTOR_MCU_DEVICE:-/dev/scout2map_drive}"
REQUIRE_SENSOR=0
REQUIRE_MOTOR=0
FAILURES=0
WARNINGS=0

usage() {
  cat <<'EOF'
Usage: ./check_mcu_interfaces.sh [options]
  --sensor-device PATH  Pico 2 USB CDC device (default: /dev/scout2map_pico)
  --motor-device PATH   Drive MCU USB CDC device (default: /dev/scout2map_drive)
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

check_topic() {
  local topic="$1"
  local expected_type="$2"
  local required="$3"
  local actual_type
  actual_type="$(ros2 topic type "$topic" 2>/dev/null | head -n 1)"
  if [[ -z "$actual_type" ]]; then
    ((required)) && fail "missing topic: $topic" || warn "missing topic: $topic"
  elif [[ "$actual_type" == "$expected_type" ]]; then
    pass "topic: $topic ($actual_type)"
  else
    fail "topic type mismatch: $topic expected $expected_type, got $actual_type"
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

  check_topic /sensors/env_snapshot scout2map_msgs/msg/EnvSnapshot "$REQUIRE_SENSOR"
  check_topic /bridge/status scout2map_msgs/msg/BridgeStatus "$REQUIRE_SENSOR"
  check_topic /cmd_vel geometry_msgs/msg/Twist "$REQUIRE_MOTOR"
  check_topic /wheel/odom nav_msgs/msg/Odometry "$REQUIRE_MOTOR"
  if ((REQUIRE_MOTOR == 0)); then
    warn 'the referenced bridge repository has no STM32 drive bridge yet; motor topics are provisional'
  fi
fi

if [[ -e "$SENSOR_DEVICE" && -e "$MOTOR_DEVICE" &&
      "$(readlink -f "$SENSOR_DEVICE" 2>/dev/null)" == "$(readlink -f "$MOTOR_DEVICE" 2>/dev/null)" ]]; then
  warn 'sensor and motor devices resolve to the same port; confirm that one MCU intentionally handles both roles'
fi

printf '\nResult: %d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
((FAILURES == 0))
