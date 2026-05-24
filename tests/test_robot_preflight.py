"""Tests for robot_preflight helpers (no hardware)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from robot_preflight import _joints_deg_from_feedback


class TestRobotPreflight(unittest.TestCase):
    def test_joints_deg_from_feedback(self):
        js = SimpleNamespace(
            joint_1=1000,
            joint_2=-2500,
            joint_3=0,
            joint_4=45000,
            joint_5=-12000,
            joint_6=500,
        )
        msg = SimpleNamespace(joint_state=js)
        self.assertEqual(_joints_deg_from_feedback(msg), [1.0, -2.5, 0.0, 45.0, -12.0, 0.5])


if __name__ == "__main__":
    unittest.main()
