"""Developer 3 — pygame sound hooks (optional stub)."""

import config
from contracts import AttackDirection, SoundPlayer


class SoundEngine:
    """Implements SoundPlayer. Set ENABLE_SOUNDS=True to init pygame."""

    def __init__(self):
        self._ready = False
        if config.ENABLE_SOUNDS:
            self._init_pygame()

    def _init_pygame(self):
        try:
            import pygame

            pygame.mixer.init()
            self._ready = True
            print("[sounds] pygame mixer ready")
        except Exception as exc:
            print(f"[sounds] disabled: {exc}")

    def play_for_attack(self, direction: AttackDirection):
        if not self._ready or direction == "none":
            return
        print(f"[sounds] stub play: {direction}")

    def shutdown(self):
        if self._ready:
            import pygame

            pygame.mixer.quit()
