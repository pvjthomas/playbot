"""Developer 3 — status dashboard hook (optional stub)."""

import config
from contracts import AttackDirection, Dashboard, RobotPose


class ConsoleDashboard:
    """Implements Dashboard — prints status; extend to pygame UI later."""

    def __init__(self):
        self._enabled = config.ENABLE_DASHBOARD
        self._last_direction: AttackDirection = "none"

    def update(
        self,
        direction: AttackDirection,
        pose: RobotPose | None,
        fps: float,
    ):
        if not self._enabled:
            return
        if direction != self._last_direction:
            print(f"[dashboard] attack={direction} pose={pose} fps={fps:.0f}")
            self._last_direction = direction

    def shutdown(self):
        pass
