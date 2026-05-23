# AI Lightsaber Trainer

Webcam vision → attack direction → PiPER block pose (stub by default).

## Quick start

```bash
cd projects/lightsaber
source .venv/bin/activate
python main.py
```

No camera? Set `USE_FAKE_ATTACKS = True` in `config.py`.

## Camera (MacBook vs Piper Dabai)

The Piper kit uses a **Dabai DC1** USB camera. On **macOS**, OpenCV device indices do not
reliably match the Piper camera when several devices are connected (built-in webcam,
iPhone Continuity, etc.). We therefore support two capture backends:

| Backend | Speed | Correct Piper on Mac? | When to use |
|---------|-------|----------------------|-------------|
| **opencv** | Fast (~30 fps) | Only if you set the right index manually | Laptop webcam; Piper on **Ubuntu** (`/dev/video*`) |
| **ffmpeg** | Slower | Yes — opens `"Dabai DC1"` by name | **Piper on Mac** (recommended for demo) |
| **auto** | — | Default: ffmpeg on Mac, opencv on Linux | Leave as default |

**Why ffmpeg is slower on Mac:** capture goes through a subprocess and a raw-video pipe
(Python → ffmpeg → AVFoundation → pipe → Python), plus pixel-format conversion. The laptop
path is direct OpenCV → AVFoundation in one process.

### Commands (copy & paste)

From `projects/lightsaber` with venv active (`source .venv/bin/activate`):

```bash
# Piper on Mac (correct Dabai, auto → ffmpeg)
python vision.py --camera piper
python main.py --camera piper

# Laptop webcam (fast dev)
python vision.py --camera laptop

# Force backend
python vision.py --camera piper --camera-backend ffmpeg   # correct, slower (Mac default)
python vision.py --camera piper --camera-backend opencv   # fast only if PIPER_OPENCV_INDEX is set

# Diagnostics
python camera.py --list
python camera.py --preview
python camera.py --pick
python camera.py --pick-opencv   # recommended on Mac: skips slow ffmpeg entries first
```

| Backend | Speed | Piper on Mac? |
|---------|-------|---------------|
| **auto** → ffmpeg | Slower | Yes (default for `--camera piper`) |
| **opencv** | Fast | Only if `PIPER_OPENCV_INDEX` is set in `config.py` |
| **opencv** + `--camera laptop` | Fast | N/A — uses MacBook webcam |

**Why Piper is slower on Mac:** OpenCV device indices do not match camera names, so Piper
uses ffmpeg (subprocess + pipe) to open `"Dabai DC1"` by name. Laptop uses direct OpenCV.

**Linux at the arm:** `--camera piper` uses OpenCV on `/dev/video*` (fast, no ffmpeg needed).

Config (`config.py`): `CAMERA_SOURCE`, `CAMERA_BACKEND`, `PIPER_CAMERA_NAME`,
`PIPER_OPENCV_INDEX`, `CAMERA_WIDTH`, `CAMERA_HEIGHT`. Flags override config for one run.

Technical details: `camera.py` module docstring.

## Platforms (Mac vs Ubuntu)

- **Vision + app:** macOS and Ubuntu both work (venv + `python main.py`).
- **Live PiPER + CAN:** use **Ubuntu** next to the arm — Mac is not reliable for `can0`.

See **[PLATFORM.md](PLATFORM.md)** for the full matrix and optional Docker smoke test.

```bash
# Optional: Ubuntu container install check (from projects/)
cd ..
docker build -f lightsaber/Dockerfile -t lightsaber .
docker run --rm lightsaber
```

## Team ownership

| Developer | Branch | Owns |
|-----------|--------|------|
| **1 — Vision** | `feature/vision` | `camera.py`, `vision.py`, `overlays.py` — see **[task-vision.md](task-vision.md)** |
| **2 — Robot** | `feature/robot` | `robot.py`, `poses.py`, `safety.py`, `movement_trainer.py` |
| **3 — App** | `feature/demo` | `main.py`, `dashboard.py`, `sounds.py`, `README.md` |

**Shared (coordinate before editing):** `contracts.py`, `config.py`, `requirements.txt`

## Architecture rule

All cross-team communication goes through **`contracts.py`**:

```python
direction: AttackDirection = vision.detect_attack(frame)
robot.respond_to_attack(direction)
```

Types: `AttackDirection`, `RobotPose`, protocols `AttackDetector`, `RobotController`.

## Safety defaults

- `DRY_RUN = True` in `config.py` — prints moves, no CAN motion
- Movement cooldown via `SafetyGuard`
- Emergency stop key: **`e`**

## Git workflow

- `main` stays stable
- One PR per feature branch; only touch owned files unless coordinating on `contracts.py`

## Milestone 1 checklist

- [ ] `python main.py` opens webcam (or fake attacks)
- [ ] Attack direction shown on overlay
- [ ] Robot prints intended pose
- [ ] Sound/dashboard hooks present (optional flags in `config.py`)
- [ ] `python -m unittest tests.test_contracts` passes

## Tests

```bash
python -m unittest tests.test_contracts
```
