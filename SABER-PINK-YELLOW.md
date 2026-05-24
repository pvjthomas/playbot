# Training plan — pink & yellow sabers

Same **shape and poses** as `redtoy`; only blade color changes. Goal: **one YOLO model**
(class `lightsaber`) that works on red, pink, and yellow — without another 80‑epoch run from
scratch.

**Base weights:** `projects/models/saber_runs/redtoy_78shot/weights/best.pt` (already trained).

---

## Strategy (recommended)

| Step | What | Time |
|------|------|------|
| 1 | **Abbreviated photo session** per saber (~28 shots) | ~10 min each |
| 2 | **Green manual boxes** (same as red) | ~15 min each |
| 3 | **Merge** red 78 + pink + yellow into `yolo_multicolor/` | ~5 min |
| 4 | **Fine-tune** from `redtoy_78shot` (~25–30 epochs) | ~15–20 min CPU |
| 5 | **Color profiles** for fast mask path (`--detector color`) | ~2 min each |

**Do not** train from `yolov8n.pt` again unless fine-tune fails.

Optional bootstrap (before real photos): hue-shift the 78 red images to pink/yellow in
Photoshop or a script, add to the merge set, then replace with real photos over time.

---

## Saber IDs & profiles

| Saber | `--saber` id | Runtime profile |
|-------|----------------|-----------------|
| Pink | `pinksaber` | `saber_profiles.py` → `pinksaber` |
| Yellow | `yellowsaber` | `saber_profiles.py` → `yellowsaber` |

HSV ranges in profiles are **starting guesses** — run `calibrate_saber_color.py` after
labeling for each color.

---

## Phase 1 — Capture (~28 shots per saber)

Use the **short session** (same poses for pink and yellow):

```bash
cd projects/lightsaber
source .venv/bin/activate

python collect_saber_trainer.py --saber pinksaber --camera laptop --interval 3 --resume
python collect_saber_trainer.py --saber yellowsaber --camera laptop --interval 3 --resume
```

Output:

- `projects/models/saber_dataset/raw/pinksaber/<horizontal|vertical|diagonal|other>/`
- `projects/models/saber_dataset/raw/yellowsaber/...`

### What the short session covers

| Group | Shots | Why |
|-------|------:|-----|
| Orientations (H / V / diagonal) | 14 | Blade angle variety |
| Strike END poses (L/R/high/center) | 8 | Same as red — sparring extensions |
| Partial / edge | 2 | Tip at frame edge |
| Variety (close / one-hand) | 4 | Scale & grip |

**Same room and camera** as redtoy when possible — only the prop color changes.

---

## Phase 2 — Manual bounding boxes

Per saber (repeat for pink, then yellow):

```bash
python export_for_manual_label.py --saber pinksaber --open
# Draw #00FF00 outline around visible blade only; save each image.

python import_manual_bboxes.py --saber pinksaber --preview
python import_manual_bboxes.py --saber pinksaber --apply --labeled-only --min-green-pixels 0
```

Repeat with `--saber yellowsaber`.

Imports land in:

- `projects/models/saber_dataset/yolo_manual/` (overwrites — **export pink/yellow to side folders first**)

**Safer workflow:** use `--out` per saber:

```bash
python import_manual_bboxes.py --saber pinksaber --apply --labeled-only --min-green-pixels 0 \
  --out ../models/saber_dataset/yolo_pinksaber

python import_manual_bboxes.py --saber yellowsaber --apply --labeled-only --min-green-pixels 0 \
  --out ../models/saber_dataset/yolo_yellowsaber
```

---

## Phase 3 — Merge into one multicolor dataset

Create `projects/models/saber_dataset/yolo_multicolor/`:

```text
yolo_multicolor/
  data.yaml
  train/images/   ← red 78 + pink ~28 + yellow ~28  (~134 total)
  train/labels/
  valid/images/   ← optional: keep red valid + a few pink/yellow
  valid/labels/
```

Copy:

1. All of `yolo_manual/` train (red, 78 images) — your existing red export
2. All of `yolo_pinksaber/train/`
3. All of `yolo_yellowsaber/train/`

`data.yaml`:

