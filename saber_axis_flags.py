"""
Saber axis tracking — toggleable improvements (test one-by-one or combined).

YOLO finds *where* the saber is; these flags control *how* grip→tip axis is fit.

Presets (use ``--saber-axis PRESET`` on saber_preview / collect_swing_eval):

  baseline     — bbox corner tip only (legacy path before axis todos)
  1_color_roi  — PCA/color axis inside YOLO bbox (diagonal blades)
  2_color_each — re-fit color axis every frame using cached bbox (between YOLO runs)
  3_smooth     — temporal EMA on blade angle + length
  4_tip_gate   — tip_in_frame flag; skip swing fusion when tip extrapolated off-screen
  all          — enable 1–4 together

Examples::

  python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis baseline
  python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis 1_color_roi
  python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis all
  python collect_swing_eval.py --camera laptop --saber redtoy --saber-axis 2_color_each
"""

from __future__ import annotations

import config

# Config keys owned by axis todos (reset before applying a preset)
AXIS_FLAG_KEYS: tuple[str, ...] = (
    "SABER_AXIS_COLOR_ROI",
    "SABER_AXIS_COLOR_EACH_FRAME",
    "SABER_AXIS_TEMPORAL",
    "SABER_AXIS_TIP_IN_FRAME",
    "SABER_FUSE_REQUIRE_TIP_IN_FRAME",
)

PRESETS: dict[str, dict[str, bool]] = {
    "baseline": {},
    "1_color_roi": {"SABER_AXIS_COLOR_ROI": True},
    "2_color_each": {
        "SABER_AXIS_COLOR_ROI": True,
        "SABER_AXIS_COLOR_EACH_FRAME": True,
    },
    "3_smooth": {
        "SABER_AXIS_COLOR_ROI": True,
        "SABER_AXIS_COLOR_EACH_FRAME": True,
        "SABER_AXIS_TEMPORAL": True,
    },
    "4_tip_gate": {
        "SABER_AXIS_COLOR_ROI": True,
        "SABER_AXIS_COLOR_EACH_FRAME": True,
        "SABER_AXIS_TEMPORAL": True,
        "SABER_AXIS_TIP_IN_FRAME": True,
        "SABER_FUSE_REQUIRE_TIP_IN_FRAME": True,
    },
    "all": {
        "SABER_AXIS_COLOR_ROI": True,
        "SABER_AXIS_COLOR_EACH_FRAME": True,
        "SABER_AXIS_TEMPORAL": True,
        "SABER_AXIS_TIP_IN_FRAME": True,
        "SABER_FUSE_REQUIRE_TIP_IN_FRAME": True,
    },
}


# Ordered for one-at-a-time DOE (baseline → cumulative → full stack)
DOE_PRESET_ORDER: tuple[str, ...] = (
    "baseline",
    "1_color_roi",
    "2_color_each",
    "3_smooth",
    "4_tip_gate",
    "all",
)


def apply_axis_preset(name: str) -> list[str]:
    """Reset axis flags, apply preset; returns human-readable enabled list."""
    key = name.strip().lower()
    if key not in PRESETS:
        known = ", ".join(list_axis_presets())
        raise ValueError(f"Unknown saber-axis preset {name!r}. Known: {known}")

    for attr in AXIS_FLAG_KEYS:
        setattr(config, attr, False)

    enabled: list[str] = []
    for attr, value in PRESETS[key].items():
        setattr(config, attr, value)
        if value:
            enabled.append(attr)

    config.SABER_AXIS_PRESET = key
    return enabled


def axis_flags_snapshot() -> dict[str, bool | str | float]:
    snap: dict[str, bool | str | float] = {
        k: bool(getattr(config, k, False)) for k in AXIS_FLAG_KEYS
    }
    snap["SABER_AXIS_PRESET"] = getattr(config, "SABER_AXIS_PRESET", "baseline")
    snap["SABER_AXIS_SMOOTH_ALPHA"] = float(
        getattr(config, "SABER_AXIS_SMOOTH_ALPHA", 0.45)
    )
    return snap
