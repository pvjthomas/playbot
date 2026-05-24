"""
Canonical direction definitions — camera frame, attacks, robot blocks, and training.

All teams and training prompts should use these terms consistently.

Reference frame
---------------
* **Camera / image frame** — 2D webcam picture. Origin top-left; **x increases to the
  RIGHT** (right side of the screen/monitor). **y increases DOWN**.
* **Partner** — person the camera sees (sparring opponent).
* **Robot** — PiPER behind the camera, facing the partner (mirror of partner view).

Camera mirror (selfie flip)
---------------------------
Some cameras mirror the preview horizontally. Calibrate per device::

    python camera_calibrate_mirror.py --camera laptop

Raise your **anatomical RIGHT hand** — if it appears on the **right side of the
screen**, the camera is **mirror/selfie** mode. If it appears on the **left side**,
it's a **true** (non-mirrored) view. Stored in ``camera_mirror.json``.

Attack labels always use **image left/right** (edges of the picture). Mirror setting
only affects how you interpret posing instructions — see ``image_direction_cheat_sheet()``
in ``camera_mirror.py``.

Motion vs single frame (IMPORTANT)
-----------------------------------
A strike is a **sequence** (e.g. image-left → image-right, overhead → down, chest → thrust).
This project standardizes on one moment for attack naming:

**Label the END of the strike — committed peak extension — not wind-up or mid-swing.**

+---------------+----------------------------------------------------------+
| Motion        | What we label (END pose in the image)                      |
+---------------+----------------------------------------------------------+
| Side swipe    | Saber/arm **fully extended** toward **image-left** or    |
| L↔R           | **image-right** (where the blow finishes)                |
+---------------+----------------------------------------------------------+
| Overhead chop | **Above shoulders**, top of arc before chop down              |
+---------------+----------------------------------------------------------+
| Thrust        | **Fully extended** toward camera at midline (not at chest) |
+---------------+----------------------------------------------------------+

* **Live ``detect_attack()``** — one frame, no motion history; same END-pose rule.
* **Guided photo capture** — with ``--interval 3``, **hold the END pose** for the full
  window so every auto-save matches the label.
* **Direction review** (``review_saber_directions.py``) — “where does the saber point
  **in this still**?” = END pose in the photo.
* **YOLO saber photos** — static blade snapshots; motion phase **does not matter** for
  bbox training (only blade visibility/angle).

See ``STRIKE_CAPTURE_PHASE`` and ``training_prompt_for_attack()`` below.

Temporal swing estimation (planned — robot response)
----------------------------------------------------
Single-frame END-pose detection (above) is enough for **labeling stills** and a first
demo, but the **robot needs timing**: it must start blocking during the swing, not only
when peak extension is already visible.

Vision will add **temporal tracking** over a short frame history (~0.3–0.8 s at camera
FPS). Works **with or without a lightsaber** — track hand/wrist motion (MediaPipe) and
optionally fuse YOLO saber bbox when available.

Swing phase (``SwingPhase`` — proposed in ``contracts.py``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Every active strike passes through three phases in **image space**:

+----------+---------------------------------------------------------------+
| Phase    | Meaning (image frame)                                         |
+----------+---------------------------------------------------------------+
| ``begin``| **Wind-up / commit** — motion starts; dominant travel direction |
|          | becomes visible. Hands at chest or pulled back, then accelerate |
|          | along the strike line.                                        |
+----------+---------------------------------------------------------------+
| ``mid``  | **Mid-swing** — hands/saber moving through the arc; velocity  |
|          | aligned with strike direction. Best window for **early block**. |
+----------+---------------------------------------------------------------+
| ``end``  | **Peak extension** — same as today's END-pose rule; full commit |
|          | before retraction. Triggers **final block** confirmation.      |
+----------+---------------------------------------------------------------+
| ``idle`` | No active swing (at rest, or between strikes).                |
+----------+---------------------------------------------------------------+

Motion kind (``MotionKind`` — proposed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Most attacks are **linear** in the image — a swipe or chop along one axis:

* **Linear** — dominant displacement is along **image left↔right** or **up↔down**
  (side swipes, overhead chops). Direction = sign of velocity on that axis.
* **Thrust** — **exception**: saber/hands start **retracted at chest** and **grow toward
  the camera** (scale increases, both hands move forward along midline). Direction is
  always ``center``; phase is inferred from **expansion** (small → large in frame), not
  lateral velocity.

Detection signals (conceptual)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **Linear** — wrist (or saber tip) velocity vector over N frames; direction from
  dominant axis; phase from speed profile (low → peak → low) and extension vs rest pose.
* **Thrust** — hands near midline + increasing ``extension_min`` / bbox area / optional
  depth (Orbbec) as prop moves toward robot.
* **Without saber** — both wrists or a virtual "grip center" (midpoint of wrists when
  close) is enough for linear swings; thrust uses two-hand chest-to-forward motion.

Robot coordination (for robot/app teams)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Intended use (team agreement still needed):

* ``begin`` +  → pre-guard / alert (optional early move)
* ``mid``      → commit block direction (primary response window)
* ``end``      → hold / confirm block (matches current END-pose semantics)

``detect_attack(frame)`` stays for backward compatibility until ``detect_swing()``
(or equivalent) is wired through ``contracts.py``.

Attack labels (``AttackDirection`` in ``contracts.py``)
-------------------------------------------------------
Names describe **where the strike finishes in the image** (END pose), NOT the partner's
anatomical left/right and NOT the robot's joint left/right.

+----------+------------------------------------------------+---------------------------+
| Label    | END pose in the image (committed extension)    | Robot pose (blocks)       |
+----------+------------------------------------------------+---------------------------+
| ``left`` | Strike **finishes** toward the **LEFT side** of  | ``BLOCK_LEFT``            |
|          | the image (viewer's left edge).                  |                           |
|          | Typical: partner's **right** arm extended across.|                           |
+----------+------------------------------------------------+---------------------------+
| ``right``| Strike **finishes** toward the **RIGHT side**.   | ``BLOCK_RIGHT``           |
|          | Typical: partner's **left** arm extended across. |                           |
+----------+------------------------------------------------+---------------------------+
| ``high`` | **Above shoulders** — top of overhead arc / chop | ``BLOCK_HIGH``            |
|          | (not the downward travel itself).                |                           |
+----------+------------------------------------------------+---------------------------+
| ``center``| **Fully thrust** at the **camera** (midline).   | ``GUARD_CENTER``          |
|          | Arms extended forward — not retracted at chest.   |                           |
+----------+------------------------------------------------+---------------------------+
| ``low``  | Low line toward waist (planned, not live yet). | ``BLOCK_LOW``             |
+----------+------------------------------------------------+---------------------------+
| ``none`` | No attack / at rest.                           | (no move)                 |
+----------+------------------------------------------------+---------------------------+

**Rule of thumb:** ``left`` = saber finishes toward the **left edge** of the photo;
``right`` = finishes toward the **right edge**. Not “which way you were moving.”

Saber YOLO training folders (NOT attack labels)
-----------------------------------------------
Photo collection uses **blade shape**, not attack direction:

* ``horizontal`` — blade roughly level (left↔right in image)
* ``vertical`` — blade roughly up↕down in image
* ``diagonal`` — blade at an angle
* ``other`` — no saber, bad frame, or negative examples

Roboflow / YOLO class is always ``lightsaber`` (bbox around the prop only).

Phase 1 orientation poses (``h_chest``, ``d_l2r``, …) are **static blade angles** —
hold still; no motion phase.

Strike poses in ``saber_training_plan.py`` (e.g. ``strike_left``) use **END-pose**
wording and match ``AttackDirection`` semantics. The **folder** is still ``diagonal`` etc.
"""

