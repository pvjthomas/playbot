# Direction definitions — attacks, robot blocks, training

**Canonical source in code:** `directions.py` (keep in sync when semantics change).

All teams, photo capture, and labeling should use these terms consistently.

---

## Reference frame

- **Camera / image frame** — 2D webcam picture. Origin top-left; **x increases RIGHT**; **y increases DOWN**.
- **Partner** — person the camera sees (sparring opponent).
- **Robot** — PiPER behind the camera, facing the partner.

### Wrist-mounted camera orientation

Wrist-mounted cameras may deliver rotated or flipped frames. Calibrate at robot guard pose
so the partner's head is toward the **top** of the image:

```bash
python camera_calibrate_orientation.py --camera piper
```

Enable `CAMERA_APPLY_ORIENTATION_CORRECTION` in `config.py`. See `camera_orientation.py` and
**task-vision.md** § *Wrist-mounted Orbbec*.

### Camera mirror (selfie flip)

```bash
python camera_calibrate_mirror.py --camera laptop
```

Raise your **anatomical RIGHT hand** — if it appears on the **right side of the screen**,
the camera is mirror/selfie mode.

**Attack labels always use image left/right** (edges of the picture), not anatomical
left/right.

---

## Motion vs single frame

A strike is a **sequence**. For **labeling stills** and today's `detect_attack()`:

**Label the END of the strike — committed peak extension — not wind-up or mid-swing.**

| Motion | What we label (END pose in the image) |
|--------|----------------------------------------|
| Side swipe L↔R | Arm/saber **fully extended** toward **image-left** or **image-right** |
| Overhead chop | **Above shoulders** — top of arc |
| Thrust | **Fully extended** toward camera at midline (not retracted at chest) |

- **Live `detect_attack()`** — one frame, no motion history; same END-pose rule.
- **Guided photo capture** — with `--interval 3`, **hold the END pose** for the full window.
- **YOLO saber photos** — static blade snapshots; motion phase does not matter for bbox training.

---

## Temporal swing estimation (planned — robot response)

Single-frame END-pose is enough for labeling; the **robot needs timing** to block during
the swing. Vision will add **temporal tracking** over ~0.3–0.8 s. Works **with or without
a lightsaber** (MediaPipe wrists; optional YOLO fusion).

### Swing phases (`SwingPhase` — proposed in `contracts.py`)

| Phase | Meaning | Robot use (proposed) |
|-------|---------|----------------------|
| `idle` | At rest, between strikes | No move |
| `begin` | Wind-up; strike direction becomes visible | Optional early guard |
| `mid` | Active travel through the arc | **Primary block window** |
| `end` | Peak extension (today's END-pose rule) | Confirm / hold block |

### Motion kind (`MotionKind` — proposed)

| Kind | Description |
|------|-------------|
| **Linear** | Side swipes, overhead chops — dominant travel along image L↔R or U↕D |
| **Thrust** | Hands start at chest and **grow toward camera**; direction always `center`; phase from expansion, not lateral velocity |

### Detection (conceptual)

- **Linear** — wrist/saber velocity over N frames; direction from dominant axis; phase from speed + extension.
- **Thrust** — midline hands + increasing extension / bbox scale / optional depth.
- **Without saber** — wrist midpoint or both wrists; thrust = two-hand chest-to-forward motion.

Full vision checklist: **task-vision.md** Milestone 2.

---

## Attack labels (`AttackDirection`)

Names describe **where the strike finishes in the image** (END pose), NOT anatomical
left/right and NOT the robot joint names.

| Label | END pose in the image | Robot pose |
|-------|----------------------|------------|
| `left` | Finishes toward **LEFT edge** of image (typical: partner's right arm crosses) | `BLOCK_LEFT` |
| `right` | Finishes toward **RIGHT edge** of image (typical: partner's left arm crosses) | `BLOCK_RIGHT` |
| `high` | **Above shoulders** — top of overhead arc | `BLOCK_HIGH` |
| `center` | **Fully thrust** at camera midline | `GUARD_CENTER` |
| `low` | Low line toward waist (planned, not live) | `BLOCK_LOW` |
| `none` | No attack / at rest | (no move) |

**Rule of thumb:** `left` = finishes toward the **left edge** of the photo; `right` = **right edge**.
Not “which way you were moving.”

---

## Saber YOLO folders (NOT attack labels)

Photo collection uses **blade shape**, not attack direction:

| Folder | Meaning |
|--------|---------|
| `horizontal` | Blade roughly level in image |
| `vertical` | Blade roughly up↕down |
| `diagonal` | Blade at an angle |
| `other` | No saber, bad frame, negatives |

YOLO class is always **`lightsaber`** (bbox around the prop only).

Strike poses in `saber_training_plan.py` (e.g. `strike_left`) use END-pose wording and
match `AttackDirection` semantics; the **folder** is still `diagonal`, etc.

---

## Partial saber visibility

During real strikes the **grip often stays in frame** while the **tip crosses or leaves**
the edge. For YOLO labels, draw the box around **visible blade only** — do not extend past
the frame. Collect **positive** partial-blade examples (not only `neg_partial` in `other/`).

Runtime notes: **task-vision.md** § *Tip in frame vs tip out of frame*.

---

## Training prompts (END pose)

Hold wording for guided capture (`training_prompt_for_attack()` in code):

- **left** — Swing toward IMAGE LEFT, then HOLD full extension toward the **left edge** of the screen.
- **right** — Swing toward IMAGE RIGHT, then HOLD toward the **right edge**.
- **high** — Raise saber above head to TOP of chop; HOLD overhead (above shoulders).
- **center** — Thrust from chest to full extension at camera; HOLD midline END.

Always: **NOT wind-up. NOT mid-swing.**
