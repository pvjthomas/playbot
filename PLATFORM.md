# Platforms — AI Lightsaber Trainer

## Summary

| Role | macOS | Ubuntu / Linux |
|------|-------|----------------|
| Vision (webcam, MediaPipe, YOLO) | Supported | Supported |
| App (main loop, sounds, dashboard) | Supported | Supported |
| PiPER arm over CAN | Not recommended | **Required for live hardware** |
| Milestone 1 (DRY_RUN stubs) | Yes | Yes |

The project is **not Ubuntu-only**. Only **real robot motion** needs Linux with CAN.

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
- USB-CAN adapters often **do not** show up as `can0`; robot hardware is usually blocked on Mac.

---

## Ubuntu (Developer 2 — robot)

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