from __future__ import annotations

from typing import TypedDict

# Re-export contract type for docs/tools
AttackDirection = str  # see contracts.AttackDirection Literal

ATTACK_DIRECTIONS: tuple[str, ...] = (
    "left",
    "right",
    "high",
    "center",
    "low",
    "none",
)

SABER_DATASET_FOLDERS: tuple[str, ...] = (
    "horizontal",
    "vertical",
    "diagonal",
    "other",
)

# Photo capture + human L/R review: committed end of strike (not wind-up / mid-swing).
STRIKE_CAPTURE_PHASE = "end"


class DirectionSpec(TypedDict):
    label: str
    image_meaning: str
    partner_typical: str
    robot_pose: str


ATTACK_SPECS: dict[str, DirectionSpec] = {
    "left": {
        "label": "left",
        "image_meaning": "END pose: saber extended toward the LEFT side of the image",
        "partner_typical": "Partner's right arm crosses body, fully extended image-left",
        "robot_pose": "BLOCK_LEFT",
    },
    "right": {
        "label": "right",
        "image_meaning": "END pose: saber extended toward the RIGHT side of the image",
        "partner_typical": "Partner's left arm crosses body, fully extended image-right",
        "robot_pose": "BLOCK_RIGHT",
    },
    "high": {
        "label": "high",
        "image_meaning": "END of overhead arc — above shoulders, before/at chop down",
        "partner_typical": "Either arm raised above shoulder line",
        "robot_pose": "BLOCK_HIGH",
    },
    "center": {
        "label": "center",
        "image_meaning": "END of thrust — fully extended toward camera at midline",
        "partner_typical": "Both hands extended forward at chest center",
        "robot_pose": "GUARD_CENTER",
    },
    "low": {
        "label": "low",
        "image_meaning": "Low line toward waist (planned)",
        "partner_typical": "Wrists below hips",
        "robot_pose": "BLOCK_LOW",
    },
    "none": {
        "label": "none",
        "image_meaning": "No attack",
        "partner_typical": "Arms relaxed or untracked",
        "robot_pose": "(none)",
    },
}


