#!/usr/bin/env bash
set -uo pipefail

ROS_DISTRO=jazzy
PROFILE=onboard
WORKSPACE="${HOME}/scout2map_ws"
FAILURES=0
WARNINGS=0

usage() { printf 'Usage: %s [--profile onboard|sim] [--workspace PATH]\n' "$0"; }
while (($#)); do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || exit 2; PROFILE="$2"; shift 2 ;;
    --workspace) [[ $# -ge 2 ]] || exit 2; WORKSPACE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '[FAIL] %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
check_command() {
  command -v "$1" >/dev/null 2>&1 && pass "command: $1" || fail "missing command: $1"
}
check_ros_package() {
  ros2 pkg prefix "$1" >/dev/null 2>&1 && pass "ROS package: $1" || fail "missing ROS package: $1"
}

printf 'Scout2Map compatibility check\n'
printf 'Profile: %s | Workspace: %s\n\n' "$PROFILE" "$WORKSPACE"

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]]; then
    pass "OS: ${PRETTY_NAME:-Ubuntu 24.04}"
  else
    fail "Ubuntu 24.04 required (detected: ${PRETTY_NAME:-unknown})"
  fi
else
  fail "/etc/os-release not found"
fi

ARCH="$(dpkg --print-architecture 2>/dev/null || printf unknown)"
[[ "$ARCH" == arm64 || "$ARCH" == amd64 ]] && pass "architecture: $ARCH" || fail "unsupported architecture: $ARCH"

if [[ -r /proc/device-tree/model ]]; then
  MODEL="$(tr -d '\0' </proc/device-tree/model)"
  [[ "$MODEL" == *"Raspberry Pi 5"* ]] && pass "board: $MODEL" || warn "board is not Raspberry Pi 5: $MODEL"
else
  warn "Raspberry Pi model data unavailable (normal on WSL/PC)"
fi

MEM_KB="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)"
if [[ "$MEM_KB" =~ ^[0-9]+$ ]]; then
  ((MEM_KB >= 7000000)) && pass "memory: $((MEM_KB / 1024 / 1024)) GiB class" ||
    warn "memory below 8 GB class; simultaneous SLAM/Nav2/vision may be constrained"
fi
FREE_KB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
if [[ "$FREE_KB" =~ ^[0-9]+$ ]]; then
  ((FREE_KB >= 15000000)) && pass "free storage: $((FREE_KB / 1024 / 1024)) GiB" ||
    warn "less than 15 GB free; rosbag, maps and AI models can exhaust storage"
fi

for command_name in python3 colcon rosdep git; do check_command "$command_name"; done

if [[ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u
  pass "ROS 2 $ROS_DISTRO environment"
else
  fail "missing /opt/ros/$ROS_DISTRO/setup.bash"
fi

if [[ -f "$WORKSPACE/install/setup.bash" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$WORKSPACE/install/setup.bash"
  set -u
  pass "workspace overlay"
else
  fail "workspace has not been built: $WORKSPACE/install/setup.bash"
fi

for package_name in rclpy nav2_bringup slam_toolbox \
  s2m_bringup s2m_description scout_gas scout2map_bridge scout2map_msgs \
  scout2map_event scout_vision explore_lite; do
  check_ros_package "$package_name"
done
if [[ "$PROFILE" == sim ]]; then
  for package_name in rviz2 ros_gz_sim ros_gz_bridge; do
    check_ros_package "$package_name"
  done
fi
python3 -c 'import yaml, serial' >/dev/null 2>&1 &&
  pass "Python YAML and serial imports" || fail "Python cannot import yaml and serial"

if compgen -G '/dev/ttyUSB*' >/dev/null || compgen -G '/dev/ttyACM*' >/dev/null; then
  pass "USB serial device detected"
else
  warn "no USB serial device; connect RPLIDAR/MCU and rerun"
fi
# Every I2C sensor sits behind an MCU, so the Pi needs no /dev/i2c-* node.
# What matters is that the udev rules resolved to stable names.
if [[ "$PROFILE" == onboard ]]; then
  for device_path in /dev/scout2map_pico /dev/scout2map_drive /dev/scout2map_lidar; do
    if [[ -e "$device_path" ]]; then
      pass "device symlink: $device_path -> $(readlink -f "$device_path")"
    else
      warn "missing device symlink: $device_path (check udev rules and replug)"
    fi
  done
  id -nG "$USER" | tr ' ' '\n' | grep -qx dialout &&
    pass "user is in the dialout group" ||
    fail "user is not in the dialout group; serial ports will not open"
fi

if command -v vcgencmd >/dev/null 2>&1; then
  THROTTLED="$(vcgencmd get_throttled 2>/dev/null || true)"
  [[ "$THROTTLED" == 'throttled=0x0' ]] && pass "Pi power/thermal flags: clear" ||
    warn "Pi reports power/thermal flags: ${THROTTLED:-unknown}"
fi

printf '\nResult: %d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
((FAILURES == 0))
