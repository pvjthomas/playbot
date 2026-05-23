"""
Optional depth-augmented attack detection (stub / fusion layer).

When ``ENABLE_DEPTH_ATTACK_HINTS`` is True and depth frames are available,
MediaPipe labels may be refined using ``DepthAttackHints`` (e.g. boost
``center`` on a lunge toward the camera).

Default path remains RGB-only ``AttackVision`` in ``vision.py``.
"""

from __future__ import annotations

import config
from contracts import AttackDirection, Frame
from orbbec_depth import DepthAttackHints
from orbbec_frames import OrbbecFrameSet
from vision import AttackVision


class DepthAugmentedAttackVision(AttackVision):
    """
    Extends MediaPipe attack detection with Orbbec depth cues.

    Stub behavior today:
    - Keeps MediaPipe classification as the primary signal.
    - When depth hints fire, may upgrade ``none`` → ``center`` or ``high``.
    - Future: wrist-aligned depth ROIs, D2C alignment, IMU fusion.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_depth_hints: DepthAttackHints | None = None
        self._depth_baseline_mm: float | None = None

    @property
    def last_depth_hints(self) -> DepthAttackHints | None:
        return self._last_depth_hints

    def detect_attack(
        self,
        frame: Frame,
        *,
        frameset: OrbbecFrameSet | None = None,
    ) -> AttackDirection:
        direction = super().detect_attack(frame)
        if not config.ENABLE_DEPTH_ATTACK_HINTS or frameset is None:
            self._last_depth_hints = None
            return direction

        hints = DepthAttackHints.from_frames(
            frameset.depth_mm,
            baseline_mm=self._depth_baseline_mm,
        )
        self._last_depth_hints = hints

        if hints.median_torso_depth_mm is not None and self._depth_baseline_mm is None:
            self._depth_baseline_mm = hints.median_torso_depth_mm

        return self._fuse_depth(direction, hints)

    @staticmethod
    def _fuse_depth(direction: AttackDirection, hints: DepthAttackHints) -> AttackDirection:
        if direction != "none":
            return direction
        if hints.lunge_toward_camera:
            return "center"
        if hints.overhead_depth_spike:
            return "high"
        return direction
