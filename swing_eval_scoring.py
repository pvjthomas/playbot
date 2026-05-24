"""
Score swing eval logs — pure functions for offline analysis and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config


@dataclass(frozen=True)
class TrialScore:
    exercise_id: str
    title: str
    expected_direction: str
    expected_kind: str | None
    frame_count: int
    tracked_fraction: float
    # Rest trials
    idle_fraction: float | None = None
    false_direction_fraction: float | None = None
    # Swing trials — legacy frame fractions
    motion_frame_count: int | None = None
    swing_direction_accuracy: float | None = None
    attack_direction_accuracy: float | None = None
    kind_accuracy: float | None = None
    saw_begin: bool | None = None
    saw_mid: bool | None = None
    saw_end: bool | None = None
    phase_fractions: dict[str, float] | None = None
    saber_detect_fraction: float | None = None
    # Strong-movement characterization
    peak_speed: float | None = None
    peak_velocity_direction: str | None = None
    peak_velocity_match: bool | None = None
    strong_frame_accuracy: float | None = None
    strong_frame_count: int | None = None
    trial_pass: bool | None = None
    motion_role: str | None = None
    centerline_end_ok: bool | None = None
    started_at_center: bool | None = None


@dataclass(frozen=True)
class SessionScore:
    log_path: str
    trial_scores: tuple[TrialScore, ...]
    overall_swing_direction_accuracy: float | None
    overall_attack_direction_accuracy: float | None
    overall_idle_fraction: float | None
    overall_false_direction_fraction: float | None
    overall_peak_velocity_match: float | None = None
    overall_trial_pass_rate: float | None = None
    overall_strong_frame_accuracy: float | None = None


def _frame_list(trial: dict[str, Any]) -> list[dict[str, Any]]:
    return trial.get("frames") or []


def _is_motion_frame(frame: dict[str, Any]) -> bool:
    return frame.get("swing_phase") != "idle" or frame.get("attack") not in (
        None,
        "none",
    )


def _velocity_label(frame: dict[str, Any]) -> str:
    if frame.get("velocity_direction") not in (None, "none", ""):
        return str(frame["velocity_direction"])
    vx = float(frame.get("vx") or 0.0)
    vy = float(frame.get("vy") or 0.0)
    speed = float(frame.get("grip_speed") or 0.0)
    kind = frame.get("swing_kind") or "linear"
    if speed < config.SWING_VELOCITY_DIR_MIN:
        return "none"
    try:
        from swing_tracker import direction_from_velocity

        return direction_from_velocity(vx, vy, speed, kind)  # type: ignore[arg-type]
    except Exception:
        return "none"


def _strong_motion_metrics(
    frames: list[dict[str, Any]], expected_dir: str, *, trial: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Peak velocity direction + strong-frame consensus for one swing trial."""
    motion_role = (trial or {}).get("motion_role", "strike")
    end_at_centerline = bool((trial or {}).get("end_at_centerline"))

    speeds = [float(f.get("grip_speed") or 0.0) for f in frames]
    peak_speed = max(speeds) if speeds else 0.0
    if peak_speed <= 0:
        return {
            "peak_speed": 0.0,
            "peak_velocity_direction": "none",
            "peak_velocity_match": False,
            "strong_frame_accuracy": 0.0,
            "strong_frame_count": 0,
            "trial_pass": False,
        }

    peak_frame = max(frames, key=lambda f: float(f.get("grip_speed") or 0.0))
    peak_dir = _velocity_label(peak_frame)
    if peak_dir == "none":
        peak_dir = peak_frame.get("swing_direction") or "none"

    threshold = peak_speed * config.SWING_STRONG_SPEED_RATIO
    strong = [f for f in frames if float(f.get("grip_speed") or 0.0) >= threshold]
    if not strong:
        strong = [peak_frame]

    strong_ok = 0
    for f in strong:
        label = _velocity_label(f)
        if label == "none":
            label = f.get("swing_direction") or "none"
        if label == expected_dir:
            strong_ok += 1

    strong_acc = strong_ok / len(strong)
    peak_match = peak_dir == expected_dir

    centerline_end_ok = False
    if end_at_centerline:
        end_frames = [
            f
            for f in frames
            if f.get("swing_phase") == "end"
            or f.get("blocked_at_centerline")
            or (
                f.get("at_centerline")
                and f.get("swing_direction") == expected_dir
            )
        ]
        if end_frames:
            centerline_end_ok = any(
                f.get("blocked_at_centerline")
                or (
                    f.get("at_centerline")
                    and f.get("swing_direction") == expected_dir
                )
                for f in end_frames
            )

    started_at_center = False
    if motion_role == "withdraw":
        early = frames[: max(1, len(frames) // 3)]
        started_at_center = any(f.get("at_centerline") for f in early)

    if motion_role == "withdraw":
        trial_pass = peak_match or (strong_acc >= 0.5 and peak_dir != "none")
    elif end_at_centerline:
        trial_pass = (
            peak_match
            or centerline_end_ok
            or (strong_acc >= 0.5 and peak_dir == expected_dir)
        )
    else:
        trial_pass = peak_match or (strong_acc >= 0.5 and peak_dir != "none")

    return {
        "peak_speed": peak_speed,
        "peak_velocity_direction": peak_dir,
        "peak_velocity_match": peak_match,
        "strong_frame_accuracy": strong_acc,
        "strong_frame_count": len(strong),
        "trial_pass": trial_pass,
        "centerline_end_ok": centerline_end_ok,
        "started_at_center": started_at_center,
    }


def score_trial(trial: dict[str, Any]) -> TrialScore:
    exercise_id = trial.get("exercise_id", "?")
    title = trial.get("title", exercise_id)
    expected_dir = trial.get("expected_direction", "none")
    expected_kind = trial.get("expected_kind")
    motion_role = trial.get("motion_role", "strike")
    end_at_centerline = bool(trial.get("end_at_centerline"))
    frames = _frame_list(trial)
    n = len(frames)
    if n == 0:
        return TrialScore(
            exercise_id=exercise_id,
            title=title,
            expected_direction=expected_dir,
            expected_kind=expected_kind,
            frame_count=0,
            tracked_fraction=0.0,
        )

    tracked = sum(1 for f in frames if f.get("tracked")) / n
    saber_frac: float | None = None
    if any("saber_detected" in f for f in frames):
        saber_frac = sum(1 for f in frames if f.get("saber_detected")) / n

    if expected_dir == "none":
        idle_n = sum(1 for f in frames if f.get("swing_phase") == "idle")
        false_n = sum(
            1
            for f in frames
            if f.get("swing_direction") not in (None, "none")
            or f.get("attack") not in (None, "none")
        )
        return TrialScore(
            exercise_id=exercise_id,
            title=title,
            expected_direction=expected_dir,
            expected_kind=expected_kind,
            frame_count=n,
            tracked_fraction=tracked,
            idle_fraction=idle_n / n,
            false_direction_fraction=false_n / n,
            saber_detect_fraction=saber_frac,
        )

    motion = [f for f in frames if _is_motion_frame(f)]
    motion_n = len(motion)
    if motion_n == 0:
        return TrialScore(
            exercise_id=exercise_id,
            title=title,
            expected_direction=expected_dir,
            expected_kind=expected_kind,
            frame_count=n,
            tracked_fraction=tracked,
            motion_frame_count=0,
            swing_direction_accuracy=0.0,
            attack_direction_accuracy=0.0,
            kind_accuracy=None if expected_kind is None else 0.0,
            saw_begin=False,
            saw_mid=False,
            saw_end=False,
            phase_fractions={"idle": 1.0, "begin": 0.0, "mid": 0.0, "end": 0.0},
            peak_speed=0.0,
            peak_velocity_direction="none",
            peak_velocity_match=False,
            strong_frame_accuracy=0.0,
            strong_frame_count=0,
            trial_pass=False,
        )

    swing_ok = sum(
        1 for f in motion if f.get("swing_direction") == expected_dir
    ) / motion_n
    attack_ok = sum(1 for f in motion if f.get("attack") == expected_dir) / motion_n

    kind_acc: float | None = None
    if expected_kind is not None:
        kind_acc = sum(
            1 for f in motion if f.get("swing_kind") == expected_kind
        ) / motion_n

    phases_seen = {f.get("swing_phase") for f in frames}
    phase_counts: dict[str, int] = {"idle": 0, "begin": 0, "mid": 0, "end": 0}
    for f in motion:
        ph = f.get("swing_phase") or "idle"
        if ph in phase_counts:
            phase_counts[ph] += 1
    phase_fractions = {k: v / motion_n for k, v in phase_counts.items()}

    strength = _strong_motion_metrics(frames, expected_dir, trial=trial)

    return TrialScore(
        exercise_id=exercise_id,
        title=title,
        expected_direction=expected_dir,
        expected_kind=expected_kind,
        frame_count=n,
        tracked_fraction=tracked,
        motion_frame_count=motion_n,
        swing_direction_accuracy=swing_ok,
        attack_direction_accuracy=attack_ok,
        kind_accuracy=kind_acc,
        saw_begin="begin" in phases_seen,
        saw_mid="mid" in phases_seen,
        saw_end="end" in phases_seen,
        phase_fractions=phase_fractions,
        saber_detect_fraction=saber_frac,
        peak_speed=strength["peak_speed"],
        peak_velocity_direction=strength["peak_velocity_direction"],
        peak_velocity_match=strength["peak_velocity_match"],
        strong_frame_accuracy=strength["strong_frame_accuracy"],
        strong_frame_count=strength["strong_frame_count"],
        trial_pass=strength["trial_pass"],
        motion_role=motion_role if expected_dir != "none" else None,
        centerline_end_ok=strength.get("centerline_end_ok") if end_at_centerline else None,
        started_at_center=strength.get("started_at_center")
        if motion_role == "withdraw"
        else None,
    )


def score_session(log: dict[str, Any], *, log_path: str = "") -> SessionScore:
    trials = log.get("trials") or []
    trial_scores = tuple(score_trial(t) for t in trials)

    swing_dirs: list[float] = []
    attack_dirs: list[float] = []
    idle_fracs: list[float] = []
    false_fracs: list[float] = []
    peak_matches: list[float] = []
    trial_passes: list[float] = []
    strong_accs: list[float] = []

    for ts in trial_scores:
        if ts.expected_direction == "none":
            if ts.idle_fraction is not None:
                idle_fracs.append(ts.idle_fraction)
            if ts.false_direction_fraction is not None:
                false_fracs.append(ts.false_direction_fraction)
        else:
            if ts.swing_direction_accuracy is not None:
                swing_dirs.append(ts.swing_direction_accuracy)
            if ts.attack_direction_accuracy is not None:
                attack_dirs.append(ts.attack_direction_accuracy)
            if ts.peak_velocity_match is not None:
                peak_matches.append(1.0 if ts.peak_velocity_match else 0.0)
            if ts.trial_pass is not None:
                trial_passes.append(1.0 if ts.trial_pass else 0.0)
            if ts.strong_frame_accuracy is not None:
                strong_accs.append(ts.strong_frame_accuracy)

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    return SessionScore(
        log_path=log_path,
        trial_scores=trial_scores,
        overall_swing_direction_accuracy=_mean(swing_dirs),
        overall_attack_direction_accuracy=_mean(attack_dirs),
        overall_idle_fraction=_mean(idle_fracs),
        overall_false_direction_fraction=_mean(false_fracs),
        overall_peak_velocity_match=_mean(peak_matches),
        overall_trial_pass_rate=_mean(trial_passes),
        overall_strong_frame_accuracy=_mean(strong_accs),
    )


def format_report(score: SessionScore) -> str:
    lines: list[str] = []
    header = "Swing eval report"
    if score.log_path:
        header += f" — {score.log_path}"
    lines.append(header)
    lines.append("=" * len(header))

    if score.overall_peak_velocity_match is not None:
        pct = score.overall_peak_velocity_match * 100
        lines.append(f"Overall peak velocity direction match: {pct:.0f}%")
    if score.overall_trial_pass_rate is not None:
        pct = score.overall_trial_pass_rate * 100
        lines.append(f"Overall trial pass (peak or strong consensus): {pct:.0f}%")
    if score.overall_strong_frame_accuracy is not None:
        pct = score.overall_strong_frame_accuracy * 100
        lines.append(f"Overall strong-frame direction match: {pct:.0f}%")
    if score.overall_swing_direction_accuracy is not None:
        pct = score.overall_swing_direction_accuracy * 100
        lines.append(
            f"Overall swing direction (all motion frames): {pct:.0f}% correct"
        )
    if score.overall_attack_direction_accuracy is not None:
        pct = score.overall_attack_direction_accuracy * 100
        lines.append(f"Overall attack direction (motion frames): {pct:.0f}% correct")
    if score.overall_idle_fraction is not None:
        pct = score.overall_idle_fraction * 100
        lines.append(f"Rest idle phase: {pct:.0f}% of frames")
    if score.overall_false_direction_fraction is not None:
        pct = score.overall_false_direction_fraction * 100
        lines.append(f"Rest false direction: {pct:.0f}% of frames")

    lines.append("")
    for ts in score.trial_scores:
        lines.append(f"--- {ts.title} ({ts.exercise_id}) ---")
        lines.append(
            f"  frames={ts.frame_count}  tracked={ts.tracked_fraction * 100:.0f}%"
        )
        if ts.expected_direction == "none":
            if ts.idle_fraction is not None:
                lines.append(f"  idle phase: {ts.idle_fraction * 100:.0f}%")
            if ts.false_direction_fraction is not None:
                lines.append(
                    f"  false direction: {ts.false_direction_fraction * 100:.0f}%"
                )
        else:
            lines.append(f"  motion frames: {ts.motion_frame_count}")
            if ts.peak_speed is not None:
                lines.append(f"  peak speed: {ts.peak_speed:.3f} norm/s")
            if ts.peak_velocity_direction is not None:
                match = "PASS" if ts.peak_velocity_match else "FAIL"
                lines.append(
                    f"  peak velocity dir: {ts.peak_velocity_direction} "
                    f"(expected {ts.expected_direction}) — {match}"
                )
            if ts.strong_frame_accuracy is not None:
                lines.append(
                    f"  strong frames: {ts.strong_frame_count}  "
                    f"dir match: {ts.strong_frame_accuracy * 100:.0f}%"
                )
            if ts.trial_pass is not None:
                lines.append(f"  trial verdict: {'PASS' if ts.trial_pass else 'FAIL'}")
            if ts.centerline_end_ok is not None:
                lines.append(
                    f"  blocked at centerline: {'yes' if ts.centerline_end_ok else 'no'}"
                )
            if ts.started_at_center is not None:
                lines.append(
                    f"  started at centerline: {'yes' if ts.started_at_center else 'no'}"
                )
            if ts.swing_direction_accuracy is not None:
                lines.append(
                    f"  swing dir (all motion): {ts.swing_direction_accuracy * 100:.0f}%"
                )
            if ts.attack_direction_accuracy is not None:
                lines.append(
                    f"  attack dir (all motion): {ts.attack_direction_accuracy * 100:.0f}%"
                )
            if ts.kind_accuracy is not None:
                lines.append(f"  kind correct: {ts.kind_accuracy * 100:.0f}%")
            phases = []
            if ts.saw_begin:
                phases.append("begin")
            if ts.saw_mid:
                phases.append("mid")
            if ts.saw_end:
                phases.append("end")
            lines.append(f"  phases seen: {', '.join(phases) or 'none'}")
            if ts.phase_fractions:
                pf = ts.phase_fractions
                lines.append(
                    "  phase mix (motion): "
                    f"begin={pf.get('begin', 0) * 100:.0f}% "
                    f"mid={pf.get('mid', 0) * 100:.0f}% "
                    f"end={pf.get('end', 0) * 100:.0f}%"
                )
        if ts.saber_detect_fraction is not None:
            lines.append(f"  saber detected: {ts.saber_detect_fraction * 100:.0f}%")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
