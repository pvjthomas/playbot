#!/usr/bin/env bash
# Bring up SocketCAN on the VM (run once per boot after USB-CAN is passed through).
set -euo pipefail
IF="${1:-can0}"
BITRATE="${2:-1000000}"

if ! ip link show "$IF" &>/dev/null; then
  echo "No $IF — attach USB-CAN to VM in UTM (not Mac), then replug."
  exit 1
fi

sudo ip link set "$IF" down 2>/dev/null || true
sudo ip link set "$IF" type can bitrate "$BITRATE"
sudo ip link set "$IF" up
ip -details link show "$IF"
echo "OK — $IF up @ ${BITRATE} bps"
