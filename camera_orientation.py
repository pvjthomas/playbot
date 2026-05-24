"""
Wrist / Orbbec camera orientation — rotation, flip, and canonical image frame.

Desk webcams mostly need horizontal mirror calibration (``camera_mirror.py``).
A **wrist-mounted** Dabai DC1 can arrive **sideways, upside-down, or mirrored**
depending on USB cable routing, bracket, and which way the lens faces along the
forearm. Attack labels in ``directions.py`` always use **image left/right**
after correction — this module maps raw frames into that frame.

Calibrate once at install (robot at a known pose):
    python camera_calibrate_orientation.py --camera piper

Storage: ``camera_orientation.json`` (merged with ``config.CAMERA_ORIENTATION_BY_SOURCE``).

Pose-dependent note (stub only)
-------------------------------
When the arm moves (e.g. high block), the sensor rotates with the wrist — image
"up" is not world up. Phase 1: **fixed** extrinsic calibration at a reference
pose (guard). Phase 2 (optional): IMU derotate via ``ORBBEC_ENABLE_IMU``.
Phase 3: keep detection **image-relative** (velocity axes) so moving FOV still
works without derotation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

import config
from camera_mirror import (
    active_camera_source_key,
    apply_mirror_correction,
    get_mirror_preview,
    image_direction_cheat_sheet,
    normalize_source_key,
)

_ORIENTATION_FILE = Path(__file__).resolve().parent / "camera_orientation.json"

RotationDeg = Literal[0, 90, 180, 270]
OrientationMode = Literal["fixed", "imu_derotate"]


class MountFacing(str, Enum):
    """How the lens points when the arm is in the calibration reference pose."""

    TOWARD_PARTNER = "toward_partner"  # sees sparring partner (typical fight cam)
    ALONG_BLADE = "along_blade"  # looks past grip toward tip
    AWAY_FROM_PARTNER = "away_from_partner"  # sees robot / room behind arm
    UNKNOWN = "unknown"


@dataclass
class OrientationCalibration:
    """Per camera source — static install calibration."""

    rotation_deg: RotationDeg = 0
    flip_h: bool = False
    flip_v: bool = False
    mount_facing: MountFacing = MountFacing.UNKNOWN
    mirror_preview: bool | None = None  # overrides camera_mirror.json when set
    reference_pose: str = "GUARD_CENTER"  # robot pose used during calibration
    mode: OrientationMode = "fixed"
    calibrated_at: str = ""
    note: str = ""


def load_orientation_map() -> dict[str, OrientationCalibration]:
    merged: dict[str, OrientationCalibration] = {}
    for key, entry in _load_json_file().items():
        merged[key] = _entry_to_cal(entry)
    cfg = getattr(config, "CAMERA_ORIENTATION_BY_SOURCE", None) or {}
    for key, val in cfg.items():
        merged[normalize_source_key(key)] = _entry_to_cal(val)
    return merged


def get_orientation(source: str | int | None = None) -> OrientationCalibration | None:
    key = normalize_source_key(source)
    return load_orientation_map().get(key)


def save_orientation(
    source: str | int,
    cal: OrientationCalibration,
) -> None:
    key = normalize_source_key(source)
    data = _load_json_file()
    data[key] = _cal_to_entry(cal)
    data[key]["calibrated_at"] = datetime.now(timezone.utc).isoformat()
    _ORIENTATION_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved camera_orientation.json[{key!r}] rotation={cal.rotation_deg}")


# --- Frame transforms (BGR and depth share the same geometry) ---


def apply_rotation(frame: np.ndarray, rotation_deg: RotationDeg) -> np.ndarray:
    if frame is None or rotation_deg == 0:
        return frame
    if rotation_deg == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation_deg == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation_deg == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def apply_flips(frame: np.ndarray, *, flip_h: bool, flip_v: bool) -> np.ndarray:
    if frame is None:
        return frame
    if flip_h and flip_v:
        return cv2.flip(frame, -1)
    if flip_h:
        return cv2.flip(frame, 1)
    if flip_v:
        return cv2.flip(frame, 0)
    return frame


def apply_orientation_transform(
    frame: np.ndarray,
    cal: OrientationCalibration,
) -> np.ndarray:
    """Rotate then flip — matches interactive calibrator key order."""
    if frame is None:
        return frame
    out = apply_rotation(frame, cal.rotation_deg)
    return apply_flips(out, flip_h=cal.flip_h, flip_v=cal.flip_v)


def transform_landmark_norm(
    x: float,
    y: float,
    cal: OrientationCalibration,
) -> tuple[float, float]:
    """
    Map MediaPipe normalized (x,y) through the same ops as ``apply_orientation_transform``.

    Call **after** pose runs on the raw frame if you correct frames before detection;
    call on raw landmarks if detection runs on uncorrected frames (not recommended).
    """
    nx, ny = float(x), float(y)
    r = cal.rotation_deg
    if r == 90:
        nx, ny = ny, 1.0 - nx
    elif r == 180:
        nx, ny = 1.0 - nx, 1.0 - ny
    elif r == 270:
        nx, ny = 1.0 - ny, nx
    if cal.flip_h:
        nx = 1.0 - nx
    if cal.flip_v:
        ny = 1.0 - ny
    return nx, ny


def apply_camera_frame_correction(
    frame: np.ndarray,
    source: str | int | None = None,
) -> np.ndarray:
    """
    Single entry for the vision loop: static orientation, then mirror correction.

    Controlled by ``CAMERA_APPLY_ORIENTATION_CORRECTION`` and
    ``CAMERA_APPLY_MIRROR_CORRECTION`` in ``config.py``.
    """
    if frame is None:
        return frame
    key = active_camera_source_key(source) if source is not None else active_camera_source_key()
    out = frame
    if getattr(config, "CAMERA_APPLY_ORIENTATION_CORRECTION", False):
        cal = get_orientation(key)
        if cal is not None:
            out = apply_orientation_transform(out, cal)
    out = apply_mirror_correction(out, key)
    return out


def effective_mirror_preview(source: str | int | None = None) -> bool | None:
    """Orientation file override, else camera_mirror.json."""
    key = normalize_source_key(source)
    cal = get_orientation(key)
    if cal is not None and cal.mirror_preview is not None:
        return cal.mirror_preview
    return get_mirror_preview(key)


def orientation_cheat_sheet(source: str | int | None = None) -> str:
    """Trainer overlay hint — mount + mirror."""
    key = normalize_source_key(source)
    cal = get_orientation(key)
    parts: list[str] = []
    if cal is not None:
        parts.append(
            f"Orient: rotate {cal.rotation_deg}°"
            + (" flipH" if cal.flip_h else "")
            + (" flipV" if cal.flip_v else "")
            + f" mount={cal.mount_facing.value}"
        )
    parts.append(image_direction_cheat_sheet(effective_mirror_preview(key)))
    return " | ".join(parts)


# --- Orbbec: keep depth aligned with color ---


def apply_orientation_to_depth(
    depth_mm: np.ndarray | None,
    cal: OrientationCalibration,
) -> np.ndarray | None:
    if depth_mm is None:
        return None
    out = depth_mm.astype(np.float32, copy=False)
    out = apply_rotation(out, cal.rotation_deg)
    return apply_flips(out, flip_h=cal.flip_h, flip_v=cal.flip_v)


def apply_camera_frameset_correction(frameset, source: str | int | None = None):
    """
    Apply orientation to ``OrbbecFrameSet`` color + depth (used by orbbec_camera).

    Returns a new ``OrbbecFrameSet`` when correction is enabled; otherwise input.
    """
    from orbbec_frames import OrbbecFrameSet

    if frameset is None:
        return None
    if not getattr(config, "CAMERA_APPLY_ORIENTATION_CORRECTION", False):
        key = active_camera_source_key(source)
        if not getattr(config, "CAMERA_APPLY_MIRROR_CORRECTION", False):
            return frameset
        color = apply_mirror_correction(frameset.color, key)
        return OrbbecFrameSet(
            color=color,
            depth_mm=frameset.depth_mm,
            ir=frameset.ir,
            timestamp_ms=frameset.timestamp_ms,
        )

    key = active_camera_source_key(source)
    cal = get_orientation(key)
    if cal is None:
        color = apply_mirror_correction(frameset.color, key)
        return OrbbecFrameSet(
            color=color,
            depth_mm=frameset.depth_mm,
            ir=frameset.ir,
            timestamp_ms=frameset.timestamp_ms,
        )

    color = apply_orientation_transform(frameset.color, cal) if frameset.color is not None else None
    color = apply_mirror_correction(color, key)
    depth = apply_orientation_to_depth(frameset.depth_mm, cal)
    ir = apply_orientation_transform(frameset.ir, cal) if frameset.ir is not None else None
    return OrbbecFrameSet(
        color=color,
        depth_mm=depth,
        ir=ir,
        timestamp_ms=frameset.timestamp_ms,
    )


# --- Auto-detect stubs (no hardware in unit tests) ---


def detect_up_from_landmarks(landmarks) -> RotationDeg | None:
    """
    Stub: infer 90° steps from shoulder line vs image vertical.

    Partner facing camera: shoulder line should be roughly horizontal (left shoulder
    left of right shoulder). If the line is vertical in the image, try rotate 90/270.
    Returns None if pose not visible.
    """
    if landmarks is None:
        return None
    lm = landmarks.landmark
    ls, rs = lm[11], lm[12]
    if ls.visibility < 0.5 or rs.visibility < 0.5:
        return None
    dx = abs(rs.x - ls.x)
    dy = abs(rs.y - ls.y)
    if dx < 0.05 and dy < 0.05:
        return None
    if dx >= dy * 1.2:
        return 0
    if dy >= dx * 1.2:
        # Shoulders stacked vertically — likely 90° off; cannot disambiguate 90 vs 270
        return 90
    return None


def derotate_frame_with_imu_stub(
    frame: np.ndarray,
    *,
    imu_sample: Any = None,
    reference_pose: str = "GUARD_CENTER",
) -> np.ndarray:
    """
    Phase 2 stub — when ``ORBBEC_ENABLE_IMU`` is wired, subtract wrist rotation
    relative to calibration quaternion so image axes stay stable during high blocks.
    """
    _ = imu_sample, reference_pose
    return frame


def suggest_calibration_steps(mount: MountFacing = MountFacing.UNKNOWN) -> list[str]:
    """Human checklist for ``camera_calibrate_orientation.py``."""
    steps = [
        "Move robot to reference pose (default GUARD_CENTER) and keep still.",
        "Partner stands in front of the arm; full upper body in frame if possible.",
        "In the preview, partner's head should be toward the TOP of the image.",
        "Partner's anatomical RIGHT should be on IMAGE-RIGHT (after mirror cal if needed).",
        "Use r/R to rotate, f/F horizontal flip, v/V vertical flip until that holds.",
        "Press y to save; verify with a slow image-left and image-right strike.",
    ]
    if mount == MountFacing.AWAY_FROM_PARTNER:
        steps.insert(
            2,
            "Lens faces away from partner (high block may point camera at ceiling/robot) — "
            "expect FOV to rotate with arm; use image-relative motion or enable IMU later.",
        )
    elif mount == MountFacing.TOWARD_PARTNER:
        steps.insert(2, "Lens should face the sparring partner in guard pose.")
    return steps


def _load_json_file() -> dict[str, Any]:
    if not _ORIENTATION_FILE.is_file():
        return {}
    try:
        return json.loads(_ORIENTATION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _entry_to_cal(entry: dict[str, Any] | OrientationCalibration) -> OrientationCalibration:
    if isinstance(entry, OrientationCalibration):
        return entry
    mount = entry.get("mount_facing", MountFacing.UNKNOWN.value)
    try:
        mount_enum = MountFacing(mount)
    except ValueError:
        mount_enum = MountFacing.UNKNOWN
    rot = int(entry.get("rotation_deg", 0))
    if rot not in (0, 90, 180, 270):
        rot = 0
    mp = entry.get("mirror_preview")
    return OrientationCalibration(
        rotation_deg=rot,  # type: ignore[arg-type]
        flip_h=bool(entry.get("flip_h", False)),
        flip_v=bool(entry.get("flip_v", False)),
        mount_facing=mount_enum,
        mirror_preview=mp if mp is None else bool(mp),
        reference_pose=str(entry.get("reference_pose", "GUARD_CENTER")),
        mode=str(entry.get("mode", "fixed")),  # type: ignore[arg-type]
        calibrated_at=str(entry.get("calibrated_at", "")),
        note=str(entry.get("note", "")),
    )


def _cal_to_entry(cal: OrientationCalibration) -> dict[str, Any]:
    return {
        "rotation_deg": cal.rotation_deg,
        "flip_h": cal.flip_h,
        "flip_v": cal.flip_v,
        "mount_facing": cal.mount_facing.value,
        "mirror_preview": cal.mirror_preview,
        "reference_pose": cal.reference_pose,
        "mode": cal.mode,
        "note": cal.note,
    }
