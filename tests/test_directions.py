"""Direction definitions — single source of truth for attacks vs training."""

import unittest

from directions import ATTACK_SPECS, SABER_DATASET_FOLDERS, training_prompt_for_attack


class TestDirections(unittest.TestCase):
    def test_attack_specs_cover_contract_labels(self):
        for key in ("left", "right", "high", "center", "none"):
            self.assertIn(key, ATTACK_SPECS)
            self.assertIn("image_meaning", ATTACK_SPECS[key])

    def test_left_means_image_left(self):
        text = ATTACK_SPECS["left"]["image_meaning"].lower()
        self.assertIn("left", text)
        self.assertIn("image", text)

    def test_training_folders_are_not_attacks(self):
        self.assertNotIn("left", SABER_DATASET_FOLDERS)
        self.assertIn("horizontal", SABER_DATASET_FOLDERS)

    def test_strike_prompt_mentions_image(self):
        p = training_prompt_for_attack("left")
        self.assertIn("IMAGE LEFT", p)
        self.assertIn("HOLD", p)
        self.assertIn("END", p)

    def test_strike_capture_phase_is_end(self):
        from directions import STRIKE_CAPTURE_PHASE

        self.assertEqual(STRIKE_CAPTURE_PHASE, "end")


if __name__ == "__main__":
    unittest.main()
