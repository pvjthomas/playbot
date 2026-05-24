#!/usr/bin/env bash
# Create venv and install deps (use: source setup.sh  OR  bash setup.sh && source .venv/bin/activate)
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "python3 not found. Install Python 3 first."
  exit 1
fi

# Prefer Homebrew Python 3.11+ (avoids 3.9 mediapipe install issues on macOS)
PY="${PYTHON:-python3.11}"
command -v "$PY" >/dev/null || PY=python3
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Optional vision training (Roboflow + saber YOLO):"
echo "  pip install -r requirements-vision.txt"
echo "  export ROBOFLOW_API_KEY=...   # https://app.roboflow.com/settings/api"
echo ""
echo "Optional Orbbec RGB-D SDK (depth / IR):"
echo "  pip install -r requirements-orbbec.txt"
echo "  python orbbec_preview.py"
echo "Done. Activate with:"
echo "  source .venv/bin/activate"
echo "Then run:"
echo "  python main.py"
if [ "$(uname -s)" = "Darwin" ]; then
  echo ""
  echo "Mac robot (candleLight on Mac USB): see MAC-ROBOT.md"
  echo "  brew install libusb && pip install \"python-can[gs-usb]\""
  echo "  python robot_discover.py"
fi
