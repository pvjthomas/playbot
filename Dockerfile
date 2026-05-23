# Minimal Ubuntu image — install deps + run contract tests.
# Build from projects/:  docker build -f lightsaber/Dockerfile -t lightsaber .
#
# Not for Mac CAN passthrough. For live PiPER + CAN, use native Ubuntu.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Shared + lightsaber requirements (paths match -r ../shared/...)
COPY shared/requirements.txt /app/shared/requirements.txt
COPY lightsaber/requirements.txt /app/lightsaber/requirements.txt

RUN python3 -m venv /app/.venv \
    && /app/.venv/bin/pip install --upgrade pip \
    && /app/.venv/bin/pip install -r /app/lightsaber/requirements.txt

COPY shared/ /app/shared/
COPY lightsaber/ /app/lightsaber/

WORKDIR /app/lightsaber

# Default: smoke test (no webcam/CAN required)
CMD ["/app/.venv/bin/python", "-m", "unittest", "tests.test_contracts"]

# --- Optional run examples (Linux host only) ---
# Webcam:
#   docker run --rm -it --device=/dev/video0 lightsaber \
#     /app/.venv/bin/python main.py
# CAN (requires privileged + device mapping on host):
#   docker run --rm -it --privileged --network host lightsaber \
#     /app/.venv/bin/python main.py
