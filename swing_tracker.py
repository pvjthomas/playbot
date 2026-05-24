"""
Temporal swing estimation — begin / mid / end phases from landmark history.

See directions.py § Temporal swing estimation and task-vision.md Milestone 2.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace
from typing import Deque

import config
from contracts import AttackDirection, MotionKind, SwingPhase, SwingState
from directions import side_end_pose_from_x, strike_from_image_dx
from saber_detector import SaberLine

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
    uses_saber: bool = False
    track_x: float = 0.0
    track_y: float = 0.0
    tip_x: float = 0.0
    tip_y: float = 0.0


def _track_x(sample: MotionSample) -> float:
    return sample.track_x if sample.uses_saber else sample.grip_x


def _track_y(sample: MotionSample) -> float:
    return sample.track_y if sample.uses_saber else sample.grip_y


def _landmark_points(landmarks):
    """Accept MediaPipe PoseLandmarks or a plain landmark sequence."""
    if landmarks is None:
        return None
    if hasattr(landmarks, "landmark"):
        return landmarks.landmark
    return landmarks


def sample_from_landmarks(landmarks, t: float) -> MotionSample | None:
    """Build a motion sample from MediaPipe pose landmarks."""
    lm = _landmark_points(landmarks)
    if not lm:
        return None
    ls = lm[_LEFT_SHOULDER]
    rs = lm[_RIGHT_SHOULDER]
    lw = lm[_LEFT_WRIST]
    rw = lm[_RIGHT_WRIST]

    center_x = (ls.x + rs.x) / 2
    shoulder_y = min(ls.y, rs.y)
    left_reach = _dist(lw, ls)
    right_reach = _dist(rw, rs)
    extension = max(left_reach, right_reach)

    wrist_sep = _dist_pts(lw.x, lw.y, rw.x, rw.y)
    # Two-hand saber grip: always track midpoint of both wrists.
    grip_x = (lw.x + rw.x) / 2
    grip_y = (lw.y + rw.y) / 2
    _ = wrist_sep  # kept for future outlier detection

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
        track_x=grip_x,
        track_y=grip_y,
        tip_x=grip_x,
        tip_y=grip_y,
    )


def build_motion_sample(
    landmarks,
    t: float,
    saber: SaberLine | None,
    frame_w: int,
    frame_h: int,
    *,
    fuse_saber: bool = False,
) -> MotionSample | None:
    """Pose sample; optionally fuse YOLO saber tip for velocity and direction."""
    base = sample_from_landmarks(landmarks, t)
    if base is None or not fuse_saber or saber is None or frame_w <= 0 or frame_h <= 0:
        return base

    if not getattr(config, "SWING_FUSE_SABER", True):
        return base
    if saber.confidence < getattr(config, "SABER_SWING_FUSE_MIN_CONF", 0.25):
        return base
    if getattr(config, "SABER_FUSE_YOLO_ONLY", False) and getattr(
        saber, "source", "arm"
    ) == "arm":
        return base
    if getattr(config, "SABER_FUSE_REQUIRE_TIP_IN_FRAME", False) and not getattr(
        saber, "tip_in_frame", True
    ):
        return base

    gx = saber.grip_x / frame_w
    gy = saber.grip_y / frame_h
    tx = saber.tip_x / frame_w
    ty = saber.tip_y / frame_h
    blade_len = math.hypot(tx - gx, ty - gy)
    extension = max(base.extension, min(0.55, blade_len * 1.15))

    return MotionSample(
        t=t,
        grip_x=gx,
        grip_y=gy,
        lw_x=base.lw_x,
        lw_y=base.lw_y,
        rw_x=base.rw_x,
        rw_y=base.rw_y,
        extension=extension,
        center_x=base.center_x,
        shoulder_y=base.shoulder_y,
        left_reach=base.left_reach,
        right_reach=base.right_reach,
        midline_band=base.midline_band,
        uses_saber=True,
        track_x=tx,
        track_y=ty,
        tip_x=tx,
        tip_y=ty,
    )


def saber_track_point(
    grip_x: float,
    grip_y: float,
    tip_x: float,
    tip_y: float,
    forearm_norm: float,
    *,
    mode: str | None = None,
) -> tuple[float, float]:
    """
    Point on blade axis for velocity tracking.

    forearm_norm is latched once per swing session (not recomputed each frame).
    Modes:
      tip       — YOLO tip
      forearm   — grip + forearm_norm along blade (in from hands)
      inset_tip — tip - forearm_norm toward grip (default; tip may be off-screen)
    """
    mode = mode or getattr(config, "SWING_SABER_TRACK_POINT", "inset_tip")
    dx = tip_x - grip_x
    dy = tip_y - grip_y
    blade = math.hypot(dx, dy)
    if blade < 1e-6:
        return tip_x, tip_y
    ux, uy = dx / blade, dy / blade
    inset = max(0.0, min(forearm_norm, blade * 0.95))

    if mode == "tip":
        return tip_x, tip_y
    if mode == "forearm":
        return grip_x + ux * inset, grip_y + uy * inset
    if mode == "inset_tip":
        return tip_x - ux * inset, tip_y - uy * inset
    return tip_x, tip_y


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
        self._session_strike_direction: AttackDirection = "none"
        self._session_min_grip_y = 1.0
        self._session_overhead_latched = False
        self._idle_frames = 0
        self._latched_forearm_norm: float | None = None
        self._last_state = SwingState(
            direction="none", phase="idle", kind="none", speed=0.0, vx=0.0, vy=0.0
        )

    @property
    def last_state(self) -> SwingState:
        return self._last_state

    @property
    def latched_forearm_norm(self) -> float | None:
        return self._latched_forearm_norm

    def reset(self) -> None:
        self._history.clear()
        self._phase = "idle"
        self._session_active = False
        self._session_peak_speed = 0.0
        self._session_peak_extension = 0.0
        self._session_start_t = None
        self._session_origin = None
        self._session_strike_direction = "none"
        self._session_min_grip_y = 1.0
        self._session_overhead_latched = False
        self._idle_frames = 0
        self._latched_forearm_norm = None
        self._last_state = SwingState(
            direction="none", phase="idle", kind="none", speed=0.0, vx=0.0, vy=0.0
        )

    def _apply_saber_track_point(self, sample: MotionSample) -> MotionSample:
        """Latch forearm length once; place track point on blade axis (not raw tip)."""
        if not sample.uses_saber:
            return sample
        if self._latched_forearm_norm is None:
            self._latched_forearm_norm = (sample.left_reach + sample.right_reach) / 2.0
        tx, ty = saber_track_point(
            sample.grip_x,
            sample.grip_y,
            sample.tip_x,
            sample.tip_y,
            self._latched_forearm_norm,
        )
        if tx == sample.track_x and ty == sample.track_y:
            return sample
        return replace(sample, track_x=tx, track_y=ty)

    def update(self, sample: MotionSample | None) -> SwingState:
        if sample is None:
            self._idle_frames += 1
            if self._idle_frames >= config.SWING_IDLE_FRAMES:
                self._end_session()
            self._last_state = SwingState(
                direction="none", phase="idle", kind="none", speed=0.0, vx=0.0, vy=0.0
            )
            return self._last_state

        sample = self._apply_saber_track_point(sample)
        self._append(sample)
        vx, vy, grip_speed = self._instant_track_velocity()
        ext_speed = self._instant_extension_speed()
        motion_speed = max(grip_speed, ext_speed)
        self._update_session(sample, motion_speed)
        kind = self._classify_kind(sample, grip_speed, ext_speed)
        phase = self._classify_phase(sample, motion_speed, kind)
        direction = self._classify_direction(sample, kind, phase, vx, vy, grip_speed)
        self._phase = phase
        self._last_state = SwingState(
            direction=direction,
            phase=phase,
            kind=kind,
            speed=round(grip_speed, 4),
            vx=round(vx, 4),
            vy=round(vy, 4),
        )
        return self._last_state

    def _append(self, sample: MotionSample) -> None:
        self._history.append(sample)
        cutoff = sample.t - config.SWING_HISTORY_SEC
        while self._history and self._history[0].t < cutoff:
            self._history.popleft()

    def _instant_track_velocity(self) -> tuple[float, float, float]:
        if len(self._history) < 2:
            return 0.0, 0.0, 0.0
        prev = self._history[-2]
        cur = self._history[-1]
        dt = cur.t - prev.t
        if dt <= 1e-6:
            return 0.0, 0.0, 0.0
        vx = (_track_x(cur) - _track_x(prev)) / dt
        vy = (_track_y(cur) - _track_y(prev)) / dt
        return vx, vy, math.hypot(vx, vy)

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
            dx = _track_x(cur) - _track_x(prev)
            dy = _track_y(cur) - _track_y(prev)
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
                self._session_min_grip_y = _track_y(sample)
                self._session_overhead_latched = False
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
        self._session_min_grip_y = min(self._session_min_grip_y, _track_y(sample))
        self._update_overhead_latch(sample)

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
        self._session_strike_direction = "none"
        self._session_peak_speed = 0.0
        self._session_peak_extension = 0.0
        self._session_min_grip_y = 1.0
        self._session_overhead_latched = False
        self._phase = "idle"
        self._idle_frames = 0

    def _update_overhead_latch(self, sample: MotionSample) -> None:
        """Latch overhead arc: rise above shoulders or vertical raise-then-chop."""
        if self._session_overhead_latched:
            return
        origin = self._session_origin
        if origin is None:
            return

        if _hands_above_shoulders(sample):
            self._session_overhead_latched = True
            return

        rise = _track_y(origin) - self._session_min_grip_y
        dx = _track_x(sample) - _track_x(origin)
        dy = _track_y(sample) - _track_y(origin)
        lateral = abs(dx)
        vertical = abs(dy)
        vertical_dominant = vertical >= lateral * config.SWING_AXIS_DOMINANCE
        if vertical_dominant and rise >= config.SWING_OVERHEAD_RISE_MIN:
            self._session_overhead_latched = True

    def _classify_kind(
        self, sample: MotionSample, grip_speed: float, ext_speed: float
    ) -> MotionKind:
        if not self._session_active:
            return "none"

        origin = self._session_origin
        if origin is None:
            return "none"

        dx = _track_x(sample) - _track_x(origin)
        dy = _track_y(sample) - _track_y(origin)
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
        self,
        sample: MotionSample,
        kind: MotionKind,
        phase: SwingPhase,
        vx: float,
        vy: float,
        grip_speed: float,
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

        if self._session_overhead_latched and self._overhead_still_active(sample):
            return "high"

        motion_dir = direction_from_start_and_motion(
            origin, sample, vx, vy, grip_speed, kind
        )

        if phase in ("begin", "mid"):
            latch_ratio = (
                config.SWING_RIGHT_LATCH_SPEED_RATIO
                if motion_dir == "right"
                else 0.4
            )
            if (
                self._session_strike_direction == "none"
                and motion_dir != "none"
                and grip_speed >= config.SWING_BEGIN_VELOCITY * latch_ratio
            ):
                self._session_strike_direction = motion_dir
            if self._session_strike_direction != "none":
                return self._session_strike_direction
            return motion_dir

        if phase == "end":
            # Travel direction latched in begin/mid — robot must react before stop.
            if self._session_strike_direction != "none":
                return self._session_strike_direction
            return motion_dir

        return "none"

    def _overhead_still_active(self, sample: MotionSample) -> bool:
        """Overhead arc includes raise, peak, and downward chop before recovery."""
        if self._session_origin is None:
            return False
        peak = self._session_min_grip_y
        chop_depth = _track_y(sample) - peak
        if chop_depth > config.SWING_OVERHEAD_CHOP_MAX:
            return False
        if _hands_above_shoulders(sample):
            return True
        if peak < sample.shoulder_y - config.HIGH_MARGIN * 0.5:
            return True
        origin = self._session_origin
        rise = _track_y(origin) - peak
        return rise >= config.SWING_OVERHEAD_RISE_MIN

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

        if session_age <= config.SWING_BEGIN_MIN_SEC:
            return "begin"

        end_pose = _end_pose_direction(sample)
        at_end_pose = end_pose != "none"

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


def direction_from_velocity(
    vx: float, vy: float, speed: float, kind: MotionKind = "linear"
) -> AttackDirection:
    speed_min = _velocity_speed_min(vx)
    if speed < speed_min:
        return "none"
    if kind == "thrust" and speed >= speed_min:
        if abs(vx) < config.SWING_THRUST_LATERAL_MAX * 2:
            return "center"
    return _direction_from_delta(
        vx, vy, min_mag=config.SWING_DIRECTION_MIN * 0.5, vx_hint=vx
    )


def _velocity_speed_min(vx: float) -> float:
    """Lower speed bar for off-hand body-right travel (−vx)."""
    if vx <= -config.SWING_DIRECTION_MIN * 0.25:
        return config.SWING_RIGHT_VELOCITY_DIR_MIN
    return config.SWING_VELOCITY_DIR_MIN


def _lateral_dominance_for_dx(dx: float) -> float:
    """How easily lateral beats vertical — relaxed on off-hand / withdraw arcs."""
    if dx < 0:
        return config.SWING_RIGHT_LATERAL_DOMINANCE
    if dx > 0:
        return config.SWING_LEFT_LATERAL_DOMINANCE
    return 1.0


def _direction_min_for_dx(dx: float, base: float) -> float:
    if dx < 0:
        return config.SWING_RIGHT_DIRECTION_MIN
    return base


def strike_from_start_side(origin: MotionSample, sample: MotionSample) -> AttackDirection:
    """
    Wind-up side at session start → likely cross-body strike.

    Started on YOUR RIGHT (true cam: low image-x) → ``left`` strike.
    Started on YOUR LEFT (high image-x) → ``right`` strike.
    """
    ox = _track_x(origin)
    margin = config.SWING_DIRECTION_MIN
    if ox < sample.center_x - margin:
        return "left"
    if ox > sample.center_x + margin:
        return "right"
    return "none"


def direction_from_start_and_motion(
    origin: MotionSample,
    sample: MotionSample,
    vx: float,
    vy: float,
    grip_speed: float,
    kind: MotionKind,
) -> AttackDirection:
    """
    Attack direction from wind-up location + active travel (not stop pose).

    Used in ``begin``/``mid`` to latch direction for robot block; ``end`` keeps
    the latched travel direction because the robot must have reacted already.
    """
    if kind == "thrust":
        if (
            sample.left_reach >= config.EXTENSION_MIN * 0.7
            and sample.right_reach >= config.EXTENSION_MIN * 0.7
        ):
            return "center"
        return "none"

    vel_dir = direction_from_velocity(vx, vy, grip_speed, kind)
    disp_dir = _direction_from_displacement(sample, origin)
    start_dir = strike_from_start_side(origin, sample)
    vel_min = _velocity_speed_min(vx)

    if vel_dir != "none" and grip_speed >= vel_min:
        return vel_dir
    if vel_dir != "none" and start_dir != "none" and vel_dir == start_dir:
        return vel_dir
    if disp_dir != "none" and start_dir != "none" and disp_dir == start_dir:
        return disp_dir
    if disp_dir == "right" and grip_speed >= config.SWING_BEGIN_VELOCITY * 0.35:
        return disp_dir
    if disp_dir != "none" and grip_speed >= config.SWING_BEGIN_VELOCITY * 0.5:
        return disp_dir
    latch_ratio = (
        config.SWING_RIGHT_LATCH_SPEED_RATIO
        if start_dir == "right"
        else 0.4
    )
    if start_dir != "none" and grip_speed >= config.SWING_BEGIN_VELOCITY * latch_ratio:
        return start_dir
    if vel_dir != "none":
        return vel_dir
    return disp_dir


def _direction_from_displacement(
    sample: MotionSample, origin: MotionSample
) -> AttackDirection:
    dx = _track_x(sample) - _track_x(origin)
    dy = _track_y(sample) - _track_y(origin)
    return _direction_from_delta(
        dx, dy, min_mag=config.SWING_DIRECTION_MIN, vx_hint=dx
    )


def _direction_from_delta(
    dx: float, dy: float, *, min_mag: float, vx_hint: float | None = None
) -> AttackDirection:
    hint = dx if vx_hint is None else vx_hint
    dom = _lateral_dominance_for_dx(hint)
    min_lat = _direction_min_for_dx(hint, min_mag)
    if abs(dx) >= abs(dy) * dom:
        side = strike_from_image_dx(dx, min_lat)
        if side != "none":
            return side
    elif dy <= -min_mag:
        return "high"
    return "none"


def _wrists_above_shoulders(sample: MotionSample) -> bool:
    cutoff = sample.shoulder_y - config.HIGH_MARGIN
    return sample.lw_y < cutoff or sample.rw_y < cutoff


def _hands_above_shoulders(sample: MotionSample) -> bool:
    if sample.uses_saber and sample.tip_y < sample.shoulder_y - config.HIGH_MARGIN:
        return True
    return _wrists_above_shoulders(sample)


def centerline_band(sample: MotionSample) -> float:
    return max(sample.midline_band, config.CENTERLINE_MARGIN)


def at_centerline_pose(sample: MotionSample) -> bool:
    """Hands/saber stopped at midline (robot block or withdraw start)."""
    if sample.extension < config.EXTENSION_MIN * 0.75:
        return False
    band = centerline_band(sample)
    lead_near = (
        abs(sample.rw_x - sample.center_x) < band
        or abs(sample.lw_x - sample.center_x) < band
    )
    both_near = (
        abs(sample.lw_x - sample.center_x) < band * 1.2
        and abs(sample.rw_x - sample.center_x) < band * 1.2
    )
    tip_near = (
        sample.uses_saber and abs(sample.tip_x - sample.center_x) < band * 1.2
    )
    return lead_near or both_near or tip_near


def side_strike_blocked_at_center(
    sample: MotionSample, direction: AttackDirection
) -> bool:
    """Cross-body strike stopped at centerline (robot block), not full extension."""
    if direction not in ("left", "right"):
        return False
    band = centerline_band(sample)
    if direction == "left":
        return (
            sample.right_reach >= config.EXTENSION_MIN * 0.8
            and abs(sample.rw_x - sample.center_x) < band
            and sample.right_reach >= sample.left_reach
        )
    return (
        sample.left_reach >= config.EXTENSION_MIN * 0.8
        and abs(sample.lw_x - sample.center_x) < band
        and sample.left_reach >= sample.right_reach
    )


def withdraw_direction_after_strike(strike_direction: str) -> str:
    """Recovery direction after a centerline block (mirror cross-body)."""
    return {"left": "right", "right": "left"}.get(strike_direction, "none")


def _end_pose_direction(sample: MotionSample) -> AttackDirection:
    """Static END-pose heuristics (same rules as vision._classify)."""
    if sample.extension < config.EXTENSION_MIN:
        return "none"

    if _wrists_above_shoulders(sample):
        return "high"

    if side_strike_blocked_at_center(sample, "left"):
        return "left"
    if side_strike_blocked_at_center(sample, "right"):
        return "right"

    if sample.uses_saber:
        saber_dir = saber_tip_direction(sample)
        if saber_dir != "none":
            return saber_dir

    if (
        sample.rw_x > sample.center_x + config.SIDE_MARGIN
        and sample.right_reach >= config.EXTENSION_MIN
    ):
        return "left"

    if (
        sample.lw_x < sample.center_x - config.SIDE_MARGIN
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


def saber_tip_direction(sample: MotionSample) -> AttackDirection:
    """Direction from fused saber tip position (body-named side at END)."""
    if sample.tip_y < sample.shoulder_y - config.HIGH_MARGIN:
        return "high"
    side = side_end_pose_from_x(
        sample.tip_x,
        sample.center_x,
        config.SIDE_MARGIN,
        extended=True,
    )
    if side != "none":
        return side
    if (
        abs(sample.tip_x - sample.center_x) < sample.midline_band
        and sample.left_reach >= config.EXTENSION_MIN * 0.7
        and sample.right_reach >= config.EXTENSION_MIN * 0.7
    ):
        return "center"
    return "none"


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _dist_pts(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x1 - x2, y1 - y2)
