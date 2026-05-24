"""
Guided swing exercises for temporal detection eval.

Discrete mode (default): one swing per countdown. Each strike direction is
prompted 2–3 separate times so every attempt starts from a clean idle/rest pose.

Prompts use **body** wording (your left/right, which arm) — not screen edges.
"""

from __future__ import annotations

from dataclasses import dataclass

from directions import (
    CENTERLINE_GET_READY,
    CENTERLINE_REST_READY,
    SWING_RECOVERY_HINT,
    body_expect_centerline_strike,
    body_expect_label,
    body_expect_withdraw,
    body_prompt_centerline_strike,
    body_prompt_for_attack,
    body_prompt_withdraw,
)
from swing_tracker import withdraw_direction_after_strike

MotionKindExpect = str | None  # "linear", "thrust", or None (don't score kind)

GET_READY_PROMPT = (
    "Get into START position — saber behind your back, low at your hip, or tucked "
    "out of view. Arms relaxed. Hold still until the countdown ends."
)

REST_PROMPT = (
    "Stand relaxed. Saber behind your back, low at your hip, or at your side "
    "— blade not pointing at the camera."
)


@dataclass(frozen=True)
class SwingExercise:
    id: str
    title: str
    prompt: str
    expected_direction: str
    expected_kind: MotionKindExpect
    prep_sec: float = 5.0
    swing_max_sec: float = 3.0
    body_hint: str = ""
    ready_prompt: str = GET_READY_PROMPT
    rep_index: int = 0
    rep_total: int = 0
    # ``strike`` = cross-body attack; ``withdraw`` = retreat from centerline
    motion_role: str = "strike"
    end_at_centerline: bool = False
    follows_strike: str | None = None  # withdraw trials: which strike was blocked
    # Legacy continuous recording window (``--continuous`` only)
    duration_sec: float = 0.0


_SWING_SPECS: tuple[tuple[str, str, str, MotionKindExpect], ...] = (
    ("swing_left", "Cross-body LEFT (right arm)", "left", "linear"),
    ("swing_right", "Cross-body RIGHT (left arm)", "right", "linear"),
    ("swing_high", "Overhead HIGH", "high", "linear"),
    ("swing_center", "Thrust CENTER", "center", "thrust"),
)


def _single_swing_prompt(direction: str) -> str:
    """One swing only — recovery happens after, before the next trial."""
    base = body_prompt_for_attack(direction)
    # Drop the multi-rep recovery paragraph from the swing cue; GET READY covers reset.
    if SWING_RECOVERY_HINT in base:
        base = base.replace(SWING_RECOVERY_HINT, "").strip()
    return f"{base} Do ONE swing when prompted — finish and hold the end pose within 3 seconds."


def _discrete_session(*, per_direction: int, ready_sec: float, swing_max_sec: float) -> list[SwingExercise]:
    per_direction = max(1, per_direction)
    trials: list[SwingExercise] = []

    trials.append(
        SwingExercise(
            id="rest_start",
            title="Rest — saber hidden",
            prompt=REST_PROMPT,
            expected_direction="none",
            expected_kind=None,
            prep_sec=ready_sec,
            swing_max_sec=3.0,
            body_hint=body_expect_label("none"),
            ready_prompt=GET_READY_PROMPT,
        )
    )

    for swing_id, title, direction, kind in _SWING_SPECS:
        for rep in range(1, per_direction + 1):
            trials.append(
                SwingExercise(
                    id=f"{swing_id}_{rep}",
                    title=f"{title} ({rep}/{per_direction})",
                    prompt=_single_swing_prompt(direction),
                    expected_direction=direction,
                    expected_kind=kind,
                    prep_sec=ready_sec,
                    swing_max_sec=swing_max_sec,
                    body_hint=body_expect_label(direction),
                    ready_prompt=GET_READY_PROMPT,
                    rep_index=rep,
                    rep_total=per_direction,
                )
            )

        trials.append(
            SwingExercise(
                id=f"rest_after_{swing_id}",
                title="Rest — reset before next type",
                prompt=f"Stand still. {SWING_RECOVERY_HINT}",
                expected_direction="none",
                expected_kind=None,
                prep_sec=min(ready_sec, 2.0),
                swing_max_sec=min(swing_max_sec, 3.0),
                body_hint=body_expect_label("none"),
                ready_prompt=GET_READY_PROMPT,
            )
        )

    if trials and trials[-1].id.startswith("rest_after_"):
        trials[-1] = SwingExercise(
            id="rest_finish",
            title="Rest — finish",
            prompt="Relax — saber behind back or at hip, arms down.",
            expected_direction="none",
            expected_kind=None,
            prep_sec=min(ready_sec, 2.0),
            swing_max_sec=min(swing_max_sec, 3.0),
            body_hint=body_expect_label("none"),
            ready_prompt=GET_READY_PROMPT,
        )

    return trials


