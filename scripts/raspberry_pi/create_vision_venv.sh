#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND="${1:-onnx}"
VENV_DIR="${2:-${HOME}/scout2map_venvs/vision}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS="${SCRIPT_DIR}/manifests/pip-onnx.txt"
ROS_REQUIREMENTS="${SCRIPT_DIR}/manifests/ros-vision.txt"

case "$BACKEND" in
  opencv|onnx) ;;
  *) printf 'Usage: %s [opencv|onnx] [venv-path]\n' "$0" >&2; exit 2 ;;
esac

if [[ "${SCOUT2MAP_SKIP_APT:-0}" != 1 ]]; then
  [[ -f "$ROS_REQUIREMENTS" ]] || {
    printf 'Missing requirements file: %s\n' "$ROS_REQUIREMENTS" >&2
    exit 1
  }
  mapfile -t ROS_PACKAGES < <(
    sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$ROS_REQUIREMENTS"
  )
  sudo apt-get update
  sudo apt-get install -y "${ROS_PACKAGES[@]}"
fi

python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
if [[ "$BACKEND" == onnx ]]; then
  [[ -f "$REQUIREMENTS" ]] || {
    printf 'Missing requirements file: %s\n' "$REQUIREMENTS" >&2
    exit 1
  }
  "$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS"
fi

"$VENV_DIR/bin/python" - <<'PY'
import cv2
import numpy
print(f"OpenCV {cv2.__version__}; NumPy {numpy.__version__}")
PY

if [[ "$BACKEND" == onnx ]]; then
  "$VENV_DIR/bin/python" -c \
    'import onnxruntime as ort; print("ONNX Runtime", ort.__version__, ort.get_available_providers())'
fi
printf 'Vision environment ready: %s\n' "$VENV_DIR"
printf 'Activate with: source %q/bin/activate\n' "$VENV_DIR"