```yaml
path: .../yolo_multicolor
train: train/images
val: valid/images
names:
  0: lightsaber
```

Keep **one class** — color is not a label, only the prop bbox.

---

## Phase 4 — Fine-tune YOLO (not full train)

```bash
python train_saber.py \
  --saber multicolor \
  --data ../models/saber_dataset/yolo_multicolor/data.yaml \
  --model ../models/saber_runs/redtoy_78shot/weights/best.pt \
  --epochs 30 \
  --name lightsaber_multicolor_v1
```

Ultralytics treats `--model` as fine-tune when it is a `.pt` checkpoint.

**Stronger color generalization** (optional, in a one-off train script or CLI later):

- `hsv_h=0.3` — heavy hue jitter during training
- `hsv_s=0.7`, `hsv_v=0.4` — defaults are often enough

Expected CPU time: **~15–25 min** for 30 epochs (vs ~45 min for 80 from scratch).

Set in `config.py`:

```python
SABER_MODEL = "../models/saber_runs/lightsaber_multicolor_v1/weights/best.pt"
```

---

## Phase 5 — Color detector (optional, fast per saber)

For `--detector color` preview without relying on YOLO every frame:

```bash
# After manual labels exist under manual_annotate/train for each saber id
python calibrate_saber_color.py --saber pinksaber --split train
python calibrate_saber_color.py --saber yellowsaber --split train
python eval_color_saber.py --saber pinksaber
python saber_preview.py --saber pinksaber --detector color --camera laptop
```

Pink/yellow need **arm corridor + calibrated HSV**, not the red `redtoy` profile.

---

## Phase 6 — Verify

```bash
python eval_saber_overlays.py \
  --model ../models/saber_runs/lightsaber_multicolor_v1/weights/best.pt \
  --data ../models/saber_dataset/yolo_multicolor \
  --out ../models/saber_dataset/multicolor_eval \
  --conf 0.25

python saber_preview.py --saber pinksaber --detector legacy --camera laptop
python saber_preview.py --saber yellowsaber --detector legacy --camera laptop
```

**Pass criteria (pragmatic):**

- Pink/yellow train: **IoU ≥ 0.5** on ≥80% of new shots
- Red train: no major regression vs `redtoy_78shot` eval

If pink/yellow fail but red still works: add **10 more** edge/partial shots for that color
only and fine-tune **10 more epochs** (same multicolor yaml).

---

## Minimal path (one saber color, demo today)

If you only need **pink OR yellow** this session:

1. ~**15** photos (skip short session — 3× horizontal, 3× vertical, 3× diagonal, 2× strike L/R, 2× high, 2× partial)
2. Manual boxes → `yolo_pinksaber` only
3. Merge **red 78 + pink 15** → fine-tune **20 epochs**

~**45 min** total hands-on + ~15 min train.

---

## Timeline summary

| Track | Photos | Train | Total |
|-------|-------:|------:|------:|
| **Both colors (recommended)** | ~56 new + 78 red | 30-epoch fine-tune | ~1.5 hr |
| **One color minimal** | ~15 + 78 red | 20-epoch fine-tune | ~45 min |
| **Synthetic bootstrap** | 0 real (hue-shift red) | 20-epoch fine-tune | ~20 min + real photos later |

---

## Checklist

### Pink

- [ ] `collect_saber_trainer.py --saber pinksaber --interval 3`
- [ ] Green manual boxes → `yolo_pinksaber/`
- [ ] `calibrate_saber_color.py --saber pinksaber`

### Yellow

- [ ] `collect_saber_trainer.py --saber yellowsaber --interval 3`
- [ ] Green manual boxes → `yolo_yellowsaber/`
- [ ] `calibrate_saber_color.py --saber yellowsaber`

### Combined model

- [ ] Merge into `yolo_multicolor/`
- [ ] Fine-tune from `redtoy_78shot` → `lightsaber_multicolor_v1`
- [ ] Update `SABER_MODEL` in `config.py`
- [ ] Preview both sabers + spot-check red regression

See also: **[TRAINING-PLAN.md](TRAINING-PLAN.md)**, **[SABER-TRAINING.md](SABER-TRAINING.md)**, **[DIRECTIONS.md](DIRECTIONS.md)**.
