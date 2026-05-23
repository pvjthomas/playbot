"""Contract tests — run: python -m unittest tests.test_contracts"""

import unittest

from contracts import (
    ATTACK_TO_POSE,
    AttackDirection,
    RobotPose,
    pose_for_attack,
)
from dashboard import ConsoleDashboard
from robot import PiperRobot
from safety import SafetyGuard
from sounds import SoundEngine
from vision import AttackVision


class TestContracts(unittest.TestCase):
    def test_attack_directions_are_strings(self):
        for key in ATTACK_TO_POSE:
            self.assertIn(key, ("left", "right", "high", "low", "center", "none"))

    def test_pose_for_attack_mapping(self):
        self.assertEqual(pose_for_attack("left"), "BLOCK_LEFT")
        self.assertEqual(pose_for_attack("right"), "BLOCK_RIGHT")
        self.assertEqual(pose_for_attack("high"), "BLOCK_HIGH")
        self.assertIsNone(pose_for_attack("none"))

    def test_robot_implements_controller(self):
        robot = PiperRobot(safety=SafetyGuard(dry_run=True))
        robot.connect()
        robot.respond_to_attack("left")
        robot.move_to_pose("HOME")
        robot.emergency_stop()
        robot.disconnect()
        self.assertEqual(robot.current_pose, "HOME")

    def test_vision_fake_mode(self):
        import config

        old = config.USE_FAKE_ATTACKS
        config.USE_FAKE_ATTACKS = True
        try:
            v = AttackVision()
            direction = v.detect_attack(None)
            self.assertIn(direction, ATTACK_TO_POSE.keys())
            v.close()
        finally:
            config.USE_FAKE_ATTACKS = old

    def test_optional_hooks_exist(self):
        sounds = SoundEngine()
        sounds.play_for_attack("none")
        sounds.shutdown()
        dash = ConsoleDashboard()
        dash.update("none", "HOME", 30.0)
        dash.shutdown()


if __name__ == "__main__":
    unittest.main()
