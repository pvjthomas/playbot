"""Direction definitions — single source of truth for attacks vs training."""

import unittest

from directions import (
    ATTACK_SPECS,
    SABER_DATASET_FOLDERS,
    body_prompt_for_attack,
    strike_from_image_dx,
    training_prompt_for_attack,
)


class TestDirections(unittest.TestCase):
    def test_attack_specs_cover_contract_labels(self):
        for key in ("left", "right", "high", "center", "none"):
            self.assertIn(key, ATTACK_SPECS)
            self.assertIn("image_meaning", ATTACK_SPECS[key])

    def test_left_means_body_left(self):
        text = ATTACK_SPECS["left"]["image_meaning"].lower()
        self.assertIn("your left", text)
        self.assertNotIn("left edge", text)

    def test_strike_from_image_dx_body_semantics(self):
        self.assertEqual(strike_from_image_dx(0.2, 0.05), "left")
        self.assertEqual(strike_from_image_dx(-0.2, 0.05), "right")
        self.assertEqual(strike_from_image_dx(0.01, 0.05), "none")

    def test_strike_prompt_mentions_body_direction(self):
        p = training_prompt_for_attack("left")
        self.assertIn("YOUR LEFT", p)
        self.assertIn("RIGHT arm", p)
        self.assertIn("HOLD", p)
        self.assertIn("END", p)

    def test_training_folders_are_not_attacks(self):
        self.assertNotIn("left", SABER_DATASET_FOLDERS)
        self.assertIn("horizontal", SABER_DATASET_FOLDERS)

    def test_strike_capture_phase_is_end(self):
        from directions import STRIKE_CAPTURE_PHASE

        self.assertEqual(STRIKE_CAPTURE_PHASE, "end")

    def test_body_prompt_uses_anatomical_wording(self):
        left = body_prompt_for_attack("left")
        right = body_prompt_for_attack("right")
        self.assertIn("RIGHT arm", left)
        self.assertIn("YOUR LEFT", left)
        self.assertIn("LEFT arm", right)
        self.assertIn("YOUR RIGHT", right)
        self.assertIn("behind", left.lower())


if __name__ == "__main__":
    unittest.main()
