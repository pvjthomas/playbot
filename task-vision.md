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
python -m unittest tests.test_vision tests.test_orbbec tests.test_camera_orientation
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

### Wrist-mounted Orbbec — image orientation plan

The Dabai on the **wrist** is not a fixed desk webcam. Raw frames may be **rotated
(90°/180°/270°)**, **flipped**, or **mirror-preview** like the laptop cam. During
**high block** the lens may point **up at the ceiling** or **away from the partner**
while attack labels still use **image left/right** (`directions.py`).

| Phase | What | Module / command |
|-------|------|------------------|
| **1 — Install cal (fixed)** | At `GUARD_CENTER`, partner in frame: head → top of image, image-left = left edge | `python camera_calibrate_orientation.py --camera piper` → `camera_orientation.json` |
| **1b — Mirror** | Same as laptop: right hand on which side of screen? | `python camera_calibrate_mirror.py --camera piper` |
| **2 — Enable correction** | Vision sees canonical BGR (+ depth if Orbbec) | `CAMERA_APPLY_ORIENTATION_CORRECTION = True` (and mirror flag if needed) |
| **3 — Pose-dependent FOV** | Arm rotates → image “up” rotates with wrist | **Default:** keep detection **image-relative** (velocity / END pose in current frame). **Optional:** `ORBBEC_ENABLE_IMU` + `derotate_frame_with_imu_stub()` |
| **4 — High attack** | Camera may not see partner face-on | Prefer **temporal** cues + depth hints; document `mount_facing` (`toward_partner` vs `away_from_partner`) |

**Stub code:** `camera_orientation.py`, `camera_calibrate_orientation.py`, tests in
`tests/test_camera_orientation.py`. Orbbec path applies the same transform to
`depth_mm` in `orbbec_camera.read_frameset()`.

**Do not** change `AttackDirection` semantics — only normalize pixels before
`detect_attack()`. If correction is off, labels still mean image axes on the **raw**
frame (document which in overlays).

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

## Milestone 2 — Temporal swing estimation (priority for robot)

**Why:** Today `detect_attack()` sees one frame at a time and only fires strongly at **peak
extension**. The robot blocks too late. Sparring needs **begin → mid → end** tracking so
the arm can move during the swing, not after it.

**Works with or without saber:** MediaPipe wrists (or grip midpoint when hands are close)
are the primary motion signal. YOLO saber bbox is optional fusion when trained weights
are available — not required for temporal phase or linear direction.

Full spec: **`directions.py`** § *Temporal swing estimation* and **[DIRECTIONS.md](DIRECTIONS.md)**.

Training index: **[TRAINING-PLAN.md](TRAINING-PLAN.md)**.

### Motion model

| Kind | Examples | How to detect (image frame) |
|------|----------|-----------------------------|
| **Linear** | Side swipes, overhead chops | Dominant wrist/saber velocity along one axis (L↔R or U↕D) over ~0.3–0.8 s |
| **Thrust** | Chest push toward camera | Hands at midline; **growing** extension / bbox scale toward robot — not lateral travel |

### Swing phases

