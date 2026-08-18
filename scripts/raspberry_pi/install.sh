#!/usr/bin/env bash
# Scout2Map SBC installer.
#
# Brings a clean Ubuntu 24.04 machine to the point where this works:
#   ros2 launch s2m_bringup s2m_slam_real.launch.py
#
# Two profiles:
#   onboard  Raspberry Pi 5 on the robot. Installs udev rules, no Gazebo.
#   sim      Development laptop. Installs Gazebo and RViz, no udev rules.
#
# The script is idempotent; rerun it after changing dependencies.repos.

set -Eeuo pipefail

ROS_DISTRO=jazzy
PROFILE=onboard
BUILD_WORKSPACE=1
INSTALL_UDEV=-1
PARALLEL_WORKERS=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MANIFEST_DIR="${SCRIPT_DIR}/manifests"
UDEV_DIR="${SCRIPT_DIR}/udev"
WORKSPACE="${HOME}/scout2map_ws"

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]
  --profile onboard|sim   onboard = robot (default), sim = laptop with Gazebo
  --workspace PATH        colcon workspace (default: ~/scout2map_ws)
  --repo-dir PATH         Scout2Map repository (default: autodetected)
  --parallel-workers N    limit colcon parallelism; use 2 on a Pi 5 that swaps
  --no-build              install packages and udev rules, skip colcon build
  --no-udev               skip udev rules even on the onboard profile
  -h, --help              show this help
EOF
}

log() { printf '\n[scout2map] %s\n' "$*"; }
note() { printf '[scout2map] %s\n' "$*"; }
die() { printf '[scout2map] ERROR: %s\n' "$*" >&2; exit 1; }

# Strip comments and blank lines from a package manifest
manifest_packages() {
  sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$1"
}

