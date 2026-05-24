#!/usr/bin/env bash
# VM setup for lightsaber (Ubuntu 26 / Python 3.14 host).
# Prefer: agent rsyncs Mac repo + runs uv (see ENVIRONMENT.md).
# Optional apt (needs sudo once on VM):
#   sudo apt install -y libgl1 libglib2.0-0 v4l-utils python3.12-venv
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
LIGHTSABER="${LIGHTSABER_DIR:-$HOME/piper-vision-hackathon/projects/lightsaber}"

if [[ ! -d "$LIGHTSABER" ]]; then
  echo "Missing $LIGHTSABER — rsync from Mac first."
  exit 1
fi

command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
cd "$LIGHTSABER"
rm -rf .venv
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
uv pip uninstall opencv-python opencv-contrib-python 2>/dev/null || true
uv pip install opencv-python-headless

.venv/bin/python -m unittest tests.test_contracts
echo "OK — $LIGHTSABER"
