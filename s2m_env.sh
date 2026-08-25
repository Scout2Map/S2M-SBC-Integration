#!/usr/bin/env bash

S2M_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source /opt/ros/jazzy/setup.bash
source "${S2M_REPO_DIR}/ws/install/setup.bash"

export ROS_DOMAIN_ID=42
export SCOUT2MAP_REPO="${S2M_REPO_DIR}"
export SCOUT2MAP_WS="${S2M_REPO_DIR}/ws"

unset S2M_REPO_DIR