# Legacy continuous blocks (``--continuous``)
_CONTINUOUS_SIDE_REP = " Do 2–3 reps: strike → retract behind back/hip → pause → next."

_CONTINUOUS_EXERCISES: tuple[SwingExercise, ...] = (
    SwingExercise(
        id="rest_1",
        title="Rest — saber hidden",
        prompt=REST_PROMPT,
        expected_direction="none",
        expected_kind=None,
        duration_sec=4.0,
        prep_sec=2.0,
        body_hint=body_expect_label("none"),
    ),
    SwingExercise(
        id="swing_left",
        title="Cross-body LEFT (right arm)",
        prompt=body_prompt_for_attack("left") + _CONTINUOUS_SIDE_REP,
        expected_direction="left",
        expected_kind="linear",
        duration_sec=12.0,
        body_hint=body_expect_label("left"),
    ),
    SwingExercise(
        id="rest_2",
        title="Rest",
        prompt=f"Stand still. {SWING_RECOVERY_HINT}",
        expected_direction="none",
        expected_kind=None,
        duration_sec=3.0,
        prep_sec=1.0,
        body_hint=body_expect_label("none"),
    ),
    SwingExercise(
        id="swing_right",
        title="Cross-body RIGHT (left arm)",
        prompt=body_prompt_for_attack("right") + _CONTINUOUS_SIDE_REP,
        expected_direction="right",
        expected_kind="linear",
        duration_sec=12.0,
        body_hint=body_expect_label("right"),
    ),
    SwingExercise(
        id="rest_3",
        title="Rest",
        prompt=f"Stand still. {SWING_RECOVERY_HINT}",
        expected_direction="none",
        expected_kind=None,
        duration_sec=3.0,
        prep_sec=1.0,
        body_hint=body_expect_label("none"),
    ),
    SwingExercise(
        id="swing_high",
        title="Overhead HIGH",
        prompt=body_prompt_for_attack("high") + _CONTINUOUS_SIDE_REP,
        expected_direction="high",
        expected_kind="linear",
        duration_sec=10.0,
        body_hint=body_expect_label("high"),
    ),
    SwingExercise(
        id="rest_4",
        title="Rest",
        prompt=f"Stand still. {SWING_RECOVERY_HINT}",
        expected_direction="none",
        expected_kind=None,
        duration_sec=3.0,
        prep_sec=1.0,
        body_hint=body_expect_label("none"),
    ),
    SwingExercise(
        id="swing_center",
        title="Thrust CENTER",
        prompt=body_prompt_for_attack("center") + _CONTINUOUS_SIDE_REP,
        expected_direction="center",
        expected_kind="thrust",
        duration_sec=10.0,
        body_hint=body_expect_label("center"),
    ),
    SwingExercise(
        id="rest_5",
        title="Rest — finish",
        prompt="Relax — saber behind back or at hip, arms down.",
        expected_direction="none",
        expected_kind=None,
        duration_sec=3.0,
        prep_sec=1.0,
        body_hint=body_expect_label("none"),
    ),
)


