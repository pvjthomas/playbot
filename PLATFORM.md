# Platforms — AI Lightsaber Trainer

## Summary

| Role | macOS | Ubuntu / Linux |
|------|-------|----------------|
| Vision (webcam, MediaPipe, YOLO) | Supported | Supported |
| App (main loop, sounds, dashboard) | Supported | Supported |
| PiPER arm over CAN | **Experimental** (`gs_usb`, see [MAC-ROBOT.md](MAC-ROBOT.md)) | **Recommended** (SocketCAN `can0`) |
| Milestone 1 (DRY_RUN stubs) | Yes | Yes |

The project is **not Ubuntu-only**. Only **real robot motion** needs Linux with CAN.

> **Why a Linux VM on Mac?** This hackathon uses legacy **`piper_sdk`** with the kit **candleLight** adapter. AgileX’s newer **`pyAgxArm`** driver is meant to be more modern and support **Mac native** (serial/SLCAN CAN modules). We use the **QEMU VM workaround** because candleLight + `gs_usb` on macOS is unreliable — see [ubuntu_shared/MAC-QEMU-ROBOT-VM.md](ubuntu_shared/MAC-QEMU-ROBOT-VM.md).

---

## macOS (Developers 1 & 3)

**Good for:** `python main.py` with `DRY_RUN=True`, tuning vision, demo UI.

```bash
cd projects/lightsaber
bash setup.sh
source .venv/bin/activate
python main.py
```

- Use `USE_FAKE_ATTACKS = True` in `config.py` if the camera is unavailable.
- `pip` may only exist inside `.venv` (not globally).
- USB-CAN on Mac: no kernel `can0`; use **python-can `gs_usb`** with the adapter plugged into the **Mac** (not the Apple-Virtualization VM).
- Full steps: **[MAC-ROBOT.md](MAC-ROBOT.md)** — `brew install libusb`, `pip install "python-can[gs-usb]"`, `python robot_discover.py` on the host.

```bash
cd projects/lightsaber && source .venv/bin/activate
brew install libusb
pip install "python-can[gs-usb]"
python robot_discover.py          # adapter on Mac USB
python robot_smoke.py --connect   # LIVE connect, no motion (set DRY_RUN=False for --connect)
```

Code: `can_platform.py` + `config.CAN_BUSTYPE` (`auto` → `gs_usb` on Darwin).

---

## Ubuntu (Developer 2 — robot)

**VM (recommended for live CAN):** UTM **QEMU** Ubuntu — full guide **[ubuntu_shared/MAC-QEMU-ROBOT-VM.md](ubuntu_shared/MAC-QEMU-ROBOT-VM.md)**. Also [ENVIRONMENT.md](ubuntu_shared/ENVIRONMENT.md), [SSH-SETUP.md](ubuntu_shared/SSH-SETUP.md). Mac UTM share: **`/Users/fio/UbuntuShared`**.

```bash
ssh philip@192.168.64.4   # example QEMU guest IP
# or: ssh ubuntu-robot-qemu   (after ~/.ssh/config setup)
```

**Good for:** `piper_sdk`, SocketCAN, `can0` at 1 Mbps.

```bash
# CAN (example — adapter name may vary)
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up

cd projects/lightsaber
bash setup.sh
source .venv/bin/activate
python main.py
```

Keep `DRY_RUN = True` until poses are calibrated and motion is approved.

---

## Docker (optional failsafe)

Use for **reproducible installs** and smoke tests on Ubuntu — **not** a guarantee that CAN or webcam work from Docker on Mac.

Build from the `projects/` directory:

```bash
cd projects
docker build -f lightsaber/Dockerfile -t lightsaber .
docker run --rm lightsaber python -m unittest lightsaber.tests.test_contracts
```

For webcam or CAN on Linux host, you must pass devices explicitly (see `Dockerfile` comments). Prefer **native Ubuntu** next to the arm for hackathon robot day.

---

## Git is the source of truth

Do not copy files manually into a container. Clone the repo (or pull `main`) on each machine:

```bash
git clone <repo-url>
cd playbot/projects/lightsaber   # adjust path to your clone
```

---

## Team split reminder

| Branch | Platform focus |
|--------|----------------|
| `feature/vision` | Mac or Ubuntu |
| `feature/demo` | Mac or Ubuntu |
| `feature/robot` | Ubuntu at the arm |
