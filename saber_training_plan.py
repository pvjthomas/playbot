"""
Guided saber photo session — prompts for each pose before you capture.

Used by collect_saber_trainer.py. Images land in:
  projects/models/saber_dataset/raw/<saber_id>/<label>/

YOLO training still needs bbox labels (Roboflow / CVAT) after collection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionPose:
    """One prompt in a guided session."""

    id: str
    label: str  # folder: horizontal | vertical | diagonal | other
    prompt: str
    count: int
    phase: str = ""


# ~60 shots — enough to start YOLO; add more if detection is weak
REDTOY_SESSION: list[CollectionPose] = [
    # Phase 1 — clear orientations (face camera, waist up in frame)
    CollectionPose(
        "h_chest",
        "horizontal",
        "Horizontal — blade left↔right at chest height, both hands optional, face camera",
        8,
        "Orientations",
    ),
    CollectionPose(
        "h_low",
        "horizontal",
        "Horizontal — blade low near waist / hip level",
        5,
        "Orientations",
    ),
    CollectionPose(
        "v_overhead",
        "vertical",
        "Vertical — blade pointing UP (overhead / high guard)",
        8,
        "Orientations",
    ),
    CollectionPose(
        "v_down",
        "vertical",
        "Vertical — blade pointing DOWN (low guard or rest)",
        5,
        "Orientations",
    ),
    CollectionPose(
        "d_l2r",
        "diagonal",
        "Diagonal — blade angled up toward the LEFT side of the image (↖ on screen)",
        6,
        "Orientations",
    ),
    CollectionPose(
        "d_r2l",
        "diagonal",
        "Diagonal — blade angled up toward the RIGHT side of the image (↗ on screen)",
        6,
        "Orientations",
    ),
    # Phase 2 — strike END poses (names match AttackDirection = body cross-body)
    CollectionPose(
        "strike_high",
        "vertical",
        "Attack HIGH — top of overhead chop; HOLD saber above head (END of raise, "
        "vision label 'high')",
        6,
        "Strike poses",
    ),
    CollectionPose(
        "strike_left",
        "diagonal",
        "Attack LEFT — RIGHT arm to YOUR LEFT; swing right → left, HOLD END on YOUR LEFT "
        "(not wind-up; → robot BLOCK_LEFT)",
        6,
        "Strike poses",
    ),
    CollectionPose(
        "strike_right",
        "diagonal",
        "Attack RIGHT — LEFT arm to YOUR RIGHT; swing left → right, HOLD END on YOUR RIGHT "
        "(not wind-up; → robot BLOCK_RIGHT)",
        6,
        "Strike poses",
    ),
    CollectionPose(
        "strike_center",
        "vertical",
        "Attack CENTER — thrust out to full extension at camera, HOLD the END "
        "(vision label 'center')",
        6,
        "Strike poses",
    ),
    # Phase 3 — variety (helps YOLO generalize)
    CollectionPose(
        "var_close",
        "horizontal",
        "Move CLOSER — saber fills more of the frame (still horizontal)",
        5,
        "Variety",
    ),
    CollectionPose(
        "var_far",
        "horizontal",
        "Step BACK — full upper body + saber visible",
        5,
        "Variety",
    ),
    CollectionPose(
        "var_one_hand",
        "diagonal",
        "One-hand grip — any diagonal angle you like",
        5,
        "Variety",
    ),
    CollectionPose(
        "var_off_center",
        "horizontal",
        "Stand to the LEFT or RIGHT of frame center (not centered)",
        5,
        "Variety",
    ),
    # Phase 4 — negatives / edge cases
    CollectionPose(
        "neg_no_saber",
        "other",
        "NO saber — empty hands or arms at sides (negative examples)",
        8,
        "Negatives",
    ),
    CollectionPose(
        "neg_partial",
        "other",
        "Saber partially out of frame OR behind your back",
        4,
        "Negatives",
    ),
    CollectionPose(
        "neg_rest",
        "other",
        "Saber pointing down at rest — relaxed stance",
        4,
        "Negatives",
    ),
    # Phase 5 — live-eval gaps (positive partial blades; do NOT use other/neg_partial)
    CollectionPose(
        "edge_partial",
        "diagonal",
        "Wide extension — tip at or past frame edge; label VISIBLE blade only (positive)",
        8,
        "Edge cases",
    ),
    CollectionPose(
        "centerline_block",
        "diagonal",
        "Centerline block — cross-body strike STOPPED at body midline, hold for robot block",
        6,
        "Edge cases",
    ),
    CollectionPose(
        "withdraw_left",
        "horizontal",
        "Withdraw LEFT — after right strike blocked: pull saber back toward YOUR LEFT",
        4,
        "Edge cases",
    ),
    CollectionPose(
        "withdraw_right",
        "horizontal",
        "Withdraw RIGHT — after left strike blocked: pull saber back toward YOUR RIGHT",
        4,
        "Edge cases",
    ),
]

# ~28 shots — fine-tune add-on for new blade colors (same shape as redtoy)
MULTICOLOR_SHORT_SESSION: list[CollectionPose] = [
    CollectionPose("h_chest", "horizontal", "Horizontal — blade left↔right at chest height", 4, "Orientations"),
    CollectionPose("v_overhead", "vertical", "Vertical — blade pointing UP", 3, "Orientations"),
    CollectionPose("v_down", "vertical", "Vertical — blade pointing DOWN", 3, "Orientations"),
    CollectionPose("d_l2r", "diagonal", "Diagonal — blade angled toward IMAGE LEFT", 3, "Orientations"),
    CollectionPose("d_r2l", "diagonal", "Diagonal — blade angled toward IMAGE RIGHT", 3, "Orientations"),
    CollectionPose("strike_left", "diagonal", "Attack LEFT — HOLD END on YOUR LEFT side", 2, "Strike poses"),
    CollectionPose("strike_right", "diagonal", "Attack RIGHT — HOLD END on YOUR RIGHT side", 2, "Strike poses"),
    CollectionPose("strike_high", "vertical", "Attack HIGH — HOLD saber above shoulders", 2, "Strike poses"),
    CollectionPose("strike_center", "vertical", "Attack CENTER — full thrust at camera, HOLD END", 2, "Strike poses"),
    CollectionPose("edge_partial", "diagonal", "Wide extension — tip at or past frame edge (visible blade only)", 2, "Edge cases"),
    CollectionPose("var_close", "horizontal", "Move CLOSER — saber fills more of frame", 2, "Variety"),
    CollectionPose("var_one_hand", "diagonal", "One-hand grip — any diagonal", 2, "Variety"),
]

SESSIONS: dict[str, list[CollectionPose]] = {
    "redtoy": REDTOY_SESSION,
    "pinksaber": MULTICOLOR_SHORT_SESSION,
    "yellowsaber": MULTICOLOR_SHORT_SESSION,
}


def session_for(saber_id: str) -> list[CollectionPose]:
    key = saber_id.strip().lower().replace("/", "_")
    if key not in SESSIONS:
        known = ", ".join(sorted(SESSIONS))
        raise ValueError(f"No session plan for {saber_id!r}. Known: {known}")
    return SESSIONS[key]


def session_summary(poses: list[CollectionPose]) -> dict[str, int]:
    total = sum(p.count for p in poses)
    by_label: dict[str, int] = {}
    for p in poses:
        by_label[p.label] = by_label.get(p.label, 0) + p.count
    return {"total": total, "by_label": by_label, "poses": len(poses)}