def training_prompt_for_attack(attack: str) -> str:
    """Short prompt for guided photo session — END pose, image-frame wording."""
    hold = "HOLD this END pose for the whole capture window (not wind-up)."
    prompts = {
        "left": (
            "Attack LEFT — swing toward IMAGE LEFT, then HOLD the END: saber fully "
            "extended toward the LEFT edge of the screen. "
            f"{hold} NOT your body's left/right."
        ),
        "right": (
            "Attack RIGHT — swing toward IMAGE RIGHT, then HOLD the END: saber fully "
            f"extended toward the RIGHT edge of the screen. {hold}"
        ),
        "high": (
            "Attack HIGH — raise saber above your head to the TOP of the chop, then "
            f"HOLD overhead (above shoulders). {hold}"
        ),
        "center": (
            "Attack CENTER — thrust from chest outward to full extension at the camera, "
            f"then HOLD the extended END (midline). {hold}"
        ),
    }
    return prompts.get(attack, ATTACK_SPECS.get(attack, {}).get("image_meaning", attack))


def print_direction_legend() -> None:
    """Print once at start of guided training session."""
    print("\n=== Direction legend (read carefully) ===")
    print("Strike names = where the saber FINISHES in the PHOTO (END pose / peak extension).")
    print("  NOT wind-up. NOT mid-swing. HOLD the end pose during auto-capture.")
    print("  left  = extended toward LEFT side of image  (→ robot BLOCK_LEFT)")
    print("  right = extended toward RIGHT side of image (→ robot BLOCK_RIGHT)")
    print("  NOT your anatomical left/right. NOT the robot arm's physical left.")
    print("YOLO folders (horizontal/vertical/diagonal) = static blade angle, not attacks.")
    print("==========================================\n")
