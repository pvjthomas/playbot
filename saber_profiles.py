"""
Saber prop profiles — HSV / blade length tuned per toy.

Apply at runtime:
    python saber_preview.py --saber redtoy --camera laptop
"""

from __future__ import annotations

from typing import Any

import config

# Each profile sets config keys used by saber_detector.py
SABER_PROFILES: dict[str, dict[str, Any]] = {
    "default": {},
    "redtoy": {
        "SABER_USE_COLOR_TIP": True,
        # Red wraps in HSV — two ranges
        "SABER_COLOR_HSV_RANGES": [
            ((0, 70, 50), (12, 255, 255)),
            ((165, 70, 50), (180, 255, 255)),
        ],
        "SABER_BLADE_LENGTH_RATIO": 0.55,
        "SABER_COLOR_SEARCH_RADIUS_PX": 45,
        "SABER_MIN_COLOR_PIXELS": 25,
        "SABER_MIN_FOREARM_REACH": 0.08,
    },
}


def apply_saber_profile(name: str) -> str:
    """Copy profile values into config; returns normalized profile name."""
    key = name.strip().lower().replace("/", "_")
    if key not in SABER_PROFILES:
        known = ", ".join(sorted(SABER_PROFILES))
        raise ValueError(f"Unknown saber profile {name!r}. Known: {known}")
    for attr, value in SABER_PROFILES[key].items():
        setattr(config, attr, value)
    config.SABER_PROFILE = key
    return key


def list_profiles() -> list[str]:
    return sorted(SABER_PROFILES.keys())
