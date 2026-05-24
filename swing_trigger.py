"""Temporal swing → robot trigger logic for main.py."""

from __future__ import annotations

from contracts import AttackDirection, SwingPhase, SwingState

SwingTriggerKey = tuple[AttackDirection, SwingPhase] | None

DEFAULT_RESPOND_PHASES: frozenset[SwingPhase] = frozenset({"begin", "mid", "end"})


def display_direction(swing: SwingState) -> AttackDirection:
    """HUD label: active swing direction, else none."""
    if swing.phase == "idle" or swing.direction == "none":
        return "none"
    return swing.direction


def compute_swing_trigger(
    swing: SwingState,
    last_key: SwingTriggerKey,
    *,
    respond_on_begin: bool = True,
    respond_phases: frozenset[SwingPhase] = DEFAULT_RESPOND_PHASES,
) -> tuple[bool, SwingTriggerKey, AttackDirection | None]:
    """
    Decide whether main should call respond_to_attack for this swing frame.

    Returns (should_respond, new_last_key, direction).
    Resets last_key when the swing returns idle.
    """
    if swing.phase == "idle" or swing.direction == "none":
        return False, None, None

    phases = set(respond_phases)
    if not respond_on_begin:
        phases.discard("begin")

    if swing.phase not in phases:
        return False, last_key, None

    key: SwingTriggerKey = (swing.direction, swing.phase)
    if key == last_key:
        return False, last_key, None

    return True, key, swing.direction
