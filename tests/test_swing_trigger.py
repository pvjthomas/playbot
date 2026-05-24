"""Tests for temporal swing trigger logic (main.py integration)."""

import unittest

from contracts import SwingState
from swing_trigger import compute_swing_trigger, display_direction


class TestSwingTrigger(unittest.TestCase):
    def test_display_direction_idle(self):
        swing = SwingState(direction="left", phase="idle", kind="none")
        self.assertEqual(display_direction(swing), "none")

    def test_display_direction_active(self):
        swing = SwingState(direction="left", phase="mid", kind="linear")
        self.assertEqual(display_direction(swing), "left")

    def test_fire_on_begin_mid_end_once_each(self):
        last = None
        for phase in ("begin", "mid", "end"):
            swing = SwingState(direction="left", phase=phase, kind="linear")
            should, last, direction = compute_swing_trigger(swing, last)
            self.assertTrue(should, phase)
            self.assertEqual(direction, "left")
            should_repeat, last, _ = compute_swing_trigger(swing, last)
            self.assertFalse(should_repeat)

    def test_skip_begin_when_disabled(self):
        swing = SwingState(direction="right", phase="begin", kind="linear")
        should, last, direction = compute_swing_trigger(
            swing, None, respond_on_begin=False
        )
        self.assertFalse(should)
        self.assertIsNone(direction)

        mid = SwingState(direction="right", phase="mid", kind="linear")
        should, last, direction = compute_swing_trigger(mid, last, respond_on_begin=False)
        self.assertTrue(should)
        self.assertEqual(direction, "right")

    def test_idle_resets_last_key(self):
        swing = SwingState(direction="left", phase="mid", kind="linear")
        _, last, _ = compute_swing_trigger(swing, None)
        idle = SwingState(direction="none", phase="idle", kind="none")
        should, last, direction = compute_swing_trigger(idle, last)
        self.assertFalse(should)
        self.assertIsNone(last)
        self.assertIsNone(direction)

        swing2 = SwingState(direction="left", phase="begin", kind="linear")
        should, _, direction = compute_swing_trigger(swing2, last)
        self.assertTrue(should)
        self.assertEqual(direction, "left")

    def test_no_fire_without_direction(self):
        swing = SwingState(direction="none", phase="mid", kind="linear")
        should, last, direction = compute_swing_trigger(swing, None)
        self.assertFalse(should)
        self.assertIsNone(last)
        self.assertIsNone(direction)


if __name__ == "__main__":
    unittest.main()
