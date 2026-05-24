"""
Per-camera horizontal mirror (selfie flip) detection and optional correction.

Some webcams show a mirror-like preview (raise your RIGHT hand → it appears on the
RIGHT side of the screen). Others show a true camera view (right hand on the LEFT of
the screen). Attack/training directions use **image left/right** — this module records
which case each camera uses so prompts stay unambiguous.

Calibrate:
    python camera_calibrate_mirror.py --camera laptop

Storage: ``camera_mirror.json`` next to this file (merged with ``config.CAMERA_MIRROR_BY_SOURCE``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

import config

_MIRROR_FILE = Path(__file__).resolve().parent / "camera_mirror.json"

_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_WRIST = 15
_RIGHT_WRIST = 16


@dataclass
class MirrorCalibration:
    """Per camera source."""

    mirror_preview: bool
    """True = selfie/mirror (right hand appears on right side of screen)."""
    calibrated_at: str = ""
    note: str = ""


def active_camera_source_key(resolved_source: str | int | None = None) -> str:
    """
    Mirror/calibration key for the camera in use.

    Prefer logical ``CAMERA_SOURCE`` (e.g. ``laptop`` from ``--camera laptop``) over the
    resolved OpenCV index (``0`` → ``index_0``) so calibration and runtime match.
    """
    logical = getattr(config, "CAMERA_SOURCE", None)
    if logical is not None and logical != "auto":
        if isinstance(logical, int):
            return normalize_source_key(logical)
        text = str(logical).strip()
        lower = text.lower()
        if not text.isdigit() and not lower.startswith("/dev/") and not lower.startswith("avfoundation:"):
            return normalize_source_key(logical)
    if resolved_source is not None:
        return normalize_source_key(resolved_source)
    return normalize_source_key(logical)


def normalize_source_key(source: str | int | None = None) -> str:
    """Stable key for laptop / piper / index / dev path."""
    if source is None:
        source = getattr(config, "CAMERA_SOURCE", "laptop")
    if isinstance(source, int):
        return f"index_{source}"
    s = str(source).strip()
    lower = s.lower()
    if lower in ("laptop", "webcam", "macbook"):
        return "laptop"
    if lower in ("piper", "dabai", "orbbec"):
        return "piper"
    if lower.isdigit():
        return f"index_{lower}"
    if s.startswith("/dev/video"):
        return s.replace("/", "_")
    if s.startswith("avfoundation:"):
        name = s.split(":", 1)[-1].strip().lower().replace(" ", "_")
        return f"avfoundation_{name}"
    return lower.replace("/", "_").replace(" ", "_")


def load_mirror_map() -> dict[str, MirrorCalibration]:
    merged: dict[str, MirrorCalibration] = {}
    file_map = _load_json_file()
    for key, entry in file_map.items():
        merged[key] = _entry_to_cal(entry)
    cfg = getattr(config, "CAMERA_MIRROR_BY_SOURCE", None) or {}
    for key, val in cfg.items():
        if isinstance(val, bool):
            merged[normalize_source_key(key)] = MirrorCalibration(mirror_preview=val)
        elif isinstance(val, dict) and "mirror_preview" in val:
            merged[normalize_source_key(key)] = _entry_to_cal(val)
    return merged


def get_mirror_preview(source: str | int | None = None) -> bool | None:
    """Return mirror state for source, or None if unknown."""
    key = normalize_source_key(source)
    cal = load_mirror_map().get(key)
    return cal.mirror_preview if cal else None


def save_mirror_preview(
    source: str | int,
    mirror_preview: bool,
    *,
    note: str = "",
) -> None:
    key = normalize_source_key(source)
    data = _load_json_file()
    data[key] = {
        "mirror_preview": mirror_preview,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    _MIRROR_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved camera_mirror.json[{key!r}] mirror_preview={mirror_preview}")


def detect_mirror_from_landmarks(landmarks) -> bool | None:
    """
    User holds anatomical RIGHT hand up (left hand down).

    Returns True if mirror/selfie preview (right wrist on right half of image),
    False if true camera view (right wrist on left half), None if unclear.
    """
    if landmarks is None:
        return None
    lm = landmarks.landmark
    ls, rs = lm[_LEFT_SHOULDER], lm[_RIGHT_SHOULDER]
    lw, rw = lm[_LEFT_WRIST], lm[_RIGHT_WRIST]

    if ls.visibility < 0.5 or rs.visibility < 0.5:
        return None
    if lw.visibility < 0.4 or rw.visibility < 0.4:
        return None

    # Right hand must be clearly raised vs left
    if not (rw.y < lw.y - 0.06):
        return None
    # Left should be lower / not extended equally
    if lw.y < rs.y - 0.02:
        return None

    center_x = (ls.x + rs.x) / 2
    margin = 0.04
    if rw.x > center_x + margin:
        return True  # mirror/selfie — right hand on right side of screen
    if rw.x < center_x - margin:
        return False  # true camera — right hand on left side of screen
    return None


def detect_mirror_from_frames(frames_landmarks: list) -> tuple[bool | None, float]:
    """Majority vote over several detections. Returns (result, confidence 0-1)."""
    votes: list[bool] = []
    for lm in frames_landmarks:
        r = detect_mirror_from_landmarks(lm)
        if r is not None:
            votes.append(r)
    if not votes:
        return None, 0.0
    true_count = sum(1 for v in votes if v)
    false_count = len(votes) - true_count
    confidence = max(true_count, false_count) / len(votes)
    return true_count >= false_count, confidence


def apply_mirror_correction(frame: np.ndarray, source: str | int | None = None) -> np.ndarray:
    """
    Optionally flip frame so vision always sees a canonical (non-mirror) image.

    Only when ``CAMERA_APPLY_MIRROR_CORRECTION`` is True and this source is calibrated
    as mirror_preview.
    """
    if frame is None:
        return frame
    if not getattr(config, "CAMERA_APPLY_MIRROR_CORRECTION", False):
        return frame
    preview = get_mirror_preview(source)
    if preview is True:
        return cv2.flip(frame, 1)
    return frame


def image_direction_cheat_sheet(mirror_preview: bool | None) -> str:
    """One-line hint for trainers/overlays."""
    if mirror_preview is True:
        return (
            "Mirror cam: IMAGE-LEFT = left side of screen. "
            "Your RIGHT hand shows on the RIGHT side of the screen."
        )
    if mirror_preview is False:
        return (
            "True cam: IMAGE-LEFT = left side of screen. "
            "Your RIGHT hand shows on the LEFT side of the screen."
        )
    return "IMAGE-LEFT = left edge of picture (run camera_calibrate_mirror.py if unsure)"


def _load_json_file() -> dict[str, Any]:
    if not _MIRROR_FILE.is_file():
        return {}
    try:
        return json.loads(_MIRROR_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _entry_to_cal(entry: dict[str, Any] | bool) -> MirrorCalibration:
    if isinstance(entry, bool):
        return MirrorCalibration(mirror_preview=entry)
    return MirrorCalibration(
        mirror_preview=bool(entry["mirror_preview"]),
        calibrated_at=str(entry.get("calibrated_at", "")),
        note=str(entry.get("note", "")),
    )
