"""Session plan tests for discrete swing eval."""

import unittest

from swing_eval_plan import session_for, session_summary


class TestSwingEvalPlan(unittest.TestCase):
    def test_discrete_default_three_per_direction(self):
        exercises = session_for()
        swing_ids = [e.id for e in exercises if e.expected_direction != "none"]
        self.assertEqual(len(swing_ids), 12)
        self.assertEqual(swing_ids.count("swing_left_1"), 1)
        self.assertEqual(swing_ids.count("swing_left_3"), 1)
        self.assertTrue(all(e.duration_sec == 0 for e in exercises))
        self.assertIn("one swing per countdown", session_summary(exercises))

    def test_discrete_quick_two_per_direction(self):
        exercises = session_for(quick=True)
        swing_ids = [e.id for e in exercises if e.expected_direction != "none"]
        self.assertEqual(len(swing_ids), 8)
        self.assertNotIn("swing_left_3", swing_ids)

    def test_continuous_legacy(self):
        exercises = session_for(continuous=True)
        self.assertEqual(len(exercises), 9)
        self.assertGreater(exercises[1].duration_sec, 0)

    def test_centerline_session_pairs_strike_and_withdraw(self):
        exercises = session_for(centerline=True, quick=True)
        ids = [e.id for e in exercises]
        self.assertIn("strike_left_centerline_1", ids)
        self.assertIn("withdraw_right_after_left_1", ids)
        self.assertIn("strike_right_centerline_1", ids)
        self.assertIn("withdraw_left_after_right_1", ids)
        strike_left_idx = ids.index("strike_left_centerline_1")
        withdraw_idx = ids.index("withdraw_right_after_left_1")
        self.assertEqual(withdraw_idx, strike_left_idx + 1)
        self.assertTrue(exercises[strike_left_idx].end_at_centerline)
        self.assertEqual(exercises[withdraw_idx].motion_role, "withdraw")
        self.assertEqual(exercises[withdraw_idx].follows_strike, "left")
        self.assertIn("centerline", session_summary(exercises).lower())


if __name__ == "__main__":
    unittest.main()
