# Vision & saber training plan — index

Central index for **attack direction semantics**, **vision milestones**, and **saber YOLO /
color detection** training. Read **DIRECTIONS.md** first for labeling rules.

---

## Documents

| Doc | Contents |
|-----|----------|
| **[DIRECTIONS.md](DIRECTIONS.md)** | Attack labels, END pose, temporal swing phases, YOLO folders |
| **[task-vision.md](task-vision.md)** | Vision developer milestones, contracts, saber detector notes |
| **[SABER-TRAINING.md](SABER-TRAINING.md)** | Red saber (`redtoy`) — collect → label → train → preview |
| **[SABER-PINK-YELLOW.md](SABER-PINK-YELLOW.md)** | Pink & yellow sabers — fine-tune from red weights |

**Code references:** `directions.py`, `saber_training_plan.py`, `saber_profiles.py`, `contracts.py`

---

## Vision milestones (summary)

| Milestone | Goal | Status |
|-----------|------|--------|
| **M1** | Single-frame `detect_attack()` — END pose via MediaPipe | Current sprint |
| **M2** | Temporal `begin` / `mid` / `end` + linear vs thrust | Priority for robot |
| **M3** | `low` attack, false-positive reduction, optional YOLO person gate | Planned |
| **M4** | FPS, overlay polish, tests | Planned |

Details: **task-vision.md**

---

## Saber detection paths

| Path | Speed | When to use |
|------|-------|-------------|
| **Pose only** | Fastest | Demo fight loop today (`detect_attack`) |
| **Color + pose** | ~5–15 ms/frame | Distinct blade color; `calibrate_saber_color.py`, `--detector color` |
| **YOLO + pose** | ~50–100 ms/frame | Tight bboxes, partial blades, multicolor |

**Current YOLO weights (red, 78 manual labels):**

```text
projects/models/saber_runs/redtoy_78shot/weights/best.pt
```

Set in `config.py` as `SABER_MODEL`.

---

## Red saber (`redtoy`) — completed baseline

1. **Capture** — `collect_saber_trainer.py --saber redtoy --interval 3` (~60 poses)
2. **Manual boxes** — green outline → `import_manual_bboxes.py --apply`
3. **Train** — `train_saber.py` → `redtoy_78shot` (78 train images)
4. **Eval** — `eval_saber_overlays.py` — train mean IoU ~0.90

Full steps: **SABER-TRAINING.md**

### Quick commands (red)

```bash
cd projects/lightsaber && source .venv/bin/activate

python collect_saber_trainer.py --saber redtoy --camera laptop --interval 3
python export_for_manual_label.py --saber redtoy --open
python import_manual_bboxes.py --saber redtoy --apply --labeled-only --min-green-pixels 0
python train_saber.py --data ../models/saber_dataset/yolo_manual/data.yaml \
  --name redtoy_78shot --epochs 80
python saber_preview.py --saber redtoy --detector legacy --camera laptop
```

---

## Pink & yellow sabers — next steps

Same shape as red; **fine-tune** from `redtoy_78shot` (~30 epochs), do not retrain from scratch.

| Saber ID | Profile | Short session shots |
|----------|---------|-------------------|
| `pinksaber` | `saber_profiles.py` → `pinksaber` | ~28 (`MULTICOLOR_SHORT_SESSION`) |
| `yellowsaber` | `saber_profiles.py` → `yellowsaber` | ~28 |

1. Capture both with `collect_saber_trainer.py --saber pinksaber|yellowsaber`
2. Manual boxes → `yolo_pinksaber/`, `yolo_yellowsaber/`
3. Merge with red 78 → `yolo_multicolor/`
4. Fine-tune: `--model ../models/saber_runs/redtoy_78shot/weights/best.pt --epochs 30 --name lightsaber_multicolor_v1`

Full plan: **SABER-PINK-YELLOW.md**

---

## Color detector (optional, per saber)

Calibrate HSV from manual labels — no YOLO required:

```bash
python calibrate_saber_color.py --saber redtoy    # or pinksaber / yellowsaber
python eval_color_saber.py --saber redtoy
python saber_preview.py --saber redtoy --detector color --camera laptop
```

Output: `projects/models/saber_color/<saber_id>_calibration.json`

Good for preview and temporal tip velocity; YOLO remains better for bbox IoU on train set.

---

## Saber profiles

```bash
python saber_preview.py --saber redtoy --camera laptop
python saber_preview.py --saber pinksaber --detector color --camera laptop
```

Profiles in **`saber_profiles.py`**: `redtoy`, `pinksaber`, `yellowsaber`. Run
`calibrate_saber_color.py` after labeling to refine HSV.

---

## Dataset layout

```text
projects/models/
  saber_dataset/
    raw/<saber_id>/              # collect_saber_trainer output
    manual_annotate/{train,valid}/  # green box drawings
    yolo_manual/                 # red 78 — current best train set
    yolo_pinksaber/              # (after pink import)
    yolo_yellowsaber/            # (after yellow import)
    yolo_multicolor/             # merged — fine-tune target
    saber_color/                 # HSV calibrations
  saber_runs/
    redtoy_78shot/               # current production weights
    lightsaber_multicolor_v1/    # (after pink+yellow fine-tune)
```

---

## Timeline cheat sheet

| Task | Time |
|------|------|
| Red full session + label + train (done) | ~1 hr |
| Pink or yellow short session + label | ~25 min each |
| Multicolor fine-tune (30 epochs, CPU) | ~15–20 min |
| Color calibrate + eval per saber | ~5 min |
