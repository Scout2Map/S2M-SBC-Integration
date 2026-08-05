#!/usr/bin/env bash
set -Eeuo pipefail

ROS_DISTRO=jazzy
PROFILE=onboard
WITH_VISION=0
WITH_RPLIDAR=0
BUILD_WORKSPACE=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/manifests"
WORKSPACE="${HOME}/scout2map_ws"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]
  --profile onboard|sim  Pi runtime (default) or Gazebo/RViz simulation
  --with-vision          Install ROS camera stack and ONNX Runtime environment
  --with-rplidar         Clone the official Slamtec ROS2 driver
  --repo-dir PATH        Scout2Map repository path
  --workspace PATH       Colcon workspace (default: ~/scout2map_ws)
  --no-build             Install packages without building the workspace
  -h, --help             Show help
EOF
}

log() { printf '\n[scout2map] %s\n' "$*"; }
die() { printf '[scout2map] ERROR: %s\n' "$*" >&2; exit 1; }

manifest_packages() {
  local manifest="$1"
  sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$manifest"
}

require_apt_packages() {
  local missing=()
  local package
  for package in "$@"; do
    apt-cache show "$package" >/dev/null 2>&1 || missing+=("$package")
  done
  ((${#missing[@]} == 0)) ||
    die "packages unavailable for ${VERSION_CODENAME}/${ARCH}: ${missing[*]}"
  sudo apt-get install -y "$@"
}

while (($#)); do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || die "--profile requires a value"; PROFILE="$2"; shift 2 ;;
    --with-vision) WITH_VISION=1; shift ;;
    --with-rplidar) WITH_RPLIDAR=1; shift ;;
    --repo-dir) [[ $# -ge 2 ]] || die "--repo-dir requires a path"; REPO_DIR="$(realpath "$2")"; shift 2 ;;
    --workspace) [[ $# -ge 2 ]] || die "--workspace requires a path"; WORKSPACE="$(realpath -m "$2")"; shift 2 ;;
    --no-build) BUILD_WORKSPACE=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "$PROFILE" == onboard || "$PROFILE" == sim ]] || die "profile must be onboard or sim"
[[ $EUID -ne 0 ]] || die "run as a normal user; the script invokes sudo when needed"
[[ -f /etc/os-release ]] || die "/etc/os-release was not found"
[[ -d "$REPO_DIR/src" ]] || die "Scout2Map src directory not found: $REPO_DIR/src"

REQUIRED_MANIFESTS=(
  ubuntu-base.txt
  ros-tools.txt
  ros-slam.txt
  ros-vision.txt
  ros-sim.txt
  pip-onnx.txt
)
for manifest_name in "${REQUIRED_MANIFESTS[@]}"; do
  [[ -f "$MANIFEST_DIR/$manifest_name" ]] ||
    die "package manifest not found: $MANIFEST_DIR/$manifest_name"
done

mapfile -t UBUNTU_PACKAGES < <(manifest_packages "$MANIFEST_DIR/ubuntu-base.txt")
mapfile -t ROS_TOOL_PACKAGES < <(manifest_packages "$MANIFEST_DIR/ros-tools.txt")
mapfile -t SLAM_PACKAGES < <(manifest_packages "$MANIFEST_DIR/ros-slam.txt")
mapfile -t VISION_PACKAGES < <(manifest_packages "$MANIFEST_DIR/ros-vision.txt")
mapfile -t SIM_PACKAGES < <(manifest_packages "$MANIFEST_DIR/ros-sim.txt")

# shellcheck disable=SC1091
source /etc/os-release
ARCH="$(dpkg --print-architecture)"
[[ "${ID:-}" == ubuntu ]] || die "Ubuntu is required (detected: ${ID:-unknown})"
[[ "${VERSION_ID:-}" == 24.04 ]] ||
  die "Ubuntu 24.04 is required for ROS 2 Jazzy (detected: ${VERSION_ID:-unknown})"
[[ "$ARCH" == arm64 || "$ARCH" == amd64 ]] ||
  die "arm64 or amd64 is required (detected: $ARCH)"

log "Target: Ubuntu ${VERSION_ID} ${ARCH}, ROS 2 ${ROS_DISTRO}, profile=${PROFILE}"
log "Installing Ubuntu base packages from manifests/ubuntu-base.txt"
sudo apt-get update
sudo apt-get install -y "${UBUNTU_PACKAGES[@]}"
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe

if ! dpkg-query -W ros2-apt-source >/dev/null 2>&1; then
  log "Adding the official ROS 2 apt source"
  ROS_APT_SOURCE_VERSION="$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest |
    sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  [[ -n "$ROS_APT_SOURCE_VERSION" ]] || die "could not determine ros-apt-source version"
  ROS_SOURCE_DEB="/tmp/ros2-apt-source.deb"
  curl -fL -o "$ROS_SOURCE_DEB" \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.${VERSION_CODENAME}_all.deb"
  sudo dpkg -i "$ROS_SOURCE_DEB"
fi

sudo apt-get update
log "Installing ROS build tools"
require_apt_packages "${ROS_TOOL_PACKAGES[@]}"
log "Installing SLAM, Nav2, localization and rosbag packages"
require_apt_packages "${SLAM_PACKAGES[@]}"

if ((WITH_VISION)); then
  log "Installing ROS camera and AI inference interfaces"
  require_apt_packages "${VISION_PACKAGES[@]}"
  SCOUT2MAP_SKIP_APT=1 "$SCRIPT_DIR/create_vision_venv.sh" onnx
fi
if [[ "$PROFILE" == sim ]]; then
  log "Installing Gazebo Harmonic and RViz verification packages"
  require_apt_packages "${SIM_PACKAGES[@]}"
fi
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then sudo rosdep init; fi
rosdep update --rosdistro "$ROS_DISTRO"

DEVICE_GROUPS=()
for group_name in dialout i2c video render; do
  getent group "$group_name" >/dev/null 2>&1 && DEVICE_GROUPS+=("$group_name")
done
if ((${#DEVICE_GROUPS[@]})); then
  GROUP_CSV="$(IFS=,; printf '%s' "${DEVICE_GROUPS[*]}")"
  sudo usermod -aG "$GROUP_CSV" "$USER"
fi
if command -v raspi-config >/dev/null 2>&1; then sudo raspi-config nonint do_i2c 0; fi

if ((BUILD_WORKSPACE)); then
  log "Creating workspace: $WORKSPACE"
  mkdir -p "$WORKSPACE/src"
  while IFS= read -r -d '' package_dir; do
    package_name="$(basename "$package_dir")"
    target="$WORKSPACE/src/$package_name"
    if [[ -e "$target" && ! -L "$target" ]]; then
      printf '[scout2map] Keeping existing package: %s\n' "$target"
    else
      ln -sfn "$package_dir" "$target"
    fi
  done < <(find "$REPO_DIR/src" -mindepth 1 -maxdepth 1 -type d -print0)

  if [[ -f "$REPO_DIR/dependencies.repos" ]]; then
    log "Importing pinned Scout2Map Hardware and MCU bridge dependencies"
    vcs import "$WORKSPACE/src" < "$REPO_DIR/dependencies.repos"
  fi

  if ((WITH_RPLIDAR)); then "$SCRIPT_DIR/install_rplidar.sh" "$WORKSPACE"; fi

  # ROS-generated setup scripts may read unset tracing variables.
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u
  if [[ "$PROFILE" == onboard ]]; then
    rosdep install --from-paths "$WORKSPACE/src" --ignore-src -r -y \
      --rosdistro "$ROS_DISTRO" \
      --skip-keys="ros_gz_sim ros_gz_bridge rviz2"
  else
    rosdep install --from-paths "$WORKSPACE/src" --ignore-src -r -y --rosdistro "$ROS_DISTRO"
  fi
  cd "$WORKSPACE"
  colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
fi

ENV_FILE="${HOME}/scout2map_env.sh"
cat >"$ENV_FILE" <<EOF
#!/usr/bin/env bash
source /opt/ros/${ROS_DISTRO}/setup.bash
if [ -f "${WORKSPACE}/install/setup.bash" ]; then
  source "${WORKSPACE}/install/setup.bash"
fi
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
export SCOUT2MAP_REPO="${REPO_DIR}"
export SCOUT2MAP_WS="${WORKSPACE}"
export SCOUT2MAP_DATA_DIR="${HOME}/scout2map_data"
export SCOUT2MAP_VISION_VENV="${HOME}/scout2map_venvs/vision"
EOF
chmod +x "$ENV_FILE"
if ! grep -Fq 'source "$HOME/scout2map_env.sh"' "${HOME}/.bashrc" 2>/dev/null; then
  printf '\n# Scout2Map ROS 2 environment\nsource "$HOME/scout2map_env.sh"\n' >>"${HOME}/.bashrc"
fi

CHECK_ARGS=(--profile "$PROFILE" --workspace "$WORKSPACE")
((WITH_VISION)) && CHECK_ARGS+=(--with-vision)
"$SCRIPT_DIR/check_compatibility.sh" "${CHECK_ARGS[@]}" || true
printf '\nInstallation finished. Reboot for device groups to take effect: sudo reboot\n'
