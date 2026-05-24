"""
Temporal swing estimation — begin / mid / end phases from landmark history.

See directions.py § Temporal swing estimation and task-vision.md Milestone 2.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque

import config
from contracts import AttackDirection, MotionKind, SwingPhase, SwingState

_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_WRIST = 15
_RIGHT_WRIST = 16


@dataclass(frozen=True)
class MotionSample:
    """One pose snapshot for swing tracking (normalized image coords)."""

    t: float
    grip_x: float
    grip_y: float
    lw_x: float
    lw_y: float
    rw_x: float
    rw_y: float
    extension: float
    center_x: float
    shoulder_y: float
    left_reach: float
    right_reach: float
    midline_band: float


def sample_from_landmarks(landmarks, t: float) -> MotionSample | None:
    """Build a motion sample from MediaPipe pose landmarks."""
    ls = landmarks[_LEFT_SHOULDER]
    rs = landmarks[_RIGHT_SHOULDER]
    lw = landmarks[_LEFT_WRIST]
    rw = landmarks[_RIGHT_WRIST]

    center_x = (ls.x + rs.x) / 2
    shoulder_y = min(ls.y, rs.y)
    left_reach = _dist(lw, ls)
    right_reach = _dist(rw, rs)
    extension = max(left_reach, right_reach)

    wrist_sep = _dist_pts(lw.x, lw.y, rw.x, rw.y)
    if wrist_sep <= config.SWING_WRIST_MERGE_DIST:
        grip_x = (lw.x + rw.x) / 2
        grip_y = (lw.y + rw.y) / 2
    elif right_reach >= left_reach:
        grip_x, grip_y = rw.x, rw.y
    else:
        grip_x, grip_y = lw.x, lw.y

    return MotionSample(
        t=t,
        grip_x=grip_x,
        grip_y=grip_y,
        lw_x=lw.x,
        lw_y=lw.y,
        rw_x=rw.x,
        rw_y=rw.y,
        extension=extension,
        center_x=center_x,
        shoulder_y=shoulder_y,
        left_reach=left_reach,
        right_reach=right_reach,
        midline_band=config.SIDE_MARGIN * 0.4,
    )


class SwingTracker:
    """Ring-buffer tracker: landmark history → SwingState."""

    def __init__(self):
        self._history: Deque[MotionSample] = deque()
        self._phase: SwingPhase = "idle"
        self._session_active = False
        self._session_peak_speed = 0.0
        self._session_peak_extension = 0.0
        self._session_start_t: float | None = None
        self._session_origin: MotionSample | None = None
        self._idle_frames = 0
        self._last_state = SwingState(direction="none", phase="idle", kind="none")

    @property
    def last_state(self) -> SwingState:
        return self._last_state

    def reset(self) -> None:
        self._history.clear()
        self._phase = "idle"
        self._session_active = False
        self._session_peak_speed = 0.0
        self._session_peak_extension = 0.0
        self._session_start_t = None
        self._session_origin = None
        self._idle_frames = 0
        self._last_state = SwingState(direction="none", phase="idle", kind="none")

    def update(self, sample: MotionSample | None) -> SwingState:
        if sample is None:
            self._idle_frames += 1
            if self._idle_frames >= config.SWING_IDLE_FRAMES:
                self._end_session()
            self._last_state = SwingState(
                direction="none", phase="idle", kind="none"
            )
            return self._last_state

        self._append(sample)
        grip_speed = self._smoothed_grip_speed()
        ext_speed = self._instant_extension_speed()
        motion_speed = max(grip_speed, ext_speed)
        self._update_session(sample, motion_speed)
        kind = self._classify_kind(sample, grip_speed, ext_speed)
        phase = self._classify_phase(sample, motion_speed, kind)
        direction = self._classify_direction(sample, kind, phase)
        self._phase = phase
        self._last_state = SwingState(direction=direction, phase=phase, kind=kind)
        return self._last_state

    def _append(self, sample: MotionSample) -> None:
        self._history.append(sample)
        cutoff = sample.t - config.SWING_HISTORY_SEC
        while self._history and self._history[0].t < cutoff:
            self._history.popleft()

    def _smoothed_grip_speed(self) -> float:
        if len(self._history) < 2:
            return 0.0
        speeds: list[float] = []
        prev = self._history[0]
        for cur in list(self._history)[1:]:
            dt = cur.t - prev.t
            if dt <= 1e-6:
                prev = cur
                continue
            dx = cur.grip_x - prev.grip_x
            dy = cur.grip_y - prev.grip_y
            speeds.append(math.hypot(dx, dy) / dt)
            prev = cur
        if not speeds:
            return 0.0
        speeds.sort()
        return speeds[len(speeds) // 2]

    def _instant_extension_speed(self) -> float:
        if len(self._history) < 2:
            return 0.0
        prev = self._history[-2]
        cur = self._history[-1]
        dt = cur.t - prev.t
        if dt <= 1e-6:
            return 0.0
        return max(0.0, (cur.extension - prev.extension) / dt)

    def _update_session(self, sample: MotionSample, motion_speed: float) -> None:
        if not self._session_active:
            if motion_speed >= config.SWING_BEGIN_VELOCITY:
                self._session_active = True
                self._session_start_t = sample.t
                self._session_origin = sample
                self._session_peak_speed = motion_speed
                self._session_peak_extension = sample.extension
                self._idle_frames = 0
                self._phase = "begin"
            else:
                self._idle_frames += 1
                if self._idle_frames >= config.SWING_IDLE_FRAMES:
                    self._end_session()
            return

        self._session_peak_speed = max(self._session_peak_speed, motion_speed)
        self._session_peak_extension = max(
            self._session_peak_extension, sample.extension
        )

        if motion_speed < config.SWING_IDLE_VELOCITY:
            self._idle_frames += 1
            if self._idle_frames >= config.SWING_IDLE_FRAMES:
                self._end_session()
        else:
            self._idle_frames = 0

    def _end_session(self) -> None:
        self._session_active = False
        self._session_start_t = None
        self._session_origin = None
        self._session_peak_speed = 0.0
        self._session_peak_extension = 0.0
        self._phase = "idle"
        self._idle_frames = 0

    def _classify_kind(
        self, sample: MotionSample, grip_speed: float, ext_speed: float
    ) -> MotionKind:
        if not self._session_active:
            return "none"

        origin = self._session_origin
        if origin is None:
            return "none"

        dx = sample.grip_x - origin.grip_x
        dy = sample.grip_y - origin.grip_y
        lateral = abs(dx)
        vertical = abs(dy)
        ext_gain = sample.extension - origin.extension

        both_midline = (
            abs(sample.lw_x - sample.center_x) < sample.midline_band * 1.5
            and abs(sample.rw_x - sample.center_x) < sample.midline_band * 1.5
            and sample.left_reach >= config.EXTENSION_MIN * 0.5
            and sample.right_reach >= config.EXTENSION_MIN * 0.5
        )
        vertical_travel = abs(sample.grip_y - origin.grip_y)
        thrust_like = (
            both_midline
            and ext_gain >= config.SWING_THRUST_EXT_MIN
            and lateral < config.SWING_THRUST_LATERAL_MAX
            and vertical_travel < config.SWING_THRUST_VERTICAL_MAX
            and ext_speed >= config.SWING_BEGIN_VELOCITY * 0.35
        )
        if thrust_like:
            return "thrust"

        motion = max(grip_speed, ext_speed)
        if motion < config.SWING_BEGIN_VELOCITY * 0.4:
            return "none"

        if lateral >= vertical * config.SWING_AXIS_DOMINANCE:
            return "linear"
        if vertical >= lateral * config.SWING_AXIS_DOMINANCE:
            return "linear"
        return "linear"

    def _classify_direction(
        self, sample: MotionSample, kind: MotionKind, phase: SwingPhase
    ) -> AttackDirection:
        if not self._session_active:
            return "none"

        origin = self._session_origin
        if origin is None:
            return "none"

        if kind == "thrust":
            if (
                sample.left_reach >= config.EXTENSION_MIN * 0.7
                and sample.right_reach >= config.EXTENSION_MIN * 0.7
            ):
                return "center"
            return "none"

        end_dir = _end_pose_direction(sample)
        if end_dir != "none" and phase in ("mid", "end"):
            return end_dir

        dx = sample.grip_x - origin.grip_x
        dy = sample.grip_y - origin.grip_y

        if abs(dx) >= abs(dy):
            if dx <= -config.SWING_DIRECTION_MIN:
                return "left"
            if dx >= config.SWING_DIRECTION_MIN:
                return "right"
        elif dy <= -config.SWING_DIRECTION_MIN:
            return "high"

        if phase == "end" and end_dir != "none":
            return end_dir
        return "none"

    def _classify_phase(
        self, sample: MotionSample, motion_speed: float, kind: MotionKind
    ) -> SwingPhase:
        if not self._session_active:
            return "idle"

        peak_speed = max(self._session_peak_speed, 1e-6)
        peak_ext = max(self._session_peak_extension, config.EXTENSION_MIN)
        speed_ratio = motion_speed / peak_speed
        ext_ratio = sample.extension / peak_ext

        session_age = 0.0
        if self._session_start_t is not None:
            session_age = sample.t - self._session_start_t

        end_pose = _end_pose_direction(sample)
        at_end_pose = end_pose != "none"

        # Active travel — primary block window (prefer mid over end pose while moving fast)
        if speed_ratio >= config.SWING_MID_SPEED_RATIO and kind != "none":
            return "mid"

        if at_end_pose and ext_ratio >= config.SWING_END_EXT_RATIO * 0.85:
            return "end"

        if (
            ext_ratio >= config.SWING_END_EXT_RATIO
            and speed_ratio <= config.SWING_END_SPEED_RATIO
            and session_age > config.SWING_BEGIN_MAX_SEC
        ):
            return "end"

        if session_age <= config.SWING_BEGIN_MAX_SEC and motion_speed >= config.SWING_BEGIN_VELOCITY * 0.5:
            return "begin"

        if (
            ext_ratio >= config.SWING_MID_EXT_RATIO
            and speed_ratio < config.SWING_MID_SPEED_RATIO
            and session_age > config.SWING_BEGIN_MAX_SEC
        ):
            return "end"

        return "begin" if motion_speed >= config.SWING_BEGIN_VELOCITY * 0.5 else "idle"


def _end_pose_direction(sample: MotionSample) -> AttackDirection:
    """Static END-pose heuristics (same rules as vision._classify)."""
    if sample.extension < config.EXTENSION_MIN:
        return "none"

    if (
        sample.lw_y < sample.shoulder_y - config.HIGH_MARGIN
        or sample.rw_y < sample.shoulder_y - config.HIGH_MARGIN
    ):
        return "high"

    if (
        sample.rw_x < sample.center_x - config.SIDE_MARGIN
        and sample.right_reach >= config.EXTENSION_MIN
    ):
        return "left"

    if (
        sample.lw_x > sample.center_x + config.SIDE_MARGIN
        and sample.left_reach >= config.EXTENSION_MIN
    ):
        return "right"

    if (
        abs(sample.lw_x - sample.center_x) < sample.midline_band
        and abs(sample.rw_x - sample.center_x) < sample.midline_band
        and sample.left_reach >= config.EXTENSION_MIN * 0.8
        and sample.right_reach >= config.EXTENSION_MIN * 0.8
    ):
        return "center"

    return "none"


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _dist_pts(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)
