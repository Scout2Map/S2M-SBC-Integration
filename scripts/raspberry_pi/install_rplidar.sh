#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${1:-${HOME}/scout2map_ws}"
SOURCE_DIR="${WORKSPACE}/src/sllidar_ros2"

if [[ -e "$SOURCE_DIR" ]]; then
  if [[ -d "$SOURCE_DIR/.git" ]]; then
    printf '[scout2map] Existing sllidar_ros2 checkout kept at %s\n' "$SOURCE_DIR"
    printf '[scout2map] Update manually with: git -C %q pull --ff-only\n' "$SOURCE_DIR"
    exit 0
  fi
  printf '[scout2map] ERROR: %s exists but is not a git checkout\n' "$SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$WORKSPACE/src"
git clone --depth 1 https://github.com/Slamtec/sllidar_ros2.git "$SOURCE_DIR"
printf '[scout2map] RPLIDAR driver cloned; the main installer will build it.\n'
printf '[scout2map] Access uses the dialout group; do not chmod 777 /dev/ttyUSB*.\n'