def _centerline_discrete_session(
    *, per_direction: int, ready_sec: float, swing_max_sec: float
) -> list[SwingExercise]:
    """L/R strikes blocked at centerline + paired withdraw trials."""
    per_direction = max(1, per_direction)
    trials: list[SwingExercise] = []

    trials.append(
        SwingExercise(
            id="rest_start",
            title="Rest — saber hidden",
            prompt=REST_PROMPT,
            expected_direction="none",
            expected_kind=None,
            prep_sec=ready_sec,
            swing_max_sec=3.0,
            body_hint=body_expect_label("none"),
            ready_prompt=CENTERLINE_REST_READY,
        )
    )

    for strike_dir, title_strike in (("left", "LEFT blocked at center"), ("right", "RIGHT blocked at center")):
        withdraw_dir = withdraw_direction_after_strike(strike_dir)
        for rep in range(1, per_direction + 1):
            trials.append(
                SwingExercise(
                    id=f"strike_{strike_dir}_centerline_{rep}",
                    title=f"{title_strike} ({rep}/{per_direction})",
                    prompt=body_prompt_centerline_strike(strike_dir),
                    expected_direction=strike_dir,
                    expected_kind="linear",
                    prep_sec=ready_sec,
                    swing_max_sec=swing_max_sec,
                    body_hint=body_expect_centerline_strike(strike_dir),
                    ready_prompt=CENTERLINE_REST_READY,
                    rep_index=rep,
                    rep_total=per_direction,
                    motion_role="strike",
                    end_at_centerline=True,
                )
            )
            trials.append(
                SwingExercise(
                    id=f"withdraw_{withdraw_dir}_after_{strike_dir}_{rep}",
                    title=f"Withdraw YOUR {withdraw_dir.upper()} after {strike_dir.upper()} ({rep}/{per_direction})",
                    prompt=body_prompt_withdraw(withdraw_dir, after_strike=strike_dir),
                    expected_direction=withdraw_dir,
                    expected_kind="linear",
                    prep_sec=ready_sec,
                    swing_max_sec=swing_max_sec,
                    body_hint=body_expect_withdraw(withdraw_dir, after_strike=strike_dir),
                    ready_prompt=CENTERLINE_GET_READY,
                    rep_index=rep,
                    rep_total=per_direction,
                    motion_role="withdraw",
                    follows_strike=strike_dir,
                )
            )

        trials.append(
            SwingExercise(
                id=f"rest_after_{strike_dir}_centerline",
                title="Rest — reset before next type",
                prompt=f"Stand still. {SWING_RECOVERY_HINT}",
                expected_direction="none",
                expected_kind=None,
                prep_sec=min(ready_sec, 2.0),
                swing_max_sec=min(swing_max_sec, 3.0),
                body_hint=body_expect_label("none"),
                ready_prompt=CENTERLINE_REST_READY,
            )
        )

    if trials and trials[-1].id.startswith("rest_after_"):
        trials[-1] = SwingExercise(
            id="rest_finish",
            title="Rest — finish",
            prompt="Relax — saber behind back or at hip, arms down.",
            expected_direction="none",
            expected_kind=None,
            prep_sec=min(ready_sec, 2.0),
            swing_max_sec=min(swing_max_sec, 3.0),
            body_hint=body_expect_label("none"),
            ready_prompt=CENTERLINE_REST_READY,
        )

    return trials


def session_for(
    *,
    quick: bool = False,
    continuous: bool = False,
    centerline: bool = False,
    per_direction: int = 3,
    ready_sec: float = 5.0,
    swing_max_sec: float = 3.0,
) -> list[SwingExercise]:
    """Return exercise list for a guided eval session."""
    if centerline:
        reps = 2 if quick else max(1, min(3, per_direction))
        return _centerline_discrete_session(
            per_direction=reps,
            ready_sec=ready_sec,
            swing_max_sec=swing_max_sec,
        )

    if continuous:
        if not quick:
            return list(_CONTINUOUS_EXERCISES)
        out: list[SwingExercise] = []
        for ex in _CONTINUOUS_EXERCISES:
            dur = ex.duration_sec
            if ex.expected_direction != "none":
                dur = min(dur, 7.0)
            elif ex.id.startswith("rest"):
                dur = min(dur, 2.0)
            out.append(
                SwingExercise(
                    id=ex.id,
                    title=ex.title,
                    prompt=ex.prompt,
                    expected_direction=ex.expected_direction,
                    expected_kind=ex.expected_kind,
                    duration_sec=dur,
                    prep_sec=min(ex.prep_sec, 1.5),
                    body_hint=ex.body_hint,
                )
            )
        return out

    reps = 2 if quick else max(2, min(3, per_direction))
    return _discrete_session(
        per_direction=reps,
        ready_sec=ready_sec,
        swing_max_sec=swing_max_sec,
    )


def session_summary(exercises: list[SwingExercise]) -> str:
    swing_n = sum(1 for e in exercises if e.expected_direction != "none")
    rest_n = len(exercises) - swing_n
    if exercises and any(e.end_at_centerline for e in exercises):
        strike_n = sum(1 for e in exercises if e.motion_role == "strike")
        withdraw_n = sum(1 for e in exercises if e.motion_role == "withdraw")
        total_sec = sum(e.prep_sec + e.swing_max_sec + 1.5 for e in exercises)
        return (
            f"{len(exercises)} centerline trials ({strike_n} strikes, {withdraw_n} withdraws, "
            f"{rest_n} rest) ~{total_sec:.0f}s — SPACE between trials"
        )
    if exercises and exercises[0].duration_sec > 0:
        total_sec = sum(e.prep_sec + e.duration_sec for e in exercises)
        return f"{len(exercises)} trials ({swing_n} swings, {rest_n} rest) ~{total_sec:.0f}s continuous"
    total_sec = sum(e.prep_sec + e.swing_max_sec + 1.5 for e in exercises)
    return (
        f"{len(exercises)} discrete trials ({swing_n} single swings, {rest_n} rest) "
        f"~{total_sec:.0f}s — one swing per countdown"
    )