# Fail with the full list of unavailable packages rather than one at a time
apt_install_checked() {
  local missing=() package
  for package in "$@"; do
    apt-cache show "$package" >/dev/null 2>&1 || missing+=("$package")
  done
  ((${#missing[@]} == 0)) ||
    die "not available for ${VERSION_CODENAME}/${ARCH}: ${missing[*]}"
  sudo apt-get install -y "$@"
}

while (($#)); do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || die "--profile requires a value"
      PROFILE="$2"; shift 2 ;;
    --workspace) [[ $# -ge 2 ]] || die "--workspace requires a path"
      WORKSPACE="$(realpath -m "$2")"; shift 2 ;;
    --repo-dir) [[ $# -ge 2 ]] || die "--repo-dir requires a path"
      REPO_DIR="$(realpath "$2")"; shift 2 ;;
    --parallel-workers) [[ $# -ge 2 ]] || die "--parallel-workers requires a number"
      PARALLEL_WORKERS="$2"; shift 2 ;;
    --no-build) BUILD_WORKSPACE=0; shift ;;
    --no-udev) INSTALL_UDEV=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

# ---------------------------------------------------------------- preflight

[[ "$PROFILE" == onboard || "$PROFILE" == sim ]] ||
  die "profile must be onboard or sim"
[[ $EUID -ne 0 ]] || die "run as a normal user; the script calls sudo itself"
[[ -d "$REPO_DIR/src" ]] || die "no src directory in repo: $REPO_DIR"
[[ -f "$REPO_DIR/dependencies.repos" ]] ||
  die "dependencies.repos not found in $REPO_DIR"

# Device symlinks only matter where the MCUs are physically attached
if ((INSTALL_UDEV == -1)); then
  [[ "$PROFILE" == onboard ]] && INSTALL_UDEV=1 || INSTALL_UDEV=0
fi

# shellcheck disable=SC1091
source /etc/os-release
ARCH="$(dpkg --print-architecture)"
[[ "${ID:-}" == ubuntu ]] || die "Ubuntu required (found: ${ID:-unknown})"
[[ "${VERSION_ID:-}" == 24.04 ]] ||
  die "ROS 2 ${ROS_DISTRO} needs Ubuntu 24.04 (found: ${VERSION_ID:-unknown})"
[[ "$ARCH" == arm64 || "$ARCH" == amd64 ]] ||
  die "arm64 or amd64 required (found: $ARCH)"

for manifest in apt-base.txt ros-tools.txt ros-onboard.txt ros-sim.txt; do
  [[ -f "$MANIFEST_DIR/$manifest" ]] || die "missing manifest: $manifest"
done

log "Ubuntu ${VERSION_ID} ${ARCH} | ROS 2 ${ROS_DISTRO} | profile ${PROFILE}"
note "repo:      $REPO_DIR"
note "workspace: $WORKSPACE"

# ---------------------------------------------------------------- apt setup

log "Installing base system packages"
sudo apt-get update
mapfile -t APT_BASE < <(manifest_packages "$MANIFEST_DIR/apt-base.txt")
sudo apt-get install -y "${APT_BASE[@]}"

sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe

if ! dpkg-query -W ros2-apt-source >/dev/null 2>&1; then
  log "Adding the ROS 2 apt source"
  ROS_APT_VERSION="$(curl -fsSL \
    https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest |
    sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  [[ -n "$ROS_APT_VERSION" ]] || die "could not resolve ros-apt-source version"
  curl -fL -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_VERSION}/ros2-apt-source_${ROS_APT_VERSION}.${VERSION_CODENAME}_all.deb"
  sudo dpkg -i /tmp/ros2-apt-source.deb
fi

sudo apt-get update

log "Installing ROS build tooling"
mapfile -t ROS_TOOLS < <(manifest_packages "$MANIFEST_DIR/ros-tools.txt")
apt_install_checked "${ROS_TOOLS[@]}"

log "Installing the onboard ROS stack"
mapfile -t ROS_ONBOARD < <(manifest_packages "$MANIFEST_DIR/ros-onboard.txt")
apt_install_checked "${ROS_ONBOARD[@]}"

if [[ "$PROFILE" == sim ]]; then
  log "Installing Gazebo Harmonic and RViz"
  mapfile -t ROS_SIM < <(manifest_packages "$MANIFEST_DIR/ros-sim.txt")
  apt_install_checked "${ROS_SIM[@]}"
fi

if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  sudo rosdep init
fi
rosdep update --rosdistro "$ROS_DISTRO"

# ---------------------------------------------------------------- device access

# Serial ports are group-owned by dialout. Never chmod 777 a tty.
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  log "Adding $USER to the dialout group"
  sudo usermod -aG dialout "$USER"
  NEEDS_RELOGIN=1
fi

if ((INSTALL_UDEV)); then
  log "Installing udev rules"
  # The MCU bridge repository ships an overlapping rule file. Two rules
  # matching one device leaves the resulting mode arbitrary, so only the
  # copy in this repository is installed.
  for pair in \
    "99-scout2map-usb.rules.example:99-scout2map-usb.rules" \
    "99-scout2map-lidar.rules.example:99-scout2map-lidar.rules"; do
    src_name="${pair%%:*}"
    dst_name="${pair##*:}"
    if [[ -f "$UDEV_DIR/$src_name" ]]; then
      sudo install -m 0644 "$UDEV_DIR/$src_name" "/etc/udev/rules.d/$dst_name"
      note "installed /etc/udev/rules.d/$dst_name"
    else
      note "WARNING: udev template not found: $src_name"
    fi
  done
  sudo udevadm control --reload-rules
  sudo udevadm trigger
fi

# ---------------------------------------------------------------- workspace

if ((BUILD_WORKSPACE)); then
  log "Linking repository packages into $WORKSPACE/src"
  mkdir -p "$WORKSPACE/src"
  while IFS= read -r -d '' package_dir; do
    package_name="$(basename "$package_dir")"
    target="$WORKSPACE/src/$package_name"
    if [[ -e "$target" && ! -L "$target" ]]; then
      note "keeping existing non-symlink package: $target"
    else
      ln -sfn "$package_dir" "$target"
    fi
  done < <(find "$REPO_DIR/src" -mindepth 1 -maxdepth 1 -type d -print0)

  # Pulls the hardware description, the MCU bridge, the event engine and the
  # LiDAR driver at their pinned commits.
  log "Importing pinned dependencies"
  BRIDGE_CHECKOUT="$WORKSPACE/src/s2m_mcu_bridge_node"
  if [[ -d "$BRIDGE_CHECKOUT/.git" ]]; then
    BRIDGE_REMOTE="$(git -C "$BRIDGE_CHECKOUT" remote get-url origin 2>/dev/null || true)"
    case "$BRIDGE_REMOTE" in
      *S2M-MCU_Bridge_Node.git*)
        note "migrating renamed MCU bridge remote"
        git -C "$BRIDGE_CHECKOUT" remote set-url origin \
          https://github.com/Scout2Map/S2M-MCU-BridgeNode.git
        ;;
    esac
  fi
  vcs import "$WORKSPACE/src" < "$REPO_DIR/dependencies.repos"

  [[ -d "$WORKSPACE/src/sllidar_ros2" ]] ||
    note "WARNING: sllidar_ros2 missing; /scan will not be published"

  # ROS setup scripts read variables that may be unset under `set -u`
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u

  log "Resolving package dependencies with rosdep"
  ROSDEP_ARGS=(--from-paths "$WORKSPACE/src" --ignore-src -r -y
               --rosdistro "$ROS_DISTRO")
  if [[ "$PROFILE" == onboard ]]; then
    # Gazebo and RViz are deliberately absent from the robot
    ROSDEP_ARGS+=(--skip-keys "ros_gz_sim ros_gz_bridge rviz2")
  fi
  rosdep install "${ROSDEP_ARGS[@]}"

  log "Building the workspace"
  BUILD_ARGS=(--symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release)
  if [[ -n "$PARALLEL_WORKERS" ]]; then
    BUILD_ARGS=(--parallel-workers "$PARALLEL_WORKERS" "${BUILD_ARGS[@]}")
  fi
  cd "$WORKSPACE"
  colcon build "${BUILD_ARGS[@]}"
fi

# ---------------------------------------------------------------- environment

ENV_FILE="${HOME}/scout2map_env.sh"
cat >"$ENV_FILE" <<EOF
#!/usr/bin/env bash
source /opt/ros/${ROS_DISTRO}/setup.bash
if [ -f "${WORKSPACE}/install/setup.bash" ]; then
  source "${WORKSPACE}/install/setup.bash"
fi
# Keep the robot and the laptop on the same domain so RViz can attach
export ROS_DOMAIN_ID=42
export SCOUT2MAP_REPO="${REPO_DIR}"
export SCOUT2MAP_WS="${WORKSPACE}"
EOF
chmod +x "$ENV_FILE"

if ! grep -Fq 'source "$HOME/scout2map_env.sh"' "${HOME}/.bashrc" 2>/dev/null; then
  printf '\n# Scout2Map ROS 2 environment\nsource "$HOME/scout2map_env.sh"\n' \
    >>"${HOME}/.bashrc"
fi

# ---------------------------------------------------------------- summary

log "Installation finished"
note "Environment file: $ENV_FILE"
printf '\nNext steps:\n'
if [[ -n "${NEEDS_RELOGIN:-}" ]]; then
  printf '  1. Reboot so the dialout group takes effect: sudo reboot\n'
else
  printf '  1. source ~/scout2map_env.sh\n'
fi
if ((INSTALL_UDEV)); then
  printf '  2. Replug the MCUs and LiDAR, then confirm the symlinks:\n'
  printf '       ls -l /dev/scout2map_pico /dev/scout2map_drive /dev/scout2map_lidar\n'
  printf '     If one is missing, compare its IDs against the rule file:\n'
  printf '       udevadm info --query=property --name=/dev/ttyACM0\n'
  printf '  3. ./scripts/raspberry_pi/check_compatibility.sh --profile %s\n' "$PROFILE"
  printf '  4. ros2 launch s2m_bringup s2m_slam_real.launch.py\n'
else
  printf '  2. ./scripts/raspberry_pi/check_compatibility.sh --profile %s\n' "$PROFILE"
  printf '  3. ros2 launch s2m_bringup s2m_slam_sim.launch.py\n'
fi
