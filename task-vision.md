# Task — Vision (Developer 1)

**Project:** this repo (`lightsaber`)  
**Branch:** `feature/vision`  
**Owns:** `camera.py`, `vision.py`, `overlays.py`, optional Orbbec stubs (`orbbec_*.py`), optional `saber_detector.py`

Do **not** import `robot`, `main`, or `dashboard`. Integrate only through `contracts.py` (`AttackDirection`, `AttackDetector`).

---

## Setup

```bash
cd projects/lightsaber   # or your clone path
git checkout -b feature/vision    # first time only
source .venv/bin/activate
python vision.py                 # vision-only preview (your files)
python main.py                   # full app integration test
python -m unittest tests.test_vision tests.test_orbbec
```

Optional Orbbec RGB-D (depth / IR):

```bash
pip install -r requirements-orbbec.txt
python orbbec_preview.py
python vision.py --orbbec-sdk --depth-hints
```

### Camera commands

On Mac: `--camera piper` opens the Dabai on the arm (auto → ffmpeg, correct but slower).
`--camera laptop` uses the MacBook webcam (fast, good for desk dev).

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
python camera.py --pick-opencv   # recommended on Mac: OpenCV indices only, faster popup
```

| Flag | What it does |
|------|----------------|
| `--camera piper` | Dabai DC1 on the arm |
| `--camera laptop` | MacBook built-in webcam |
| `--camera-backend ffmpeg` | Open Piper by device name (Mac default) |
| `--camera-backend opencv` | Direct OpenCV (fast; needs `PIPER_OPENCV_INDEX` on Mac for Piper) |
| `--orbbec-sdk` | Orbbec `pyorbbecsdk` capture (RGB+depth) instead of OpenCV/ffmpeg |
| `--depth-hints` | Fuse depth cues in `vision.py` preview (use with `--orbbec-sdk`) |

On **Ubuntu** at the arm, `--camera piper` uses `/dev/video*` and is fast like the laptop path.
Config keys: `CAMERA_SOURCE`, `CAMERA_BACKEND`, `PIPER_CAMERA_NAME`, `CAMERA_WIDTH/HEIGHT`.
More detail: **[CAMERA.md](CAMERA.md)** (hardware + Orbbec SDK links), README § Camera, `camera.py` docstring.

## Milestone 1 — Working detection (current sprint)

- [ ] Confirm camera opens (`python camera.py --list`, then `python vision.py --camera piper` or `--camera laptop`)
- [ ] `detect_attack(frame)` returns valid `AttackDirection` values
- [ ] Overlay shows `attack: left|right|high|center|none` (`overlays.py`)
- [ ] MediaPipe skeleton draws when pose is tracked
- [ ] Test with slow mock strikes; tune `HIGH_MARGIN`, `SIDE_MARGIN`, `EXTENSION_MIN` in `config.py`

**Done when:** another dev can run `main.py` and see stable attack labels on screen.

### Your daily loop

1. `python vision.py` — iterate on detection + overlay without robot
2. Tune margins in `config.py` if labels flicker or miss strikes
3. `python main.py` — confirm robot dev sees your labels in the full app
4. Commit only vision-owned files (+ `config.py` vision keys, `README.md`, this file)

---

## Milestone 2 — Improve detection

- [ ] Implement reliable **`low`** attack (hip/knee or torso heuristics)
- [ ] Reduce false positives when arms are at rest
- [ ] Add optional YOLO person gate (read flags from `config.py` only)
- [ ] Keep MediaPipe on every frame; YOLO on every N frames for latency
- [ ] Document tuning params at top of `vision.py`

---

## Milestone 3 — Polish

- [ ] FPS stable ≥ 20 on demo laptop
- [ ] Overlay: color per direction, optional confidence/debug text
- [ ] Unit test for `_classify` / fake mode in `tests/` (vision-owned test file OK)
- [ ] PR to `feature/vision` — **only** touch owned files (+ `config.py` vision keys if needed)

---

## Contract you must implement

```python
class AttackVision:
    def detect_attack(self, frame) -> AttackDirection: ...
```

Valid returns: `"left"`, `"right"`, `"high"`, `"low"`, `"center"`, `"none"`

---

## Coordination

- Changing `AttackDirection` values → PR on **`contracts.py`** with team review
- Camera broken? use `USE_FAKE_ATTACKS = True` in `config.py` for robot/app devs

---

## Optional — Lightsaber object (grip → tip)

**Not required for demo.** Current strikes use **body pose** (wrists), not the prop.

**redtoy profile (Mac webcam):**

```bash
python saber_preview.py --saber redtoy --camera laptop
python collect_saber_trainer.py --saber redtoy --camera laptop   # guided session (recommended)
python collect_saber_data.py --saber redtoy --camera laptop      # free-form capture
```

Full YOLO pipeline: **[SABER-TRAINING.md](SABER-TRAINING.md)**

Profiles: `saber_profiles.py` (`redtoy` = dual-range red HSV + longer blade ratio).

**Goal:** Treat the saber as a **tubular object** attached to the hand, with a defined **grip** and **tip**, for overlay + finer aim.

| Approach | Effort | What you need |
|----------|--------|----------------|
| **A — Color tip + wrist** | ~2–4 hrs | Bright tape on tip, MediaPipe wrist, HSV blob at tip, line grip→tip |
| **B — Train YOLOv8** | ~4–8 hrs | 50–100 photos of your saber, label bbox or segment, `yolo train` |
| **C — Hybrid** | Medium | YOLO custom class + match bbox to nearest wrist |

**Stub:** `saber_detector.py` → `detect_saber(frame) -> SaberLine | None`  
**Config:** `ENABLE_SABER_DETECTION = False` (off by default)

### Optional checklist

- [ ] Collect 50+ images: saber in hand, varied angles/lighting (for path B)
- [ ] Label in [Roboflow](https://roboflow.com) or ultralytics — class `lightsaber`
- [ ] Train: `yolo train data=... model=yolov8n.pt epochs=50`
- [ ] Or path A: tip tape + HSV thresholds in `config.py`
- [ ] Draw grip→tip line in `overlays.py`
- [ ] (Later) Fuse saber angle with pose for `detect_attack()` — team PR on `contracts.py` if API changes

**Integration rule:** Do not break existing `detect_attack()` until saber path is stable; run in parallel for preview first.
