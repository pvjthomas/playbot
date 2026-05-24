#!/usr/bin/env python3
"""
Guided swing exercise session — log temporal detection vs ground truth.

Discrete mode (default): 5s GET READY → auto 3s RECORDING → SPACE for next trial.
Each strike direction is prompted 2–3 separate times for clean idle boundaries.
REC windows are saved as overlay videos under swing_eval_logs/videos/ (use --no-video to disable).

Run:
  python collect_swing_eval.py --camera laptop
  python collect_swing_eval.py --camera laptop --quick
  python collect_swing_eval.py --camera laptop --saber redtoy --detector yolo --yolo-every 3
  python collect_swing_eval.py --camera laptop --centerline --saber redtoy --detector yolo

Keys during session:
  SPACE — start session / advance after each 3s recording (DONE)
  s     — skip current trial
  b     — back one trial
  q     — quit and save log so far

Analyze a saved log:
  python analyze_swing_eval.py path/to/session.json
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2

import config
from analyze_swing_eval import analyze_log_file
from camera import add_camera_cli, configure_camera_from_args, open_camera
from directions import print_body_direction_legend, print_centerline_eval_legend
from overlays import AttackOverlay
from saber_detector import SaberDetector, SaberLine, draw_saber_overlay
from saber_axis_flags import apply_axis_preset, axis_flags_snapshot, list_axis_presets
from saber_profiles import apply_saber_profile, list_profiles
from swing_eval_plan import SwingExercise, session_for, session_summary
from swing_tracker import (
    at_centerline_pose,
    direction_from_velocity,
    sample_from_landmarks,
    side_strike_blocked_at_center,
)
from vision import AttackVision

LOG_DIR = Path(__file__).resolve().parent / "swing_eval_logs"


@dataclass
class SaberEvalHelper:
    """Optional red-saber YOLO / color overlay for eval sessions."""

    mode: str  # "none", "yolo", "arm", "color"
    profile: str = ""
    yolo_loaded: bool = False
    _legacy: SaberDetector | None = None
    _color: object | None = None

    def detect(self, frame, landmarks) -> SaberLine | None:
        if self._color is not None:
            return self._color.detect_saber(frame, landmarks)
        if self._legacy is not None:
            return self._legacy.detect_saber(frame, landmarks)
        return None

    def close(self) -> None:
        if self._legacy is not None:
            self._legacy.close()
        if self._color is not None:
            self._color.close()


def _make_saber_helper(
    saber: str | None, detector: str, *, yolo_every: int = 3
) -> SaberEvalHelper:
    if not saber:
        return SaberEvalHelper(mode="none")

    profile = apply_saber_profile(saber)
    if detector == "color":
        from color_saber_detector import ColorSaberDetector, calibration_path

        if not calibration_path(profile).is_file():
            raise SystemExit(
                f"Missing color calibration for {profile!r}. Run:\n"
                f"  python calibrate_saber_color.py --saber {profile}"
            )
        return SaberEvalHelper(
            mode="color",
            profile=profile,
            _color=ColorSaberDetector(profile),
        )

    config.SABER_YOLO_EVERY_N_FRAMES = max(1, yolo_every)
    legacy = SaberDetector()
    yolo_loaded = legacy._yolo is not None
    if detector == "yolo" and not yolo_loaded:
        model = getattr(config, "SABER_MODEL", "")
        raise SystemExit(
            f"YOLO weights not loaded (SABER_MODEL={model!r}). "
            "Train or fix path — see SABER-TRAINING.md"
        )
    config.SABER_FUSE_YOLO_ONLY = detector == "yolo" and yolo_loaded
    mode = "yolo" if yolo_loaded else "arm"
    return SaberEvalHelper(
        mode=mode,
        profile=profile,
        yolo_loaded=yolo_loaded,
        _legacy=legacy,
    )


@dataclass
class FrameRecord:
    t_rel: float
    attack: str
    swing_direction: str
    swing_phase: str
    swing_kind: str
    tracked: bool
    saber_detected: bool = False
    saber_orientation: str = ""
    saber_confidence: float = 0.0
    saber_source: str = ""
    saber_axis_method: str = ""
    saber_tip_in_frame: bool = True
    swing_uses_saber: bool = False
    grip_speed: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    velocity_direction: str = "none"
    at_centerline: bool = False
    blocked_at_centerline: bool = False


class TrialVideoRecorder:
    """Write preview frames during the REC window to an mp4."""

    def __init__(self, path: Path, fps: float):
        self.path = path
        self.fps = max(1.0, fps)
        self._writer: cv2.VideoWriter | None = None

    def write(self, frame) -> None:
        if frame is None:
            return
        if self._writer is None:
            h, w = frame.shape[:2]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(str(self.path), fourcc, self.fps, (w, h))
        self._writer.write(frame)

    def close(self) -> Path | None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        if self.path.is_file() and self.path.stat().st_size > 0:
            return self.path
        if self.path.is_file():
            self.path.unlink(missing_ok=True)
        return None

    def discard(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        self.path.unlink(missing_ok=True)


def _trial_video_path(video_dir: Path, trial_index: int, exercise: SwingExercise) -> Path:
    safe_id = exercise.id.replace("/", "_")
    return video_dir / f"trial_{trial_index + 1:03d}_{safe_id}.mp4"


def _swing_config_snapshot() -> dict[str, float | int | str]:
    keys = [
        "SWING_HISTORY_SEC",
        "SWING_BEGIN_VELOCITY",
        "SWING_IDLE_VELOCITY",
        "SWING_IDLE_FRAMES",
        "SWING_MID_SPEED_RATIO",
        "SWING_END_EXT_RATIO",
        "HIGH_MARGIN",
        "SIDE_MARGIN",
        "EXTENSION_MIN",
        "SABER_MODEL",
        "SABER_PROFILE",
        "SABER_YOLO_EVERY_N_FRAMES",
        "SABER_YOLO_CONFIDENCE",
        "SABER_YOLO_CACHE_BLEND",
        "SABER_FUSE_YOLO_ONLY",
        "SWING_FUSE_SABER",
        "SABER_SWING_FUSE_MIN_CONF",
        "SWING_BEGIN_MIN_SEC",
        "SWING_VELOCITY_DIR_MIN",
        "SWING_RIGHT_VELOCITY_DIR_MIN",
        "SWING_RIGHT_DIRECTION_MIN",
        "SWING_RIGHT_LATERAL_DOMINANCE",
        "SWING_LEFT_LATERAL_DOMINANCE",
        "SWING_RIGHT_LATCH_SPEED_RATIO",
        "SWING_STRONG_SPEED_RATIO",
        "SWING_SABER_TRACK_POINT",
    ]
    return {k: getattr(config, k) for k in keys if hasattr(config, k)}


def _eval_frame(
    vision: AttackVision,
    frame,
    saber: SaberEvalHelper | None = None,
) -> tuple[str, object, SaberLine | None]:
    fuse = bool(
        saber is not None
        and saber.yolo_loaded
        and getattr(config, "SWING_FUSE_SABER", True)
    )
    if fuse and saber is not None:
        attack, swing = vision.process_frame(
            frame,
            fuse_saber=True,
            saber_detect_fn=saber.detect,
        )
        return attack, swing, vision.last_saber_line

    attack, swing = vision.process_frame(frame)
    saber_line = saber.detect(frame, vision.last_landmarks) if saber else None
    return attack, swing, saber_line


def _render_preview(
    overlay: AttackOverlay,
    frame,
    vision: AttackVision,
    *,
    attack: str,
    swing_line: str,
    saber_line: SaberLine | None = None,
) -> object:
    preview = overlay.render(
        frame,
        attack,
        pose=vision.last_landmarks,
        swing=vision.last_swing,
    )
    if saber_line is not None:
        preview = draw_saber_overlay(preview, saber_line)
        cv2.putText(
            preview,
            f"saber: {saber_line.orientation} conf={saber_line.confidence:.2f}",
            (12, preview.shape[0] - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 200, 255),
            1,
        )
    return preview


def _draw_eval_hud(
    frame,
    *,
    exercise: SwingExercise | None,
    exercise_index: int,
    exercise_total: int,
    phase_label: str,
    countdown: float | None,
    attack: str,
    swing_line: str,
    match_ok: bool | None,
    hud_prompt: str | None = None,
    recording_total_sec: float | None = None,
) -> None:
    h, w = frame.shape[:2]

    if exercise is None:
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        cv2.putText(
            frame,
            "SPACE=start session   q=quit",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 200),
            2,
        )
        return

    if phase_label == "DONE":
        keys_line = (
            f"Trial {exercise_index + 1}/{exercise_total}  [{phase_label}]  "
            "SPACE=next  s=skip  b=back  q=quit"
        )
    else:
        keys_line = (
            f"Trial {exercise_index + 1}/{exercise_total}  [{phase_label}]  "
            "s=skip  b=back  q=quit"
        )

    title_scale, title_th = 0.65, 2
    title_y = 50
    (_, title_h), _ = cv2.getTextSize(
        exercise.title, cv2.FONT_HERSHEY_SIMPLEX, title_scale, title_th
    )

    swing_y = 108
    prompt_y = 128
    hud_h = 150
    rec_draw: tuple[str, int, tuple[int, int, int], float, int] | None = None
    countdown_draw: tuple[str, int, tuple[int, int, int], float, int] | None = None
    action_draw: str | None = None
    rec_bar: tuple[int, int, float] | None = None

    if countdown is not None:
        if phase_label in ("GET READY",):
            label = "Get ready in"
            timer_color = (0, 200, 255)
            timer_scale = 0.7
            timer_th = 2
        elif phase_label in ("SWING NOW", "HOLD STILL", "RECORDING"):
            label = "REC"
            timer_color = (0, 0, 255)
            timer_scale = 1.05
            timer_th = 3
        else:
            label = "Starting in"
            timer_color = (0, 200, 255)
            timer_scale = 0.7
            timer_th = 2
        secs = max(0.0, countdown)
        if phase_label in ("SWING NOW", "HOLD STILL", "RECORDING"):
            rec_text = f"{label}  {secs:.1f}s left"
            (_, rec_h), _ = cv2.getTextSize(
                rec_text, cv2.FONT_HERSHEY_SIMPLEX, timer_scale, timer_th
            )
            rec_y = title_y + title_h + 8 + rec_h
            rec_draw = (rec_text, rec_y, timer_color, timer_scale, timer_th)
            if recording_total_sec and recording_total_sec > 0:
                elapsed = recording_total_sec - secs
                frac = max(0.0, min(1.0, elapsed / recording_total_sec))
                bar_top = rec_y + 10
                bar_bottom = bar_top + 6
                rec_bar = (bar_top, bar_bottom, frac)
                swing_y = bar_bottom + 18
            else:
                swing_y = rec_y + rec_h + 18
            prompt_y = swing_y + 28
            hud_h = max(178, prompt_y + 24)
        else:
            countdown_draw = (
                f"{label} {secs:.1f}s...",
                78,
                timer_color,
                timer_scale,
                timer_th,
            )
    else:
        hint = exercise.body_hint or exercise.expected_direction
        action = f"Do: {hint}"
        if phase_label == "DONE":
            action = "SPACE for next trial"
        elif phase_label == "GET READY":
            action = "Then recording starts automatically"
        action_draw = action

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, hud_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    cv2.putText(
        frame,
        keys_line,
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (0, 255, 200),
        2,
    )
    cv2.putText(
        frame,
        exercise.title,
        (12, title_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        title_scale,
        (255, 255, 255),
        title_th,
    )

    if rec_draw is not None:
        rec_text, rec_y, timer_color, timer_scale, timer_th = rec_draw
        cv2.putText(
            frame,
            rec_text,
            (12, rec_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            timer_scale,
            timer_color,
            timer_th,
        )
        if rec_bar is not None:
            bar_top, bar_bottom, frac = rec_bar
            bar_w = w - 24
            cv2.rectangle(frame, (12, bar_top), (12 + bar_w, bar_bottom), (60, 60, 60), -1)
            cv2.rectangle(
                frame,
                (12, bar_top),
                (12 + int(bar_w * frac), bar_bottom),
                timer_color,
                -1,
            )
    elif countdown_draw is not None:
        text, y_pos, timer_color, timer_scale, timer_th = countdown_draw
        cv2.putText(
            frame,
            text,
            (12, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            timer_scale,
            timer_color,
            timer_th,
        )
    elif action_draw is not None:
        cv2.putText(
            frame,
            action_draw,
            (12, 78),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (200, 220, 255),
            1,
        )

    det_color = (160, 160, 160)
    if match_ok is True:
        det_color = (80, 220, 80)
    elif match_ok is False:
        det_color = (80, 80, 255)

    if swing_line:
        cv2.putText(
            frame,
            f"attack: {attack}   {swing_line}",
            (12, swing_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            det_color,
            2,
        )

    prompt_text = hud_prompt if hud_prompt is not None else exercise.prompt
    words = prompt_text.split()
    line = ""
    y = prompt_y
    for word in words:
        test = f"{line} {word}".strip()
        if len(test) > 72:
            cv2.putText(
                frame,
                line,
                (12, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (180, 180, 180),
                1,
            )
            y += 16
            line = word
        else:
            line = test
    if line and y <= hud_h - 4:
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (180, 180, 180),
            1,
        )


def _pose_flags(vision: AttackVision, swing_direction: str) -> tuple[bool, bool]:
    if vision.last_landmarks is None:
        return False, False
    sample = sample_from_landmarks(vision.last_landmarks, 0.0)
    if sample is None:
        return False, False
    at_cl = at_centerline_pose(sample)
    blocked = (
        swing_direction in ("left", "right")
        and side_strike_blocked_at_center(sample, swing_direction)
    )
    return at_cl, blocked


def _match_expected(
    exercise: SwingExercise,
    attack: str,
    swing_dir: str,
    swing_phase: str,
    *,
    velocity_dir: str = "none",
    at_centerline: bool = False,
    blocked_at_centerline: bool = False,
) -> bool | None:
    if exercise.expected_direction == "none":
        return swing_dir == "none" and swing_phase == "idle" and attack == "none"
    if swing_phase == "idle" and attack == "none" and velocity_dir == "none":
        return None

    if exercise.motion_role == "withdraw":
        if velocity_dir == exercise.expected_direction:
            return True
        if swing_dir == exercise.expected_direction:
            return True
        if swing_phase != "idle" and velocity_dir not in ("none", ""):
            return False
        return None

    if exercise.end_at_centerline:
        if swing_dir == exercise.expected_direction:
            return True
        if blocked_at_centerline and swing_dir == exercise.expected_direction:
            return True
        if at_centerline and swing_phase == "end" and swing_dir == exercise.expected_direction:
            return True
        if swing_phase != "idle" and swing_dir not in ("none", ""):
            if swing_dir != exercise.expected_direction:
                return False
        return None

    return swing_dir == exercise.expected_direction


def _record_frame(
    vision: AttackVision,
    frame,
    t_rel: float,
    saber: SaberEvalHelper | None = None,
    *,
    attack: str | None = None,
    swing=None,
    saber_line: SaberLine | None = None,
) -> FrameRecord:
    if attack is None or swing is None:
        attack, swing, saber_line = _eval_frame(vision, frame, saber)
    vel_dir = direction_from_velocity(
        getattr(swing, "vx", 0.0),
        getattr(swing, "vy", 0.0),
        getattr(swing, "speed", 0.0),
        swing.kind,
    )
    at_cl, blocked = _pose_flags(vision, swing.direction)
    return FrameRecord(
        t_rel=round(t_rel, 4),
        attack=attack,
        swing_direction=swing.direction,
        swing_phase=swing.phase,
        swing_kind=swing.kind,
        tracked=vision.last_landmarks is not None,
        saber_detected=saber_line is not None,
        saber_orientation=saber_line.orientation if saber_line else "",
        saber_confidence=round(saber_line.confidence, 3) if saber_line else 0.0,
        saber_source=getattr(saber_line, "source", "") if saber_line else "",
        saber_axis_method=getattr(saber_line, "axis_method", "") if saber_line else "",
        saber_tip_in_frame=getattr(saber_line, "tip_in_frame", True) if saber_line else True,
        swing_uses_saber=vision.last_fused_saber,
        grip_speed=round(getattr(swing, "speed", 0.0), 4),
        vx=round(getattr(swing, "vx", 0.0), 4),
        vy=round(getattr(swing, "vy", 0.0), 4),
        velocity_direction=vel_dir,
        at_centerline=at_cl,
        blocked_at_centerline=blocked,
    )


def _trial_payload(
    exercise: SwingExercise,
    frames: list[FrameRecord],
    *,
    discrete: bool,
    video_path: str | None = None,
) -> dict:
    payload = {
        "exercise_id": exercise.id,
        "title": exercise.title,
        "prompt": exercise.prompt,
        "body_hint": exercise.body_hint,
        "expected_direction": exercise.expected_direction,
        "expected_kind": exercise.expected_kind,
        "motion_role": exercise.motion_role,
        "end_at_centerline": exercise.end_at_centerline,
        "follows_strike": exercise.follows_strike,
        "frames": [asdict(f) for f in frames],
        "trial_mode": "discrete" if discrete else "continuous",
    }
    if discrete:
        payload["prep_sec"] = exercise.prep_sec
        payload["swing_max_sec"] = exercise.swing_max_sec
        if exercise.rep_index:
            payload["rep_index"] = exercise.rep_index
            payload["rep_total"] = exercise.rep_total
    else:
        payload["duration_sec"] = exercise.duration_sec
    if video_path:
        payload["video_path"] = video_path
    return payload


def _format_swing_line(swing, *, fused: bool = False) -> str:
    line = f"swing: {swing.phase} | {swing.kind} -> {swing.direction}"
    if fused:
        line += " [fused]"
    return line


def _is_discrete_session(exercises: list[SwingExercise]) -> bool:
    return bool(exercises) and exercises[0].duration_sec <= 0


def _trial_motion_seen(rec: FrameRecord) -> bool:
    return rec.swing_phase != "idle" or rec.attack not in ("none", None)


def _trial_best_match(exercise: SwingExercise, frames: list[FrameRecord]) -> bool | None:
    if exercise.expected_direction == "none":
        if not frames:
            return None
        return all(
            f.swing_phase == "idle" and f.attack == "none" and f.swing_direction == "none"
            for f in frames
        )
    for f in frames:
        if not _trial_motion_seen(f):
            continue
        if exercise.motion_role == "withdraw":
            if f.velocity_direction == exercise.expected_direction:
                return True
            if f.swing_direction == exercise.expected_direction:
                return True
        elif exercise.end_at_centerline:
            if f.swing_direction == exercise.expected_direction:
                return True
            if f.blocked_at_centerline and f.swing_direction == exercise.expected_direction:
                return True
        elif f.swing_direction == exercise.expected_direction:
            return True
    for f in frames:
        if _trial_motion_seen(f):
            return False
    return None


def _draw_recording_badge(frame, remaining: float, total: float) -> None:
    """Large on-frame REC badge — visible even when HUD is busy."""
    h, w = frame.shape[:2]
    secs = max(0.0, remaining)
    badge = f"REC {secs:.1f}s"
    scale = 1.2
    thickness = 3
    (tw, th), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    pad = 10
    x = w - tw - pad - 16
    y = h - pad
    cv2.rectangle(
        frame,
        (x - pad, y - th - pad),
        (x + tw + pad, y + pad // 2),
        (0, 0, 0),
        -1,
    )
    cv2.rectangle(
        frame,
        (x - pad, y - th - pad),
        (x + tw + pad, y + pad // 2),
        (0, 0, 255),
        2,
    )
    cv2.putText(
        frame,
        badge,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (0, 0, 255),
        thickness,
    )
    if total > 0:
        frac = max(0.0, min(1.0, (total - secs) / total))
        cv2.rectangle(frame, (0, h - 6), (w, h), (40, 40, 40), -1)
        cv2.rectangle(frame, (0, h - 6), (int(w * frac), h), (0, 0, 255), -1)


def _show_live_frame(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None,
    *,
    phase_label: str,
    countdown: float | None,
    hud_prompt: str | None = None,
    match_ok: bool | None = None,
    log_frames: bool = False,
    frame_sink: list[FrameRecord] | None = None,
    t0: float | None = None,
    recording_total_sec: float | None = None,
    video_recorder: TrialVideoRecorder | None = None,
) -> int:
    """Render one preview frame. Returns key pressed (0 if none)."""
    frame = camera.read_frame()
    if frame is None:
        return 0

    attack, swing, saber_line = _eval_frame(vision, frame, saber)
    swing_line = _format_swing_line(swing, fused=vision.last_fused_saber)
    if log_frames and frame_sink is not None and t0 is not None:
        rec = _record_frame(
            vision,
            frame,
            time.monotonic() - t0,
            saber,
            attack=attack,
            swing=swing,
            saber_line=saber_line,
        )
        frame_sink.append(rec)
        match_ok = _match_expected(
            exercise,
            rec.attack,
            rec.swing_direction,
            rec.swing_phase,
            velocity_dir=rec.velocity_direction,
            at_centerline=rec.at_centerline,
            blocked_at_centerline=rec.blocked_at_centerline,
        )

    preview = _render_preview(
        overlay,
        frame,
        vision,
        attack=attack,
        swing_line=swing_line,
        saber_line=saber_line,
    )
    _draw_eval_hud(
        preview,
        exercise=exercise,
        exercise_index=exercise_index,
        exercise_total=exercise_total,
        phase_label=phase_label,
        countdown=countdown,
        attack=attack,
        swing_line=swing_line if phase_label != "GET READY" else "",
        match_ok=match_ok,
        hud_prompt=hud_prompt,
        recording_total_sec=recording_total_sec,
    )
    if (
        phase_label in ("SWING NOW", "HOLD STILL", "RECORDING")
        and countdown is not None
        and recording_total_sec
    ):
        _draw_recording_badge(preview, countdown, recording_total_sec)
    if log_frames and video_recorder is not None:
        video_recorder.write(preview)
    cv2.imshow("Swing Eval", preview)
    return cv2.waitKey(1) & 0xFF


def _run_get_ready(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None = None,
) -> str:
    """Countdown to start position, then auto-start recording. Returns status."""
    vision.reset_swing()
    ready_end = time.monotonic() + exercise.prep_sec

    while True:
        now = time.monotonic()
        remaining = ready_end - now
        if remaining <= 0:
            return "go"

        key = _show_live_frame(
            camera,
            vision,
            overlay,
            exercise,
            exercise_index,
            exercise_total,
            saber,
            phase_label="GET READY",
            countdown=remaining,
            hud_prompt=exercise.ready_prompt,
        )
        if key == ord("q"):
            return "quit"
        if key == ord("s"):
            return "skip"
        if key == ord("b"):
            return "back"


def _run_swing_capture(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None = None,
    *,
    video_dir: Path | None = None,
    logs_root: Path | None = None,
) -> tuple[list[FrameRecord], str, str | None]:
    """Record one swing (or rest hold) for a fixed window. Returns (frames, status, video_path)."""
    frames: list[FrameRecord] = []
    vision.reset_swing()
    start = time.monotonic()
    end = start + exercise.swing_max_sec
    is_rest = exercise.expected_direction == "none"
    record_total = exercise.swing_max_sec
    video_recorder: TrialVideoRecorder | None = None
    if video_dir is not None:
        fps = float(getattr(config, "CAMERA_FPS", 30) or 30)
        video_recorder = TrialVideoRecorder(
            _trial_video_path(video_dir, exercise_index, exercise),
            fps,
        )

    def _video_rel(saved: Path | None) -> str | None:
        if saved is None or logs_root is None:
            return None
        return str(saved.relative_to(logs_root))

    while time.monotonic() < end:
        remaining = end - time.monotonic()
        key = _show_live_frame(
            camera,
            vision,
            overlay,
            exercise,
            exercise_index,
            exercise_total,
            saber,
            phase_label="RECORDING" if not is_rest else "HOLD STILL",
            countdown=remaining,
            hud_prompt=exercise.prompt,
            log_frames=True,
            frame_sink=frames,
            t0=start,
            recording_total_sec=record_total,
            video_recorder=video_recorder,
        )
        if key == ord("q"):
            return frames, "quit", _video_rel(
                video_recorder.close() if video_recorder else None
            )
        if key == ord("s"):
            if video_recorder is not None:
                video_recorder.discard()
            return frames, "skip", None
        if key == ord("b"):
            if video_recorder is not None:
                video_recorder.discard()
            return frames, "back", None

    return frames, "ok", _video_rel(video_recorder.close() if video_recorder else None)


def _run_done_pause(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    frames: list[FrameRecord],
    saber: SaberEvalHelper | None = None,
) -> str:
    """Show result until SPACE. Returns 'next', 'skip', or 'quit'."""
    match_ok = _trial_best_match(exercise, frames)
    while True:
        key = _show_live_frame(
            camera,
            vision,
            overlay,
            exercise,
            exercise_index,
            exercise_total,
            saber,
            phase_label="DONE",
            countdown=None,
            hud_prompt=exercise.prompt,
            match_ok=match_ok,
        )
        if key == ord("q"):
            return "quit"
        if key == ord("s"):
            return "skip"
        if key == ord("b"):
            return "back"
        if key == ord(" "):
            return "next"


def _run_discrete_trial(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None = None,
    *,
    video_dir: Path | None = None,
    logs_root: Path | None = None,
) -> tuple[list[FrameRecord] | None, str, str | None]:
    """
    GET READY → one swing → DONE.
    Returns (frames, status, video_path) where status is 'ok', 'skip', or 'quit'.
    """
    ready = _run_get_ready(
        camera, vision, overlay, exercise, exercise_index, exercise_total, saber
    )
    if ready in ("quit", "skip", "back"):
        return None, ready, None

    frames, capture_status, video_path = _run_swing_capture(
        camera,
        vision,
        overlay,
        exercise,
        exercise_index,
        exercise_total,
        saber,
        video_dir=video_dir,
        logs_root=logs_root,
    )
    if capture_status in ("quit", "skip", "back"):
        return (
            frames if capture_status == "quit" and frames else None,
            capture_status,
            video_path if capture_status == "quit" else None,
        )

    done = _run_done_pause(
        camera,
        vision,
        overlay,
        exercise,
        exercise_index,
        exercise_total,
        frames,
        saber,
    )
    if done in ("quit", "skip", "back"):
        return (
            frames if done == "quit" else None,
            done,
            video_path if done == "quit" else None,
        )
    return frames, "ok", video_path


def _run_prep(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None = None,
) -> str:
    """Prep countdown. Returns 'ready', 'skip', or 'quit'."""
    prep_end = time.monotonic() + exercise.prep_sec
    while True:
        frame = camera.read_frame()
        if frame is None:
            continue
        now = time.monotonic()
        remaining = prep_end - now
        if remaining <= 0:
            return "ready"

        attack, swing, saber_line = _eval_frame(vision, frame, saber)
        swing_line = _format_swing_line(swing, fused=vision.last_fused_saber)
        preview = _render_preview(
            overlay,
            frame,
            vision,
            attack=attack,
            swing_line=swing_line,
            saber_line=saber_line,
        )
        _draw_eval_hud(
            preview,
            exercise=exercise,
            exercise_index=exercise_index,
            exercise_total=exercise_total,
            phase_label="PREP",
            countdown=remaining,
            attack=attack,
            swing_line=swing_line,
            match_ok=None,
        )
        cv2.imshow("Swing Eval", preview)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            return "quit"
        if key == ord("s"):
            return "skip"
        if key == ord(" "):
            return "ready"


def _run_record(
    camera,
    vision: AttackVision,
    overlay: AttackOverlay,
    exercise: SwingExercise,
    exercise_index: int,
    exercise_total: int,
    saber: SaberEvalHelper | None = None,
) -> tuple[list[FrameRecord], bool]:
    """Record one exercise. Returns (frames, user_quit)."""
    frames: list[FrameRecord] = []
    vision.reset_swing()
    start = time.monotonic()
    end = start + exercise.duration_sec

    while time.monotonic() < end:
        frame = camera.read_frame()
        if frame is None:
            continue
        attack, swing, saber_line = _eval_frame(vision, frame, saber)
        t_rel = time.monotonic() - start
        rec = _record_frame(
            vision,
            frame,
            t_rel,
            saber,
            attack=attack,
            swing=swing,
            saber_line=saber_line,
        )
        frames.append(rec)

        match_ok = _match_expected(
            exercise,
            rec.attack,
            rec.swing_direction,
            rec.swing_phase,
            velocity_dir=rec.velocity_direction,
            at_centerline=rec.at_centerline,
            blocked_at_centerline=rec.blocked_at_centerline,
        )
        swing_line = _format_swing_line(
            swing,
            fused=rec.swing_uses_saber,
        )
        preview = _render_preview(
            overlay,
            frame,
            vision,
            attack=rec.attack,
            swing_line=swing_line,
            saber_line=saber_line,
        )
        _draw_eval_hud(
            preview,
            exercise=exercise,
            exercise_index=exercise_index,
            exercise_total=exercise_total,
            phase_label="RECORD",
            countdown=None,
            attack=rec.attack,
            swing_line=swing_line,
            match_ok=match_ok,
        )
        cv2.imshow("Swing Eval", preview)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            return frames, True
        if key == ord("s"):
            return frames, False

    return frames, False


def run_session(
    *,
    exercises: list[SwingExercise],
    out_dir: Path,
    camera_source: str,
    saber: SaberEvalHelper | None = None,
    discrete: bool = True,
    record_video: bool = True,
) -> Path | None:
    camera = open_camera()
    vision = AttackVision()
    overlay = AttackOverlay()

    trials: list[dict] = []
    user_quit = False
    session_stamp: str | None = None
    video_dir: Path | None = None

    if any(e.end_at_centerline or e.motion_role == "withdraw" for e in exercises):
        print_centerline_eval_legend()
    else:
        print_body_direction_legend()
    if saber is not None and saber.mode != "none":
        print(
            f"Saber overlay: profile={saber.profile!r} mode={saber.mode!r} "
            f"yolo_loaded={saber.yolo_loaded} yolo_every={config.SABER_YOLO_EVERY_N_FRAMES}"
        )
    print(f"Session: {session_summary(exercises)}")
    if discrete and record_video:
        print("Trial videos: REC window only (overlay + HUD) → swing_eval_logs/videos/")
    print("Press SPACE in the preview window to start.\n")

    waiting = True
    while waiting and not user_quit:
        frame = camera.read_frame()
        if frame is None:
            continue
        preview = overlay.render(frame, "none")
        _draw_eval_hud(
            preview,
            exercise=None,
            exercise_index=0,
            exercise_total=len(exercises),
            phase_label="READY",
            countdown=None,
            attack="none",
            swing_line="",
            match_ok=None,
        )
        cv2.putText(
            preview,
            session_summary(exercises),
            (12, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 200, 200),
            1,
        )
        cv2.imshow("Swing Eval", preview)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            waiting = False
            session_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            if discrete and record_video:
                video_dir = out_dir / "videos" / f"session_{session_stamp}"
        elif key == ord("q"):
            user_quit = True

    idx = 0
    while idx < len(exercises) and not user_quit:
        exercise = exercises[idx]

        print(f"[{idx + 1}/{len(exercises)}] {exercise.title}")

        if discrete:
            frames, status, video_path = _run_discrete_trial(
                camera,
                vision,
                overlay,
                exercise,
                idx,
                len(exercises),
                saber=saber,
                video_dir=video_dir if record_video else None,
                logs_root=out_dir,
            )
            if status == "back":
                if idx > 0:
                    idx -= 1
                    if trials:
                        trials.pop()
                    print("  back to previous trial")
                continue
            if status == "quit":
                user_quit = True
                if frames:
                    trials.append(
                        _trial_payload(
                            exercise, frames, discrete=True, video_path=video_path
                        )
                    )
                break
            if status == "skip":
                print("  skipped")
                idx += 1
                continue
            if frames:
                trials.append(
                    _trial_payload(
                        exercise, frames, discrete=True, video_path=video_path
                    )
                )
                match = _trial_best_match(exercise, frames)
                print(
                    f"  logged {len(frames)} frames  "
                    f"match={'yes' if match else 'no' if match is False else '?'}"
                )
                if video_path:
                    print(f"  video: {video_path}")
            idx += 1
            continue

        prep = _run_prep(
            camera, vision, overlay, exercise, idx, len(exercises), saber=saber
        )
        if prep == "quit":
            user_quit = True
            break
        if prep == "skip":
            print("  skipped")
            idx += 1
            continue

        frames, quit_now = _run_record(
            camera, vision, overlay, exercise, idx, len(exercises), saber=saber
        )
        trials.append(_trial_payload(exercise, frames, discrete=False))
        print(f"  logged {len(frames)} frames")
        if quit_now:
            user_quit = True
            break
        idx += 1

    vision.close()
    if saber is not None:
        saber.close()
    camera.release()
    cv2.destroyAllWindows()

    if not trials:
        print("No data recorded.")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = session_stamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"session_{stamp}.json"
    payload = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "camera_source": camera_source,
        "saber_profile": saber.profile if saber else "",
        "saber_detector": saber.mode if saber else "none",
        "saber_yolo_loaded": saber.yolo_loaded if saber else False,
        "saber_yolo_every": getattr(config, "SABER_YOLO_EVERY_N_FRAMES", 3)
        if saber
        else 0,
        "config": _swing_config_snapshot(),
        "saber_axis": axis_flags_snapshot(),
        "trial_mode": "discrete" if discrete else "continuous",
        "trials": trials,
    }
    if video_dir is not None and video_dir.is_dir():
        payload["video_dir"] = str(video_dir.relative_to(out_dir))
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\nSaved: {out_path}")
    if video_dir is not None and video_dir.is_dir():
        n_videos = sum(1 for t in trials if t.get("video_path"))
        print(f"Videos: {video_dir.relative_to(out_dir)} ({n_videos} trials)")
    return out_path


def parse_args():
    p = argparse.ArgumentParser(description="Guided swing eval + logging")
    add_camera_cli(p)
    p.add_argument(
        "--out",
        type=Path,
        default=LOG_DIR,
        help=f"Output directory (default: {LOG_DIR.name}/)",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="2 swings per direction (vs 3) and slightly shorter countdowns",
    )
    p.add_argument(
        "--no-video",
        action="store_true",
        help="Disable per-trial mp4 recording during REC windows",
    )
    p.add_argument(
        "--continuous",
        action="store_true",
        help="Legacy mode: long recording windows with multiple reps per trial",
    )
    p.add_argument(
        "--per-direction",
        type=int,
        default=3,
        metavar="N",
        help="Single swings per direction in discrete mode (default: 3; --quick uses 2)",
    )
    p.add_argument(
        "--ready-sec",
        type=float,
        default=5.0,
        metavar="SEC",
        help="GET READY countdown before each swing (default: 5)",
    )
    p.add_argument(
        "--swing-max-sec",
        type=float,
        default=3.0,
        metavar="SEC",
        help="Seconds to record each swing — hold end pose inside this window (default: 3)",
    )
    p.add_argument(
        "--no-report",
        action="store_true",
        help="Skip printing score report after session",
    )
    p.add_argument(
        "--saber",
        default=None,
        help=f"Red saber profile for YOLO overlay ({', '.join(list_profiles())})",
    )
    p.add_argument(
        "--detector",
        choices=("yolo", "legacy", "color"),
        default="yolo",
        help="Saber detector: yolo=YOLO+arm (default), legacy=arm+YOLO if weights exist, color=HSV",
    )
    p.add_argument(
        "--yolo-every",
        type=int,
        default=3,
        metavar="N",
        help="Run saber YOLO every N frames; reuse last bbox between (default: 3)",
    )
    p.add_argument(
        "--centerline",
        action="store_true",
        help="Centerline-only eval: L/R strikes stop at midline + paired withdraw trials",
    )
    p.add_argument(
        "--saber-axis",
        default="1_color_roi",
        metavar="PRESET",
        help=(
            "Axis tracking todos: "
            + ", ".join(list_axis_presets())
            + " — see SABER-AXIS-TODO.md"
        ),
    )
    p.add_argument(
        "--saber-track",
        choices=("tip", "forearm", "inset_tip"),
        default=None,
        help="YOLO blade track point: tip, forearm from grip, or inset_tip (default: inset_tip)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    if args.saber_track is not None:
        config.SWING_SABER_TRACK_POINT = args.saber_track
    enabled_axis = apply_axis_preset(args.saber_axis)
    if enabled_axis:
        print(f"Saber axis preset {args.saber_axis!r}: {', '.join(enabled_axis)}")
    elif args.saber_axis != "baseline":
        print(f"Saber axis preset: {args.saber_axis!r} (baseline)")
    exercises = session_for(
        quick=args.quick,
        continuous=args.continuous,
        centerline=args.centerline,
        per_direction=args.per_direction,
        ready_sec=args.ready_sec,
        swing_max_sec=args.swing_max_sec,
    )
    discrete = _is_discrete_session(exercises)
    camera_source = getattr(config, "CAMERA_SOURCE", "unknown")
    saber = (
        _make_saber_helper(args.saber, args.detector, yolo_every=args.yolo_every)
        if args.saber
        else None
    )

    out_path = run_session(
        exercises=exercises,
        out_dir=args.out,
        camera_source=camera_source,
        saber=saber if args.saber else None,
        discrete=discrete,
        record_video=not args.no_video,
    )
    if out_path and not args.no_report:
        print()
        print(analyze_log_file(out_path))


if __name__ == "__main__":
    main()
