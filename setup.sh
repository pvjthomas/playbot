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
echo "Done. Activate with:"
echo "  source .venv/bin/activate"
echo "Then run:"
echo "  python main.py"
