#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HEADLESS=false

if [[ "${1:-}" == "--headless" ]]; then
  HEADLESS=true
elif [[ $# -gt 0 ]]; then
  printf 'Usage: %s [--headless]\n' "$0" >&2
  exit 2
fi

# ROS setup scripts may inspect variables which are unset in a clean shell.
set +u
source "${REPO_DIR}/s2m_env.sh"
set -u

if [[ "$HEADLESS" == true ]]; then
  exec ros2 launch s2m_bringup s2m_return_home_sim.launch.py \
    headless:=true use_rviz:=false
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  printf 'No GUI display detected. Use --headless or configure DISPLAY.\n' >&2
  exit 1
fi

exec ros2 launch s2m_bringup s2m_return_home_sim.launch.py \
  headless:=false use_rviz:=true
