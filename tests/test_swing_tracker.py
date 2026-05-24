"""Temporal swing phase tests — synthetic landmark paths."""

import unittest

import config
from swing_tracker import MotionSample, SwingTracker


def _sample(
    t: float,
    *,
    grip_x: float = 0.5,
    grip_y: float = 0.45,
    lw_x: float = 0.52,
    lw_y: float = 0.45,
    rw_x: float = 0.48,
    rw_y: float = 0.45,
    extension: float = 0.2,
    center_x: float = 0.5,
    shoulder_y: float = 0.35,
    left_reach: float = 0.2,
    right_reach: float = 0.2,
) -> MotionSample:
    return MotionSample(
        t=t,
        grip_x=grip_x,
        grip_y=grip_y,
        lw_x=lw_x,
        lw_y=lw_y,
        rw_x=rw_x,
        rw_y=rw_y,
        extension=extension,
        center_x=center_x,
        shoulder_y=shoulder_y,
        left_reach=left_reach,
        right_reach=right_reach,
        midline_band=config.SIDE_MARGIN * 0.4,
    )


class TestSwingTracker(unittest.TestCase):
    def test_at_rest_stays_idle(self):
        tracker = SwingTracker()
        for i in range(20):
            state = tracker.update(_sample(i * 0.033, extension=0.12))
        self.assertEqual(state.phase, "idle")
        self.assertEqual(state.kind, "none")
        self.assertEqual(state.direction, "none")

    def test_linear_left_swing_phases(self):
        tracker = SwingTracker()
        phases: list[str] = []
        directions: list[str] = []

        # Rest
        tracker.update(_sample(0.0, rw_x=0.52, extension=0.12, right_reach=0.12))
        # Wind-up + travel toward image left (right wrist leads)
        for i, rw in enumerate(
            [0.50, 0.46, 0.42, 0.38, 0.34, 0.30, 0.27, 0.25], start=1
        ):
            ext = 0.15 + i * 0.02
            state = tracker.update(
                _sample(
                    i * 0.04,
                    grip_x=rw,
                    rw_x=rw,
                    extension=ext,
                    right_reach=ext,
                )
            )
            phases.append(state.phase)
            directions.append(state.direction)

        self.assertIn("mid", phases)
        self.assertIn("left", directions)

    def test_overhead_high_direction(self):
        tracker = SwingTracker()
        phases: list[str] = []
        t = 0.0
        tracker.update(_sample(t, grip_y=0.55, lw_y=0.55, rw_y=0.55, extension=0.15))
        for i in range(1, 10):
            t = i * 0.05
            gy = 0.55 - i * 0.03
            state = tracker.update(
                _sample(
                    t,
                    grip_y=gy,
                    lw_y=gy,
                    rw_y=gy,
                    lw_x=0.42,
                    rw_x=0.58,
                    extension=0.18 + i * 0.01,
                    left_reach=0.2,
                    right_reach=0.2,
                )
            )
            phases.append(state.phase)

        self.assertTrue(any(p in ("begin", "mid") for p in phases))
        end = tracker.update(
            _sample(
                t + 0.05,
                grip_y=0.22,
                lw_y=0.22,
                rw_y=0.22,
                lw_x=0.42,
                rw_x=0.58,
                extension=0.28,
                left_reach=0.28,
                right_reach=0.28,
            )
        )
        self.assertEqual(end.direction, "high")

    def test_thrust_center(self):
        tracker = SwingTracker()
        tracker.update(
            _sample(
                0.0,
                grip_x=0.5,
                lw_x=0.49,
                rw_x=0.51,
                extension=0.14,
                left_reach=0.14,
                right_reach=0.14,
            )
        )
        kinds: list[str] = []
        directions: list[str] = []
        for i in range(1, 12):
            ext = 0.14 + i * 0.015
            state = tracker.update(
                _sample(
                    i * 0.04,
                    grip_x=0.5,
                    lw_x=0.49,
                    rw_x=0.51,
                    extension=ext,
                    left_reach=ext,
                    right_reach=ext,
                )
            )
            kinds.append(state.kind)
            directions.append(state.direction)

        self.assertIn("thrust", kinds)
        self.assertIn("center", directions)

    def test_session_resets_to_idle(self):
        tracker = SwingTracker()
        for i in range(8):
            tracker.update(
                _sample(i * 0.04, rw_x=0.5 - i * 0.04, extension=0.15 + i * 0.02)
            )
        for i in range(12):
            state = tracker.update(
                _sample(0.5 + i * 0.04, rw_x=0.5, extension=0.12, right_reach=0.12)
            )
        self.assertEqual(state.phase, "idle")


if __name__ == "__main__":
    unittest.main()
