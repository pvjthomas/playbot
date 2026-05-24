"""
Shared types and protocols — all teams integrate through this file only.

Do not import across team boundaries (vision ↔ robot ↔ app) except via contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

# --- Shared types ---
#
# Attack direction semantics (image frame, not body left/right): see directions.py

AttackDirection = Literal["left", "right", "high", "low", "center", "none"]

SwingPhase = Literal["idle", "begin", "mid", "end"]
MotionKind = Literal["none", "linear", "thrust"]


@dataclass(frozen=True)
class SwingState:
    direction: AttackDirection
    phase: SwingPhase
    kind: MotionKind

RobotPose = Literal[
    "HOME",
    "GUARD_CENTER",
    "BLOCK_LEFT",
    "BLOCK_RIGHT",
    "BLOCK_HIGH",
    "BLOCK_LOW",
    "DODGE_BACK",
    "COUNTER_TAP",
    "RESET",
]

Frame = Any  # OpenCV BGR numpy array

# --- Attack → pose mapping (owned by contracts; tune with team agreement) ---

ATTACK_TO_POSE: dict[AttackDirection, RobotPose | None] = {
    "left": "BLOCK_LEFT",
    "right": "BLOCK_RIGHT",
    "high": "BLOCK_HIGH",
    "low": "BLOCK_LOW",
    "center": "GUARD_CENTER",
    "none": None,
}


def pose_for_attack(direction: AttackDirection) -> RobotPose | None:
    """Return the robot pose for an attack direction, or None if no response."""
    return ATTACK_TO_POSE.get(direction)


# --- Protocols (interface contracts) ---


@runtime_checkable
class AttackDetector(Protocol):
    def detect_attack(self, frame: Frame) -> AttackDirection: ...

    def detect_swing(self, frame: Frame) -> SwingState: ...


@runtime_checkable
class RobotController(Protocol):
    def respond_to_attack(self, direction: AttackDirection) -> None: ...
    def move_to_pose(self, name: RobotPose) -> None: ...
    def emergency_stop(self) -> None: ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...


@runtime_checkable
class OverlayRenderer(Protocol):
    def render(self, frame: Frame, direction: AttackDirection, **kwargs) -> Frame: ...


@runtime_checkable
class SoundPlayer(Protocol):
    def play_for_attack(self, direction: AttackDirection) -> None: ...
    def shutdown(self) -> None: ...


@runtime_checkable
class Dashboard(Protocol):
    def update(self, direction: AttackDirection, pose: RobotPose | None, fps: float) -> None: ...
    def shutdown(self) -> None: ...
