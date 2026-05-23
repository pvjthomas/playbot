"""
Depth-based vision helpers for Orbbec RGB-D capture.

These utilities work on numpy depth maps — no hardware required in unit tests.
Future attack logic can fuse depth with MediaPipe (see ``orbbec_vision.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import config
from orbbec_frames import Frame


def depth_at(depth_mm: Frame, x: int, y: int) -> float | None:
    """Depth in millimeters at pixel (x, y), or None if invalid."""
    h, w = depth_mm.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        return None
    value = float(depth_mm[y, x])
    if not np.isfinite(value) or value <= 0:
        return None
    return value


def median_depth_in_roi(
    depth_mm: Frame,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> float | None:
    """Robust depth inside an axis-aligned ROI (pixel coords)."""
    h, w = depth_mm.shape[:2]
    xa, xb = sorted((max(0, x0), min(w, x1)))
    ya, yb = sorted((max(0, y0), min(h, y1)))
    if xb <= xa or yb <= ya:
        return None
    patch = depth_mm[ya:yb, xa:xb]
    valid = patch[np.isfinite(patch) & (patch > 0)]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def depth_delta_from_baseline(
    depth_mm: Frame,
    baseline_mm: float,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> float | None:
    """
    Positive delta means the ROI moved *closer* than ``baseline_mm``.

    Useful for detecting a lunge toward the camera (future ``center`` boost).
    """
    current = median_depth_in_roi(depth_mm, x0, y0, x1, y1)
    if current is None:
        return None
    return baseline_mm - current


@dataclass
class DepthAttackHints:
    """Stub fusion layer — depth cues that may refine MediaPipe attack labels."""

    lunge_toward_camera: bool = False
    overhead_depth_spike: bool = False
    median_torso_depth_mm: float | None = None

    @classmethod
    def from_frames(
        cls,
        depth_mm: Frame | None,
        *,
        torso_roi: tuple[int, int, int, int] | None = None,
        baseline_mm: float | None = None,
    ) -> DepthAttackHints:
        """
        Estimate coarse depth cues from a depth map.

        ``torso_roi`` is (x0, y0, x1, y1) in color/depth pixel space.
        """
        if depth_mm is None:
            return cls()

        roi = torso_roi or _default_torso_roi(depth_mm)
        median = median_depth_in_roi(depth_mm, *roi)
        hints = cls(median_torso_depth_mm=median)

        if median is None:
            return hints

        base = baseline_mm
        if base is None:
            base = median

        delta = depth_delta_from_baseline(depth_mm, base, *roi)
        if delta is not None and delta >= config.ORBBEC_LUNGE_DEPTH_DELTA_MM:
            hints.lunge_toward_camera = True

        # Stub: overhead strike might show a nearer band above the torso ROI.
        x0, y0, x1, y1 = roi
        head_roi = (x0, max(0, y0 - (y1 - y0)), x1, y0)
        head_median = median_depth_in_roi(depth_mm, *head_roi)
        if head_median is not None and median is not None:
            if median - head_median >= config.ORBBEC_OVERHEAD_DEPTH_DELTA_MM:
                hints.overhead_depth_spike = True

        return hints


def _default_torso_roi(depth_mm: Frame) -> tuple[int, int, int, int]:
    h, w = depth_mm.shape[:2]
    return (w // 4, h // 4, 3 * w // 4, 3 * h // 2)
