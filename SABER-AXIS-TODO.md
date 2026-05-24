# Saber axis tracking — TODOs & test plan

YOLO outputs an axis-aligned bbox. **Blade axis is post-processed.** These todos improve
line tracking **without retraining** (best on colored sabers like `redtoy`).

## Todos (toggle via `--saber-axis PRESET`)

| ID | Preset | Flag(s) | What it does |
|----|--------|---------|--------------|
| ☐ 0 | `baseline` | *(none)* | Bbox far corner + optional color tip along forearm hint |
| ☐ 1 | `1_color_roi` | `SABER_AXIS_COLOR_ROI` | HSV mask inside YOLO bbox → PCA long axis → tip = farthest red pixel on axis |
| ☐ 2 | `2_color_each` | `SABER_AXIS_COLOR_EACH_FRAME` | Re-run color axis **every frame** using cached bbox (not only on YOLO frames) |
| ☐ 3 | `3_smooth` | `SABER_AXIS_TEMPORAL` | EMA smooth angle + length per hand (`SABER_AXIS_SMOOTH_ALPHA`) |
| ☐ 4 | `4_tip_gate` | `SABER_AXIS_TIP_IN_FRAME`, `SABER_FUSE_REQUIRE_TIP_IN_FRAME` | Mark truncated tips; skip swing fusion when tip off-screen |
| ☐ ✓ | `all` | 1–4 combined | Recommended after each step looks good in preview |

## Default (enabled now)

**`1_color_roi`** is on by default — highest single-factor gain for redtoy (YOLO finds saber,
HSV PCA finds diagonal axis). Override with `--saber-axis baseline` to compare.

## DOE — compare presets on the same clip

One-at-a-time + full stack on identical frames (controls: same video, same YOLO weights).

```bash
# After eval videos exist:
python run_saber_axis_doe.py --saber redtoy \
  --video-dir swing_eval_logs/videos/session_YYYYMMDD_HHMMSS/

# Or quick live capture (5s, swing during capture):
python run_saber_axis_doe.py --saber redtoy --camera laptop --seconds 5

# Subset of factors:
python run_saber_axis_doe.py --saber redtoy --video trial_003.mp4 \
  --presets baseline,1_color_roi,2_color_each,all
```

**Read the table:** prefer higher `composite`; check `jitter°` and `flips` dropped vs baseline.
Report JSON → `swing_eval_logs/saber_axis_doe_*.json` with `recommended` preset.

| Metric | Better |
|--------|--------|
| detect | higher — YOLO line present |
| color_pca | higher — using pixel axis not bbox corner |
| tip_in | higher |
| jitter° | lower — stable angle |
| flips | lower — less horizontal↔vertical bounce |
| composite | higher — weighted rank |

## Manual preview (step-by-step)

```bash
cd projects/lightsaber
source .venv/bin/activate

# Step 0 — current baseline
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis baseline

# Step 1 — color axis in bbox (watch diagonal swings)
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis 1_color_roi

# Step 2 — axis updates between YOLO frames
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis 2_color_each

# Step 3 — less orientation flicker
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis 3_smooth

# Step 4 — fusion ignores bad off-screen tips
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis 4_tip_gate

# Combined
python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis all
```

**Keys:** `q` quit · `m` color mask debug (should show red strip aligned with blade in bbox)

**Look for:** overlay line hugging red blade on diagonals; `[yolo_cached]` frames still
tracking during motion; label shows `trunc` when tip leaves frame.

## Eval session (same flags)

```bash
python collect_swing_eval.py --camera laptop --saber redtoy --detector yolo \
  --saber-axis all --centerline
```

Session JSON logs `saber_axis` snapshot + per-frame `saber_tip_in_frame`, `saber_axis_method`.

## Still needs YOLO retrain (not covered by these todos)

- Saber not detected at all / wrong bbox
- Partial blade with no visible color in ROI
- Non-red sabers without HSV ranges

See `saber_detector.py` module docstring · `SABER-TRAINING.md` · new poses in
`saber_training_plan.py` (`edge_partial`, `centerline_block`, withdraw).

## Future (not implemented)

- [ ] OBB / segmentation YOLO head (angle from model)
- [ ] Export hard frames from `swing_eval_logs/videos/` into training set
- [ ] Disable forearm tip entirely when YOLO+color axis is stable
