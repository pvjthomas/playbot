"""
Canonical direction definitions — camera frame, attacks, robot blocks, and training.

Human-readable export: **DIRECTIONS.md** (keep in sync with this module).
Training index: **TRAINING-PLAN.md**.

All teams and training prompts should use these terms consistently.

Reference frame
---------------
* **Camera / image frame** — 2D webcam picture. Origin top-left; **x increases to the
  RIGHT** (right side of the screen/monitor). **y increases DOWN**.
* **Partner** — person the camera sees (sparring opponent).
* **Robot** — PiPER behind the camera, facing the partner (mirror of partner view).

Wrist / Orbbec orientation (rotation + flip)
--------------------------------------------
Wrist-mounted cameras may deliver **sideways or upside-down** frames. Calibrate at
robot guard pose so partner's head is toward the **top** of the image and image-left
matches ``directions.py``::

    python camera_calibrate_orientation.py --camera piper

Then enable ``CAMERA_APPLY_ORIENTATION_CORRECTION`` in ``config.py``. See
``camera_orientation.py`` and **task-vision.md** § *Wrist-mounted Orbbec*.

Camera mirror (selfie flip)
---------------------------
Some cameras mirror the preview horizontally. Calibrate per device::

    python camera_calibrate_mirror.py --camera laptop

Raise your **anatomical RIGHT hand** — if it appears on the **right side of the
screen**, the camera is **mirror/selfie** mode. If it appears on the **left side**,
it's a **true** (non-mirrored) view. Stored in ``camera_mirror.json``.

Attack labels use **body cross-body direction** (YOUR left/right), aligned with swing
eval prompts and robot blocks — not raw “toward the left edge of the JPEG.” Mirror
setting still matters for how you interpret the preview; see ``image_direction_cheat_sheet()``
in ``camera_mirror.py``.

Motion vs single frame (IMPORTANT)
-----------------------------------
A strike is a **sequence** (e.g. your right → your left, overhead → down, chest → thrust).
This project standardizes on one moment for attack naming:

**Label the END of the strike — committed peak extension — not wind-up or mid-swing.**

+---------------+----------------------------------------------------------+
| Motion        | What we label (END pose — body side)                       |
+---------------+----------------------------------------------------------+
| Side swipe    | Arm/saber **fully extended** on **YOUR LEFT** or         |
| L↔R           | **YOUR RIGHT** (where the blow finishes on your body)    |
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
Names describe **body-relative cross-body strikes** (partner facing the camera),
aligned with swing eval prompts and robot blocks. **Not** raw screen-edge compass
unless you explicitly use photo-training prompts.

+----------+------------------------------------------------+---------------------------+
| Label    | Meaning (partner facing camera)                | Robot pose (blocks)       |
+----------+------------------------------------------------+---------------------------+
| ``left`` | Cross-body to **YOUR LEFT** — right arm;       | ``BLOCK_LEFT``            |
|          | travel **your right → your left**; finish on   |                           |
|          | your left (true cam: toward **image-right**).  |                           |
+----------+------------------------------------------------+---------------------------+
| ``right``| Cross-body to **YOUR RIGHT** — left arm;       | ``BLOCK_RIGHT``           |
|          | travel **your left → your right**; finish on   |                           |
|          | your right (true cam: toward **image-left**).  |                           |
+----------+------------------------------------------------+---------------------------+
| ``high`` | **Above shoulders** — top of overhead arc / chop | ``BLOCK_HIGH``            |
+----------+------------------------------------------------+---------------------------+
| ``center``| **Fully thrust** at the **camera** (midline).   | ``GUARD_CENTER``          |
+----------+------------------------------------------------+---------------------------+
| ``low``  | Low line toward waist (planned).               | ``BLOCK_LOW``             |
+----------+------------------------------------------------+---------------------------+
| ``none`` | No attack / at rest.                           | (no move)                 |
+----------+------------------------------------------------+---------------------------+

**Temporal motion (``begin``/``mid``):** horizontal velocity uses the same body
semantics — ``left`` = dominant travel toward **your left** (+image-x on a true
camera facing you).

**END pose (``end`` / ``detect_attack``):** committed extension on **your left**
(right arm across) or **your right** (left arm across), not “saber toward the
left edge of the JPEG.”

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
        "image_meaning": "Cross-body to YOUR LEFT — right arm; finish on your left side",
        "partner_typical": "Right arm crosses body; travel your right → your left",
        "robot_pose": "BLOCK_LEFT",
    },
    "right": {
        "label": "right",
        "image_meaning": "Cross-body to YOUR RIGHT — left arm; finish on your right side",
        "partner_typical": "Left arm crosses body; travel your left → your right",
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
    """Short prompt for guided photo session — END pose, body strike wording."""
    hold = "HOLD this END pose for the whole capture window (not wind-up)."
    prompts = {
        "left": (
            "Attack LEFT — RIGHT arm crosses body to YOUR LEFT; swing right → left, "
            f"then HOLD fully extended on YOUR LEFT. {hold}"
        ),
        "right": (
            "Attack RIGHT — LEFT arm crosses body to YOUR RIGHT; swing left → right, "
            f"then HOLD fully extended on YOUR RIGHT. {hold}"
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


# Body-based prompts for live training / swing eval (mirror-independent).
SWING_RECOVERY_HINT = (
    "After each finish: pull the saber back — tuck elbow, rotate grip so the blade "
    "passes behind your shoulder or rests low at your hip (out of the camera's view). "
    "Pause there before the next swing so detection returns to idle."
)


def body_expect_label(attack: str) -> str:
    """One-line HUD label — anatomical, not image left/right."""
    labels = {
        "left": "RIGHT arm → finish on YOUR LEFT",
        "right": "LEFT arm → finish on YOUR RIGHT",
        "high": "Raise over head → chop DOWN",
        "center": "Both hands → thrust FORWARD (chest out)",
        "none": "Rest — saber behind back or at hip",
    }
    return labels.get(attack, attack)


def body_prompt_for_attack(attack: str) -> str:
    """Guided swing prompt using your body, not screen edges."""
    recovery = SWING_RECOVERY_HINT
    prompts = {
        "left": (
            "LEFT strike — use your RIGHT arm. Start on your right side, swing across "
            "your chest, and FINISH fully extended on YOUR LEFT. "
            f"{recovery}"
        ),
        "right": (
            "RIGHT strike — use your LEFT arm. Start on your left side, swing across "
            "your chest, and FINISH fully extended on YOUR RIGHT. "
            f"{recovery}"
        ),
        "high": (
            "HIGH strike — raise hands/saber over your head, then CHOP DOWN through "
            "the arc (raise → peak → downward strike). "
            f"{recovery}"
        ),
        "center": (
            "CENTER thrust — both hands at chest, push straight out to full extension "
            f"toward the camera, FINISH extended. {recovery}"
        ),
    }
    return prompts.get(attack, ATTACK_SPECS.get(attack, {}).get("image_meaning", attack))


CENTERLINE_GET_READY = (
    "GET READY at CENTERLINE — hold the blocked pose: saber stopped at midline as if "
    "the robot just blocked your cross-body strike. Arms extended at center. Hold still."
)

CENTERLINE_REST_READY = (
    "Get into START position — saber behind your back, low at your hip, or tucked "
    "out of view. Arms relaxed. Hold still until the countdown ends."
)


def body_prompt_centerline_strike(direction: str) -> str:
    arm = "RIGHT" if direction == "left" else "LEFT"
    return (
        f"{direction.upper()} strike — {arm} arm swings across your body but STOP at "
        "the midline (robot blocks you there). HOLD the blocked pose at center during "
        "the recording window. Do ONE strike when recording starts."
    )


def body_prompt_withdraw(withdraw_direction: str, *, after_strike: str) -> str:
    strike = after_strike.upper()
    wd = withdraw_direction.upper()
    return (
        f"WITHDRAW toward YOUR {wd} — start from centerline (blocked after {strike} "
        f"strike). Pull saber back across your body toward YOUR {wd} during the 3s "
        "window. One smooth retreat."
    )


def body_expect_centerline_strike(direction: str) -> str:
    return f"{direction.upper()} strike → STOP at centerline"


def body_expect_withdraw(direction: str, *, after_strike: str) -> str:
    return f"Withdraw YOUR {direction.upper()} (after {after_strike} block)"


def print_body_direction_legend() -> None:
    """Print at start of swing eval / body-guided sessions."""
    print("\n=== Swing directions (YOUR body) ===")
    print("  LEFT  = RIGHT arm: travel YOUR RIGHT → YOUR LEFT, finish on YOUR LEFT")
    print("  RIGHT = LEFT arm:  travel YOUR LEFT → YOUR RIGHT, finish on YOUR RIGHT")
    print("  HIGH  = raise over head, chop downward (full arc)")
    print("  CENTER = straight thrust forward from chest")
    print("  Between reps: retract saber behind shoulder/back or low at hip.")
    print("===================================\n")


def print_centerline_eval_legend() -> None:
    """Print at start of --centerline eval sessions."""
    print("\n=== Centerline eval (robot blocks at midline) ===")
    print("  Strike LEFT  → stop at centerline → withdraw RIGHT")
    print("  Strike RIGHT → stop at centerline → withdraw LEFT")
    print("  Each pair: strike trial, then withdraw trial (SPACE between trials).")
    print("================================================\n")


def strike_from_image_dx(dx: float, min_mag: float) -> AttackDirection:
    """
    Map horizontal image delta → body-named side strike.

    Partner facing camera (true cam): +dx = toward your left = ``left`` strike.
    """
    if dx >= min_mag:
        return "left"
    if dx <= -min_mag:
        return "right"
    return "none"


def side_end_pose_from_x(
    x: float, center_x: float, margin: float, *, extended: bool
) -> AttackDirection:
    """END extension on your left (high x) or your right (low x)."""
    if not extended:
        return "none"
    if x > center_x + margin:
        return "left"
    if x < center_x - margin:
        return "right"
    return "none"


def print_direction_legend() -> None:
    """Print once at start of guided training session."""
    print("\n=== Direction legend (read carefully) ===")
    print("Strike names = body cross-body direction + END pose (peak extension).")
    print("  NOT wind-up. NOT mid-swing. HOLD the end pose during auto-capture.")
    print("  left  = YOUR RIGHT → YOUR LEFT  (→ robot BLOCK_LEFT)")
    print("  right = YOUR LEFT → YOUR RIGHT (→ robot BLOCK_RIGHT)")
    print("YOLO folders (horizontal/vertical/diagonal) = static blade angle, not attacks.")
    print("==========================================\n")
