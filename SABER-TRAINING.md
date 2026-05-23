# Saber YOLO training — redtoy (Mac webcam)

Collect → label → train → plug into `saber_detector.py`.

## Phase 1 — Guided photo session (~60 shots)

```bash
cd projects/lightsaber
source .venv/bin/activate
python collect_saber_trainer.py --saber redtoy --camera laptop
```

The trainer **tells you what to hold** (horizontal, overhead strike, negatives, etc.).  
You press **SPACE** when the pose looks good.

| Key | Action |
|-----|--------|
| SPACE | Save photo |
| s | Skip rest of this prompt |
| b | Previous prompt |
| q | Quit |

Output: `projects/models/saber_dataset/raw/redtoy/<label>/`

Resume a partial session:

```bash
python collect_saber_trainer.py --saber redtoy --camera laptop --resume
```

### Session plan (what you'll be asked)

| Phase | Prompts | ~Photos | Purpose |
|-------|---------|---------|---------|
| Orientations | horizontal ×2, vertical ×2, diagonal ×2 | 38 | Blade angle diversity |
| Strike poses | high, left, right, thrust | 24 | Match sparring directions |
| Variety | close, far, one-hand, off-center | 20 | Generalization |
| Negatives | no saber, partial, at rest | 16 | Reduce false detections |

**Total target: ~98** (OK to stop at 60+ for a first train).

Free-form capture (no prompts): `python collect_saber_data.py --saber redtoy --camera laptop`

---

## Phase 2 — Label bounding boxes

Folder labels (horizontal/vertical/…) are for **organization only**. YOLO needs **one box per saber**, class name e.g. `lightsaber`.

1. Upload `projects/models/saber_dataset/raw/redtoy/**/*.jpg` to [Roboflow](https://roboflow.com) (free tier is fine).
2. Create project → **Object Detection**.
3. Draw a tight box around the **entire saber** (handle + blade) on each image.
4. Single class: `lightsaber` (or `redtoy`).
5. Export **YOLOv8** format → unzip to:
   ```
   projects/models/saber_dataset/yolo/
     data.yaml
     train/images  train/labels
     valid/images  valid/labels
   ```

**Tip:** Roboflow can auto-split train/val and augment (flip, brightness). Start with 80/20 split, light augmentation.

---

## Phase 3 — Train

```bash
cd projects/lightsaber
source .venv/bin/activate
yolo detect train \
  data=../models/saber_dataset/yolo/data.yaml \
  model=yolov8n.pt \
  epochs=50 \
  imgsz=640 \
  project=../models/saber_runs \
  name=redtoy_v1
```

Best weights: `projects/models/saber_runs/redtoy_v1/weights/best.pt`

---

## Phase 4 — Wire into detector

In `config.py` or via profile:

```python
SABER_MODEL = "../models/saber_runs/redtoy_v1/weights/best.pt"
```

Test:

```bash
python saber_preview.py --saber redtoy --camera laptop
```

YOLO boxes snap to the nearest wrist grip in `saber_detector.py` (`_merge_yolo`).

---

## Quality checklist

- [ ] Saber fully visible in most shots (not cropped)
- [ ] Mix of lighting (window vs desk lamp)
- [ ] At least 8 **negative** images (no saber)
- [ ] Labels tight on the prop — not whole body
- [ ] val set includes poses not copied from train (Roboflow split handles this)

## Timeline (solo)

| Step | Time |
|------|------|
| Guided capture | 15–25 min |
| Roboflow labeling | 45–90 min |
| Train yolov8n | 10–30 min on Mac CPU/GPU |
| Preview + tune | 15 min |
