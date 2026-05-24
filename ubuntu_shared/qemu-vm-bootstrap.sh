#!/usr/bin/env bash
# Run ON the new QEMU Ubuntu VM (no robot/camera required).
# Paste or: curl/bash from Mac after rsync, or copy via shared folder.
set -euo pipefail

echo "=== base packages ==="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  git curl wget rsync \
  python3 python3-venv python3-pip \
  can-utils usbutils net-tools \
  libgl1 libglib2.0-0

echo "=== uv (Python 3.12 for mediapipe on Ubuntu 26) ==="
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

LIGHTSABER="${LIGHTSABER_DIR:-$HOME/piper-vision-hackathon/projects/lightsaber}"
SHARED="${SHARED_DIR:-$HOME/piper-vision-hackathon/projects/shared}"
mkdir -p "$(dirname "$LIGHTSABER")"

if [[ ! -f "$LIGHTSABER/main.py" ]]; then
  echo "=== waiting for lightsaber code ==="
  echo "From Mac (other terminal), run:"
  echo "  rsync -az --exclude .venv --exclude __pycache__ \\"
  echo "    ~/Projects/piper-vision-hackathon/projects/lightsaber/ \\"
  echo "    philip@192.168.64.4:~/piper-vision-hackathon/projects/lightsaber/"
  echo "  rsync -az ~/Projects/piper-vision-hackathon/projects/shared/ \\"
  echo "    philip@192.168.64.4:~/piper-vision-hackathon/projects/shared/"
  exit 1
fi

cd "$LIGHTSABER"
rm -rf .venv
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
uv pip uninstall opencv-python opencv-contrib-python 2>/dev/null || true
uv pip install opencv-python-headless

.venv/bin/python -m unittest tests.test_contracts -q
.venv/bin/python robot_smoke.py
.venv/bin/python robot_discover.py || true

echo ""
echo "OK — software ready. When robot is plugged in:"
echo "  UTM USB → attach candleLight"
echo "  bash ~/piper-vision-hackathon/projects/lightsaber/ubuntu_shared/can-up.sh"
echo "  cd $LIGHTSABER && source .venv/bin/activate && python robot_discover.py"