| Phase | Meaning | Robot use (proposed — team PR on `contracts.py`) |
|-------|---------|-----------------------------------------------------|
| `idle` | At rest, between strikes | No move |
| `begin` | Wind-up; strike direction becomes visible | Optional early guard |
| `mid` | Active travel through the arc | **Primary block window** |
| `end` | Peak extension (today's END-pose rule) | Confirm / hold block |

### Checklist

- [ ] Ring buffer of recent landmarks (and optional saber tip) — config: window length, min velocity
- [ ] Classify **linear vs thrust** per active swing
- [ ] Estimate **direction** (`left`/`right`/`high`/`center`/`none`) from velocity axis, not static pose alone
- [ ] Estimate **phase** (`begin`/`mid`/`end`/`idle`) from speed + extension profile
- [ ] Overlay: show `phase`, `kind`, and direction (debug text or color)
- [ ] Unit tests with synthetic landmark sequences (hand-crafted begin→mid→end paths)
- [ ] Propose extended contract on `contracts.py` (see below); keep `detect_attack()` until robot/app adopt it

### Implementation notes

- **Linear swing:** back-and-forth grip motion → direction = sign of dominant displacement
  (image-left vs image-right, or up vs down for overhead). Hysteresis so idle↔begin
  doesn't flicker.
- **Thrust:** retracted at chest → forward growth; use two-hand midline + increasing reach;
  optional depth/scale from Orbbec when `--depth-hints` is on.
- **Phase boundaries:** `begin` when velocity crosses threshold from rest; `mid` while
  speed is high and aligned with strike axis; `end` when extension peaks then velocity
  drops (or static END-pose heuristics match).
- Do **not** break Milestone 1: temporal layer wraps or extends `AttackVision`, doesn't
  replace single-frame path until integrated in `main.py`.

---

## Milestone 3 — Improve detection

- [ ] Implement reliable **`low`** attack (hip/knee or torso heuristics)
- [ ] Reduce false positives when arms are at rest
- [ ] Add optional YOLO person gate (read flags from `config.py` only)
- [ ] Keep MediaPipe on every frame; YOLO on every N frames for latency
- [ ] Document tuning params at top of `vision.py`

---

## Milestone 4 — Polish

- [ ] FPS stable ≥ 20 on demo laptop
- [ ] Overlay: color per direction, optional confidence/debug text
- [ ] Unit test for `_classify` / fake mode in `tests/` (vision-owned test file OK)
- [ ] PR to `feature/vision` — **only** touch owned files (+ `config.py` vision keys if needed)

---

## Contract you must implement

**Today (Milestone 1):**

```python
class AttackVision:
    def detect_attack(self, frame) -> AttackDirection: ...
```

Valid returns: `"left"`, `"right"`, `"high"`, `"low"`, `"center"`, `"none"`

**Proposed (Milestone 2 — team PR on `contracts.py` before robot/app wire it):**

```python
SwingPhase = Literal["idle", "begin", "mid", "end"]
MotionKind = Literal["none", "linear", "thrust"]

@dataclass
class SwingState:
    direction: AttackDirection   # strike direction in image frame (see directions.py)
    phase: SwingPhase            # where we are in the swing
    kind: MotionKind             # linear swipe/chop vs chest thrust

class AttackDetector:
    def detect_attack(self, frame) -> AttackDirection: ...  # keep for compat
    def detect_swing(self, frame) -> SwingState: ...         # temporal API
```

Robot team can then respond on `phase == "mid"` (early) instead of only on direction
edges at `end`. App team updates `main.py` trigger logic when contract lands.

---

## Coordination

- Changing `AttackDirection` values → PR on **`contracts.py`** with team review
- Adding `SwingState` / `detect_swing()` → PR on **`contracts.py`** + notify robot/app
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
- [ ] Auto-label: `python prepare_saber_yolo_dataset.py --saber redtoy`
- [ ] Train: `python train_saber.py --saber redtoy`
- [ ] Or path A: tip tape + HSV thresholds in `config.py`
- [ ] Draw grip→tip line in `overlays.py`
- [ ] (Later) Fuse saber angle with pose for `detect_attack()` — team PR on `contracts.py` if API changes

**Integration rule:** Do not break existing `detect_attack()` until saber path is stable; run in parallel for preview first.

### Possible direction (not planned yet)

Forearm direction (elbow → wrist) is a **weak predictor** of actual blade direction — the grip can rotate independently, and two-handed holds decouple wrist angle from saber axis.

Once YOLO saber weights are stable, we **may** want to **turn off** the forearm-extends-blade geometry in `saber_detector.py` (`_saber_from_arm` tip placement along the forearm ray) and instead:

- **YOLO** — find the saber bbox / long axis in the frame
- **MediaPipe** — anchor grip to the nearest wrist (already sketched in `_merge_yolo`)

Blade direction would come from the **detected object**, not inferred from arm pose. Evaluate after training; no change until the YOLO path is proven on real strikes.

### Tip in frame vs tip out of frame

Real swings often show the **grip in frame** while the **tip is cropped** at an edge (or fully
off-screen on wide extensions). The codebase handles this **inconsistently** today:

| Layer | Tip fully in frame | Tip out of frame / cropped |
|-------|-------------------|----------------------------|
| **`_saber_from_arm`** | Extrapolates tip along forearm ray | Same — tip `(x,y)` **not clamped**; can lie outside image bounds |
| **Color tip refine** | Farthest red pixel along ray | Search **stops at frame edge** — tip ≈ last visible blade pixel (better) |
| **`_merge_yolo`** | Bbox + grip → extrapolated tip | Uses bbox aspect for angle but tip still **extrapolated past frame**; truncated YOLO boxes are not used as visible extent |
| **`prepare_saber_yolo_dataset`** | Bbox around grip→tip | Bbox **clipped to frame** (`max(0,…)`, `min(w,…)`) — labels can be partial sabers |
| **`SaberLine`** | grip + tip coords | **No `tip_visible` flag** — callers cannot tell observed vs inferred tip |
| **Training photos** | Most poses assume full saber | `neg_partial` (“partially out of frame”) lives in **`other/`** (negative class) — only 4 shots; no dedicated **positive** partial-blade set yet |

**Implications**

- Overlays may draw a tip **off-screen** when the real tip is cropped.
- Direction from extrapolated off-frame tips is **unreliable** (especially forearm-based).
- YOLO should be trained on **partial bboxes** (blade cut by edge) as positives, not only
  `other/` negatives — otherwise live detection fails on the strikes that matter most
  (full extension toward frame edge).
- Temporal swing tracking should prefer **in-frame grip / visible blade pixels** for velocity;
  treat extrapolated tips as low confidence when the tip is outside bounds.

**Possible improvements (not implemented)**

- Add `tip_in_frame: bool` (or `truncated: bool`) on `SaberLine`.
- When YOLO bbox touches a frame edge, set tip to **bbox far end inside frame**, not extrapolation.
- Collection: add positive poses — tip at left/right/top **edge**, tip just off-screen, wide swipe.
- Manual bbox labels: draw box over **visible blade only** (already implied by export docs).
