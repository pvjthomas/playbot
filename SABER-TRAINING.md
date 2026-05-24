# Saber YOLO training — redtoy (Mac webcam)

Collect → **auto-label** → **direction review (L/R)** → **box review (y/n)** → train → plug into `saber_detector.py`.

## Direction definitions (read this first)

**All names like `left` / `right` mean where the strike FINISHES in the PHOTO / ON SCREEN**
— not your body's anatomical left, and not the robot arm's physical left.

### Strikes are motions; we label the END pose

| Motion you perform | What the label means (hold this for capture) |
|--------------------|-----------------------------------------------|
| Swipe image-left → image-right | Label **left** or **right** at **peak extension** (where the blow finishes), not wind-up |
| Overhead chop | **high** = saber **above shoulders** (top of arc), not the downward travel |
| Chest → thrust | **center** = **fully extended** toward camera, not retracted at chest |

With `--interval 3`, **hold the END pose** for the whole window so auto-saves match the label.

**Live vision** (`detect_attack`) uses the same rule on a **single frame** — no motion history.

| Attack label | END pose in the image | Robot blocks |
|--------------|----------------------|--------------|
| **left** | Saber extended toward **LEFT edge** of image | `BLOCK_LEFT` |
| **right** | Saber extended toward **RIGHT edge** of image | `BLOCK_RIGHT` |
| **high** | Overhead, above shoulders | `BLOCK_HIGH` |
| **center** | Full thrust at camera (midline) | `GUARD_CENTER` |

**YOLO photo folders** (`horizontal`, `vertical`, `diagonal`, `other`) = **static blade angle**
for bbox training only — motion phase does not matter. YOLO class: **`lightsaber`**.

Full spec: **`directions.py`**.

### Partial saber visibility (tip in / out of frame)

During real strikes the **grip often stays in frame** while the **tip crosses or leaves** the
image edge (especially `left` / `right` / `high` END poses). Expect both cases in training
and live detection:

- **Tip in frame** — full blade visible; YOLO bbox and color tip refine work best.
- **Tip cropped or off-screen** — label the YOLO box around **visible blade only** (do not
  extend the bbox past the frame). Auto-label in `prepare_saber_yolo_dataset.py` already
  clips boxes to frame bounds.

Collect **positive** examples with partial blades (not only `neg_partial` in `other/`, which
teaches “no saber”). Include wide extensions where the tip hits the left/right/top edge.

Runtime (`saber_detector.py`) does **not** yet expose whether the tip was seen vs extrapolated
— see **`task-vision.md`** § *Tip in frame vs tip out of frame*.

---

## Phase 1 — Guided photo session

```bash
cd projects/lightsaber
source .venv/bin/activate
python collect_saber_trainer.py --saber redtoy --camera laptop --interval 3 --resume
```

| Key | Action |
|-----|--------|
| *(auto)* | Saves every `--interval` seconds |
| s / b / q | skip / back / quit |

Output: `projects/models/saber_dataset/raw/redtoy/<label>/`

---

## Phase 2 — Auto-label (red HSV → bounding boxes)

```bash
python prepare_saber_yolo_dataset.py --saber redtoy
```

Builds `projects/models/saber_dataset/yolo/` with train/val split and `data.yaml`.
Negative images (`other/`) get empty label files.

**Manual boxes (Paint / ImageJ) — recommended if auto-label is wrong:**

```bash
python export_for_manual_label.py --saber redtoy --open
# Draw bright green (#00FF00) rectangle OUTLINE around saber in each image; save.
python import_manual_bboxes.py --saber redtoy --preview   # check detections
python import_manual_bboxes.py --saber redtoy --apply     # → yolo_manual/
```

See `manual_annotate/HOW_TO_ANNOTATE.txt`. Training prefers `yolo_manual/` over auto `yolo/`.

**Auto review (y/n) — optional if using manual import:**

```bash
python review_saber_labels.py --saber redtoy
```

Shows each photo with the green auto-box (or “NEGATIVE”). **`y`** approve · **`n`** reject · **`b`** back · **`q`** quit.  
Approved images → `yolo_reviewed/` (used automatically by `train_saber.py`).

**Optional — direction spot-check (L/R on existing photos, no recollection):**

```bash
python review_saber_directions.py --saber redtoy
```

Vision shows what it thinks; you press **`L`** / **`R`** for where the saber points **in that still**
(END pose). Use `--mode strike` for all `strike_left` / `strike_right` photos.

---

## Phase 3 — Train

```bash
python train_saber.py --saber redtoy
```

Best weights: `projects/models/saber_runs/redtoy_v1/weights/best.pt`

---

## Phase 4 — Wire into detector

```python
SABER_MODEL = "../models/saber_runs/redtoy_v1/weights/best.pt"
```

```bash
python saber_preview.py --saber redtoy --camera laptop
```

---

## Timeline

| Step | Time |
|------|------|
| Guided capture | ~15–25 min |
| Auto-label | ~1 min |
| Train yolov8n | ~10–30 min |
| Preview + tune | ~15 min |
