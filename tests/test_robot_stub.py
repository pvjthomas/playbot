"""Milestone 1 — DRY_RUN robot stub (no hardware)."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import config
from contracts import ATTACK_TO_POSE, pose_for_attack
from poses import JOINT_POSES
from robot import PiperRobot
from safety import SafetyGuard


class TestRobotStub(unittest.TestCase):
    def setUp(self):
        self.robot = PiperRobot(safety=SafetyGuard(dry_run=True))

    def test_dry_run_default_from_config(self):
        self.assertTrue(config.DRY_RUN)
        self.assertTrue(self.robot.safety.dry_run)

    def test_connect_moves_home_in_dry_run(self):
        with redirect_stdout(io.StringIO()) as out:
            self.robot.connect()
        self.assertIn("[robot] DRY_RUN → HOME:", out.getvalue())
        self.assertEqual(self.robot.current_pose, "HOME")

    def test_move_to_pose_all_defined_poses(self):
        self.robot.connect()
        for name in JOINT_POSES:
            with self.subTest(pose=name):
                with redirect_stdout(io.StringIO()) as out:
                    self.robot.move_to_pose(name)
                self.assertIn(f"[robot] DRY_RUN → {name}:", out.getvalue())
                self.assertEqual(self.robot.current_pose, name)

    def test_respond_to_attack_maps_all_attack_directions(self):
        for direction, expected in ATTACK_TO_POSE.items():
            if expected is None:
                continue
            with self.subTest(direction=direction):
                robot = PiperRobot(safety=SafetyGuard(dry_run=True, cooldown_sec=0))
                robot.connect()
                self.assertEqual(pose_for_attack(direction), expected)
                with redirect_stdout(io.StringIO()) as out:
                    robot.respond_to_attack(direction)
                text = out.getvalue()
                self.assertIn(f"[robot] DRY_RUN → {expected}:", text)
                self.assertEqual(robot.current_pose, expected)

    def test_respond_to_attack_none_is_no_op(self):
        self.robot.connect()
        with redirect_stdout(io.StringIO()) as out:
            self.robot.respond_to_attack("none")
        self.assertEqual(out.getvalue(), "")

    def test_emergency_stop_blocks_respond_and_move(self):
        self.robot.connect()
        self.robot.emergency_stop()
        with redirect_stdout(io.StringIO()) as out:
            self.robot.respond_to_attack("left")
            self.robot.move_to_pose("BLOCK_RIGHT")
        text = out.getvalue()
        self.assertIn("blocked (left → BLOCK_LEFT)", text)
        self.assertIn("blocked (move → BLOCK_RIGHT)", text)
        self.assertEqual(self.robot.current_pose, "HOME")

    def test_cooldown_blocks_rapid_respond_to_attack(self):
        guard = SafetyGuard(dry_run=True, cooldown_sec=10.0)
        robot = PiperRobot(safety=guard)
        robot.connect()
        with redirect_stdout(io.StringIO()) as out:
            robot.respond_to_attack("left")
            robot.respond_to_attack("right")
        text = out.getvalue()
        self.assertEqual(text.count("[robot] DRY_RUN →"), 1)
        self.assertIn("blocked (right → BLOCK_RIGHT)", text)

    def test_cooldown_allows_move_after_elapsed(self):
        guard = SafetyGuard(dry_run=True, cooldown_sec=0.05)
        robot = PiperRobot(safety=guard)
        robot.connect()
        with patch("safety.time.monotonic", side_effect=[100.0, 100.0, 100.06, 100.06]):
            with redirect_stdout(io.StringIO()) as out:
                robot.respond_to_attack("left")
                robot.respond_to_attack("right")
        text = out.getvalue()
        self.assertEqual(text.count("[robot] DRY_RUN →"), 2)


if __name__ == "__main__":
    unittest.main()
