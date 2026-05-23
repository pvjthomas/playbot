"""Developer 2 — movement safety gate."""

import time

import config


class SafetyGuard:
    """DRY_RUN, cooldown, and emergency stop."""

    def __init__(
        self,
        dry_run: bool | None = None,
        cooldown_sec: float | None = None,
    ):
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self.cooldown_sec = (
            config.MOVEMENT_COOLDOWN_SEC if cooldown_sec is None else cooldown_sec
        )
        self._last_move_at = 0.0
        self._emergency_stop = False

    @property
    def emergency_stop_active(self) -> bool:
        return self._emergency_stop

    def trigger_emergency_stop(self):
        self._emergency_stop = True
        print("[safety] EMERGENCY STOP — all motion blocked")

    def clear_emergency_stop(self):
        self._emergency_stop = False
        print("[safety] emergency stop cleared")

    def may_move(self) -> bool:
        if self._emergency_stop:
            return False
        return (time.monotonic() - self._last_move_at) >= self.cooldown_sec

    def record_move(self):
        self._last_move_at = time.monotonic()

    def hardware_enabled(self) -> bool:
        return not self.dry_run and not self._emergency_stop
