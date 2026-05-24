"""Direction review helpers."""

import unittest

from review_saber_directions import _build_queue, filename_hint


class TestReviewSaberDirections(unittest.TestCase):
    def test_strike_left_hint(self):
        self.assertEqual(
            filename_hint("redtoy_diagonal_strike_left_1779575808392"),
            "left",
        )

    def test_d_r2l_hint(self):
        self.assertEqual(filename_hint("redtoy_diagonal_d_r2l_1779575768888"), "right")

    def test_spot_queue_samples_buckets(self):
        records = [{"path": f"L{i}", "predicted": "left", "filename_hint": None} for i in range(10)]
        records += [{"path": f"R{i}", "predicted": "right", "filename_hint": None} for i in range(8)]
        queue = _build_queue(records, "spot", per_bucket=3, seed=1)
        self.assertEqual(len(queue), 6)

    def test_mismatch_mode(self):
        records = [
            {"path": "a", "predicted": "right", "filename_hint": "left"},
            {"path": "b", "predicted": "left", "filename_hint": "left"},
        ]
        queue = _build_queue(records, "mismatches", per_bucket=6, seed=1)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["path"], "a")


if __name__ == "__main__":
    unittest.main()
