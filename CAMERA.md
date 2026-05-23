# Camera — Dabai DC1 (Orbbec)

The Piper kit ships a **Dabai DC1** USB RGB camera (Orbbec). On macOS it appears as **"Dabai DC1"** in AVFoundation; on Linux it shows up as `/dev/video*`.

This lightsaber app captures **RGB frames** by default via OpenCV or ffmpeg AVFoundation (`camera.py`). For **depth / IR / D2C** via the vendor SDK, see the optional modules below.

## Optional Orbbec SDK path (vision stubs)

| Module | Purpose |
|--------|---------|
| `orbbec_sdk.py` | Lazy import + install hints |
| `orbbec_camera.py` | RGB-D capture via `pyorbbecsdk` (`OrbbecCamera`) |
| `orbbec_depth.py` | Depth ROI helpers + lunge/overhead hints |
| `orbbec_vision.py` | `DepthAugmentedAttackVision` fusion stub |
| `orbbec_preview.py` | Side-by-side color + depth preview |

Install SDK (optional):

```bash
pip install -r requirements-orbbec.txt
```

Enable in `config.py`: `ENABLE_ORBBEC_SDK = True`, or pass `--orbbec-sdk` on the CLI.

```bash
python orbbec_preview.py
python vision.py --orbbec-sdk --depth-hints
python vision.py --orbbec-sdk
```

Config keys: `ORBBEC_ENABLE_DEPTH`, `ORBBEC_ENABLE_IR`, `ENABLE_DEPTH_ATTACK_HINTS`, `ORBBEC_*_MM` thresholds.

## Hardware (this project)

| Item | Value |
|------|-------|
| Model | **Dabai DC1** (Piper kit camera) |
| Vendor / SDK family | [Orbbec](https://www.orbbec.com/) |
| macOS device name | `Dabai DC1` (`PIPER_CAMERA_NAME` in `config.py`) |
| Default resolution | 1280×720 (`CAMERA_WIDTH` / `CAMERA_HEIGHT`; native OpenCV path was 1632×1224) |
| Default FPS target | 30 |

## How we capture frames

| Platform | Backend | Notes |
|----------|---------|-------|
| macOS — Piper | ffmpeg → AVFoundation by name | Correct Dabai feed when multiple USB cameras are connected |
| macOS — laptop dev | OpenCV index 0 | MacBook built-in webcam |
| Linux — Piper | OpenCV → V4L2 `/dev/video*` | Fast; no ffmpeg needed |

Run commands and CLI flags: **[README.md § Camera](README.md#camera-macbook-vs-piper-dabai)** and **[task-vision.md](task-vision.md)**.

## Orbbec SDK and tools

### Base SDK

- **OrbbecSDK (pre-compiled v1 & v2):** https://github.com/orbbec/OrbbecSDK

### API documentation

- **C++ API user guide (PDF, Chinese):** https://github.com/orbbec/OrbbecSDK/blob/main/doc/tutorial/Chinese/OrbbecSDK_C%2B%2B_API_user_guide-v1.0.pdf

### OrbbecViewer

Desktop tool for exploring camera streams, depth, and device settings.

- **Download (releases):** https://github.com/orbbec/OrbbecSDK/releases
- **User guide (PDF):** https://www.orbbec.com/docs/g330-explore-camera-functions-in-orbbec-viewer/

### Python SDK

- **pyorbbecsdk:** https://github.com/orbbec/pyorbbecsdk
- **Install in this repo:** `pip install -r requirements-orbbec.txt` (see optional modules in this file § Optional Orbbec SDK path)

Use this if you need depth, IMU, or vendor-specific controls beyond plain UVC/OpenCV capture.

### ROS wrappers

| ROS version | Repository | Docs |
|-------------|------------|------|
| ROS 1 | https://github.com/orbbec/OrbbecSDK_ROS1 | https://github.com/orbbec/OrbbecSDK_ROS1/tree/main/docs |
| ROS 2 | https://github.com/orbbec/OrbbecSDK_ROS2 | https://github.com/orbbec/OrbbecSDK_ROS2/tree/main/docs |

## Config keys (`config.py`)

- `CAMERA_SOURCE` — `"piper"`, `"laptop"`, numeric index, or `/dev/videoN`
- `CAMERA_BACKEND` — `"auto"` \| `"opencv"` \| `"ffmpeg"`
- `PIPER_CAMERA_NAME` — AVFoundation name on macOS (default `"Dabai DC1"`)
- `PIPER_OPENCV_INDEX` — optional OpenCV index when using `--camera-backend opencv` on Mac
- `CAMERA_WIDTH`, `CAMERA_HEIGHT`, `CAMERA_FPS`

## Diagnostics

```bash
cd projects/lightsaber
source .venv/bin/activate

python camera.py --list
python camera.py --preview
python camera.py --pick-opencv   # find OpenCV index on Mac
```
