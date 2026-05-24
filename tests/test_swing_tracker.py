"""Temporal swing phase tests — synthetic landmark paths."""

import unittest

import config
from swing_tracker import MotionSample, SwingTracker, build_motion_sample, sample_from_landmarks
from saber_detector import SaberLine


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
        track_x=grip_x,
        track_y=grip_y,
        tip_x=grip_x,
        tip_y=grip_y,
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
        # Wind-up + travel toward YOUR LEFT (right wrist leads; +image-x on true cam)
        for i, rw in enumerate(
            [0.50, 0.54, 0.58, 0.62, 0.66, 0.70, 0.73, 0.75], start=1
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

    def test_overhead_downward_chop_stays_high(self):
        """After peak, downward chop should still read as high (motion, not static pose)."""
        tracker = SwingTracker()
        tracker.update(
            _sample(0.0, grip_y=0.55, lw_y=0.55, rw_y=0.55, extension=0.15)
        )
        t = 0.0
        for i in range(1, 8):
            t = i * 0.05
            gy = 0.55 - i * 0.04
            tracker.update(
                _sample(
                    t,
                    grip_y=gy,
                    lw_y=gy,
                    rw_y=gy,
                    lw_x=0.42,
                    rw_x=0.58,
                    extension=0.2,
                )
            )
        chop_dirs: list[str] = []
        for i in range(1, 7):
            t += 0.05
            gy = 0.27 + i * 0.03
            state = tracker.update(
                _sample(
                    t,
                    grip_y=gy,
                    lw_y=gy,
                    rw_y=gy,
                    lw_x=0.42,
                    rw_x=0.58,
                    extension=0.22,
                )
            )
            chop_dirs.append(state.direction)

        self.assertIn("high", chop_dirs)
        self.assertGreater(chop_dirs.count("high"), len(chop_dirs) // 2)

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

    def test_begin_phase_visible_on_motion_start(self):
        tracker = SwingTracker()
        tracker.update(_sample(0.0, grip_x=0.52, lw_x=0.52, rw_x=0.52, extension=0.12))
        phases: list[str] = []
        for i in range(1, 6):
            gx = 0.52 - i * 0.015
            state = tracker.update(
                _sample(
                    i * 0.05,
                    grip_x=gx,
                    lw_x=gx,
                    rw_x=gx,
                    extension=0.15 + i * 0.01,
                    right_reach=0.15 + i * 0.01,
                    left_reach=0.15 + i * 0.01,
                )
            )
            phases.append(state.phase)
        self.assertIn("begin", phases)

    def test_velocity_direction_left(self):
        from swing_tracker import direction_from_velocity

        self.assertEqual(direction_from_velocity(0.5, 0.0, 0.4, "linear"), "left")

    def test_velocity_direction_right_off_hand_diagonal(self):
        """Off-hand right strike: lateral wins over vertical at lower speed."""
        from swing_tracker import direction_from_velocity

        # vy dominates numerically but −vx is meaningful (typical left-arm arc)
        self.assertEqual(direction_from_velocity(-0.35, -0.55, 0.16, "linear"), "right")
        self.assertEqual(direction_from_velocity(-0.35, -0.55, 0.12, "linear"), "none")

    def test_velocity_direction_left_withdraw_diagonal(self):
        from swing_tracker import direction_from_velocity

        self.assertEqual(direction_from_velocity(0.40, -0.50, 0.22, "linear"), "left")

    def test_saber_track_point_inset_from_tip(self):
        from swing_tracker import saber_track_point

        # grip (0.5,0.5) tip (0.8,0.5) forearm 0.1 → track at 0.7,0.5
        tx, ty = saber_track_point(0.5, 0.5, 0.8, 0.5, 0.1, mode="inset_tip")
        self.assertAlmostEqual(tx, 0.7)
        self.assertAlmostEqual(ty, 0.5)

    def test_saber_track_point_forearm_from_grip(self):
        from swing_tracker import saber_track_point

        tx, ty = saber_track_point(0.5, 0.5, 0.8, 0.5, 0.1, mode="forearm")
        self.assertAlmostEqual(tx, 0.6)
        self.assertAlmostEqual(ty, 0.5)

    def test_latched_forearm_not_recomputed(self):
        from swing_tracker import build_motion_sample, saber_track_point
        from saber_detector import SaberLine

        class FakeLandmark:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        landmarks = [None] * 17
        landmarks[11] = FakeLandmark(0.45, 0.35)
        landmarks[12] = FakeLandmark(0.55, 0.35)
        landmarks[15] = FakeLandmark(0.48, 0.45)
        landmarks[16] = FakeLandmark(0.52, 0.45)

        tracker = SwingTracker()
        saber = SaberLine(
            grip_x=320, grip_y=240, tip_x=480, tip_y=240,
            hand="right", orientation="horizontal", confidence=0.9,
        )
        s1 = build_motion_sample(landmarks, 0.0, saber, 640, 480, fuse_saber=True)
        assert s1 is not None
        tracker.update(s1)
        latch1 = tracker.latched_forearm_norm
        self.assertIsNotNone(latch1)

        saber2 = SaberLine(
            grip_x=320, grip_y=240, tip_x=520, tip_y=240,
            hand="right", orientation="horizontal", confidence=0.9,
        )
        s2 = build_motion_sample(landmarks, 0.04, saber2, 640, 480, fuse_saber=True)
        tracker.update(s2)
        self.assertEqual(tracker.latched_forearm_norm, latch1)

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

    def test_centerline_blocked_left_end_pose(self):
        from swing_tracker import _end_pose_direction, side_strike_blocked_at_center

        sample = _sample(
            1.0,
            rw_x=0.51,
            lw_x=0.49,
            extension=0.22,
            right_reach=0.22,
            left_reach=0.18,
            center_x=0.5,
        )
        self.assertTrue(side_strike_blocked_at_center(sample, "left"))
        self.assertEqual(_end_pose_direction(sample), "left")

    def test_centerline_blocked_right_end_pose(self):
        from swing_tracker import _end_pose_direction, side_strike_blocked_at_center

        sample = _sample(
            1.0,
            lw_x=0.49,
            rw_x=0.52,
            extension=0.22,
            left_reach=0.22,
            right_reach=0.18,
            center_x=0.5,
        )
        self.assertTrue(side_strike_blocked_at_center(sample, "right"))
        self.assertEqual(_end_pose_direction(sample), "right")

    def test_withdraw_direction_mapping(self):
        from swing_tracker import withdraw_direction_after_strike

        self.assertEqual(withdraw_direction_after_strike("left"), "right")
        self.assertEqual(withdraw_direction_after_strike("right"), "left")

    def test_strike_from_start_side(self):
        from swing_tracker import strike_from_start_side

        origin = _sample(0.0, grip_x=0.38, rw_x=0.38, lw_x=0.40, center_x=0.5)
        self.assertEqual(strike_from_start_side(origin, origin), "left")
        origin_r = _sample(0.0, grip_x=0.62, rw_x=0.62, lw_x=0.60, center_x=0.5)
        self.assertEqual(strike_from_start_side(origin_r, origin_r), "right")

    def test_direction_latched_through_centerline_stop(self):
        """Travel direction from start+velocity must persist at centerline stop."""
        tracker = SwingTracker()
        tracker.update(
            _sample(0.0, grip_x=0.38, rw_x=0.38, extension=0.12, right_reach=0.12)
        )
        for i in range(1, 8):
            gx = 0.38 + i * 0.04
            state = tracker.update(
                _sample(
                    i * 0.04,
                    grip_x=gx,
                    rw_x=gx,
                    extension=0.15 + i * 0.02,
                    right_reach=0.15 + i * 0.02,
                )
            )
        self.assertIn(state.direction, ("left", "none"))
        # Blocked at centerline — should not flip to none/other from END pose
        blocked = tracker.update(
            _sample(
                0.5,
                grip_x=0.51,
                rw_x=0.51,
                lw_x=0.49,
                extension=0.22,
                right_reach=0.22,
                left_reach=0.18,
                center_x=0.5,
            )
        )
        self.assertEqual(blocked.direction, "left")

    def test_saber_fusion_tracks_tip_motion(self):
        """Fused saber tip should drive left swing when wrist barely moves."""
        class FakeLandmark:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        landmarks = [None] * 17
        landmarks[11] = FakeLandmark(0.45, 0.35)
        landmarks[12] = FakeLandmark(0.55, 0.35)
        landmarks[15] = FakeLandmark(0.50, 0.45)
        landmarks[16] = FakeLandmark(0.50, 0.45)

        tracker = SwingTracker()
        tracker.update(sample_from_landmarks(landmarks, 0.0))
        directions: list[str] = []
        for i, tip_x in enumerate([240, 300, 360, 420, 480], start=1):
            saber = SaberLine(
                grip_x=500,
                grip_y=300,
                tip_x=tip_x,
                tip_y=300,
                hand="right",
                orientation="horizontal",
                confidence=0.9,
            )
            sample = build_motion_sample(
                landmarks, i * 0.04, saber, 640, 480, fuse_saber=True
            )
            assert sample is not None and sample.uses_saber
            state = tracker.update(sample)
            directions.append(state.direction)

        self.assertIn("left", directions)


if __name__ == "__main__":
    unittest.main()
