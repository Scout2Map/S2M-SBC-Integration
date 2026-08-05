#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${1:-${HOME}/scout2map_ws}"
SOURCE_DIR="${WORKSPACE}/src/sllidar_ros2"
RPLIDAR_COMMIT="34300099fadfc772965962dec837bf436706188f"

if [[ -e "$SOURCE_DIR" ]]; then
  if [[ -d "$SOURCE_DIR/.git" ]]; then
    CURRENT_COMMIT="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
    if [[ "$CURRENT_COMMIT" == "$RPLIDAR_COMMIT" ]]; then
      printf '[scout2map] Pinned sllidar_ros2 checkout already present at %s\n' "$SOURCE_DIR"
      exit 0
    fi
    printf '[scout2map] ERROR: existing sllidar_ros2 is at %s, expected %s\n' \
      "$CURRENT_COMMIT" "$RPLIDAR_COMMIT" >&2
    printf '[scout2map] Move or update that checkout explicitly before rerunning.\n' >&2
    exit 1
  fi
  printf '[scout2map] ERROR: %s exists but is not a git checkout\n' "$SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$WORKSPACE/src"
git init "$SOURCE_DIR"
git -C "$SOURCE_DIR" remote add origin https://github.com/Slamtec/sllidar_ros2.git
git -C "$SOURCE_DIR" fetch --depth 1 origin "$RPLIDAR_COMMIT"
git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD
printf '[scout2map] RPLIDAR driver cloned; the main installer will build it.\n'
printf '[scout2map] Access uses the dialout group; do not chmod 777 /dev/ttyUSB*.\n'
