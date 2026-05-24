"""Unit tests for swing eval scoring."""

import json
import tempfile
import unittest
from pathlib import Path

from analyze_swing_eval import analyze_log_file
from swing_eval_scoring import score_session, score_trial


def _frame(
    *,
    attack="none",
    swing_direction="none",
    swing_phase="idle",
    swing_kind="none",
    tracked=True,
):
    return {
        "attack": attack,
        "swing_direction": swing_direction,
        "swing_phase": swing_phase,
        "swing_kind": swing_kind,
        "tracked": tracked,
    }


class TestSwingEvalScoring(unittest.TestCase):
    def test_rest_trial_idle_and_false_positives(self):
        trial = {
            "exercise_id": "rest_1",
            "title": "Rest",
            "expected_direction": "none",
            "frames": [
                _frame(),
                _frame(),
                _frame(swing_direction="left", swing_phase="mid"),
            ],
        }
        s = score_trial(trial)
        self.assertAlmostEqual(s.idle_fraction, 2 / 3)
        self.assertAlmostEqual(s.false_direction_fraction, 1 / 3)

    def test_swing_trial_peak_velocity_pass(self):
        trial = {
            "exercise_id": "swing_left_1",
            "title": "Left",
            "expected_direction": "left",
            "expected_kind": "linear",
            "frames": [
                {
                    "grip_speed": 0.15,
                    "vx": -0.3,
                    "vy": 0.0,
                    "velocity_direction": "left",
                    "swing_phase": "begin",
                    "swing_direction": "left",
                    "swing_kind": "linear",
                    "attack": "none",
                },
                {
                    "grip_speed": 0.55,
                    "vx": -0.9,
                    "vy": 0.0,
                    "velocity_direction": "left",
                    "swing_phase": "mid",
                    "swing_direction": "left",
                    "swing_kind": "linear",
                    "attack": "left",
                },
            ],
        }
        s = score_trial(trial)
        self.assertTrue(s.peak_velocity_match)
        self.assertTrue(s.trial_pass)
        self.assertEqual(s.peak_velocity_direction, "left")

    def test_swing_trial_direction_accuracy(self):
        trial = {
            "exercise_id": "swing_left",
            "title": "Left",
            "expected_direction": "left",
            "expected_kind": "linear",
            "frames": [
                _frame(),
                _frame(
                    attack="none",
                    swing_direction="left",
                    swing_phase="begin",
                    swing_kind="linear",
                ),
                _frame(
                    attack="left",
                    swing_direction="left",
                    swing_phase="mid",
                    swing_kind="linear",
                ),
                _frame(
                    attack="left",
                    swing_direction="right",
                    swing_phase="mid",
                    swing_kind="linear",
                ),
            ],
        }
        s = score_trial(trial)
        self.assertEqual(s.motion_frame_count, 3)
        self.assertAlmostEqual(s.swing_direction_accuracy, 2 / 3)
        self.assertAlmostEqual(s.attack_direction_accuracy, 2 / 3)
        self.assertTrue(s.saw_begin and s.saw_mid)

    def test_session_overall_averages(self):
        log = {
            "trials": [
                {
                    "exercise_id": "rest",
                    "expected_direction": "none",
                    "frames": [_frame()] * 4,
                },
                {
                    "exercise_id": "swing_left",
                    "expected_direction": "left",
                    "frames": [
                        _frame(
                            swing_direction="left",
                            swing_phase="mid",
                            swing_kind="linear",
                        ),
                        _frame(
                            swing_direction="left",
                            swing_phase="end",
                            swing_kind="linear",
                        ),
                    ],
                },
            ]
        }
        s = score_session(log)
        self.assertAlmostEqual(s.overall_swing_direction_accuracy, 1.0)
        self.assertAlmostEqual(s.overall_idle_fraction, 1.0)

    def test_analyze_writes_summary(self):
        log = {
            "version": 1,
            "trials": [
                {
                    "exercise_id": "swing_right",
                    "title": "Right",
                    "expected_direction": "right",
                    "frames": [
                        _frame(
                            swing_direction="right",
                            swing_phase="mid",
                            swing_kind="linear",
                        ),
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session_test.json"
            path.write_text(json.dumps(log))
            report = analyze_log_file(path)
            self.assertIn("swing dir (all motion): 100%", report)
            self.assertTrue(path.with_name("session_test_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
