"""Saber detector tests — run: python -m unittest discover -s tests -p 'test_saber*.py'"""

import math
import unittest

import cv2
import numpy as np

import config
from saber_detector import SaberDetector, SaberLine, orientation_from_angle
from saber_profiles import apply_saber_profile


class TestSaberOrientation(unittest.TestCase):
    def test_horizontal(self):
        self.assertEqual(orientation_from_angle(0), "horizontal")
        self.assertEqual(orientation_from_angle(170), "horizontal")

    def test_vertical(self):
        self.assertEqual(orientation_from_angle(90), "vertical")
        self.assertEqual(orientation_from_angle(-90), "vertical")

    def test_diagonal(self):
        self.assertEqual(orientation_from_angle(45), "diagonal")

    def test_saber_line_angle(self):
        s = SaberLine(0, 0, 100, 0, "right", "horizontal", 1.0)
        self.assertAlmostEqual(s.angle_deg, 0.0, places=1)


class TestSaberColor(unittest.TestCase):
    def test_redtoy_profile_sets_hsv(self):
        old = config.SABER_PROFILE
        try:
            apply_saber_profile("redtoy")
            self.assertTrue(config.SABER_USE_COLOR_TIP)
            self.assertIsNotNone(config.SABER_COLOR_HSV_RANGES)
            self.assertEqual(len(config.SABER_COLOR_HSV_RANGES), 2)
        finally:
            config.SABER_PROFILE = old

    def test_color_mask_finds_red_pixel(self):
        apply_saber_profile("redtoy")
        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        frame[60, 80:] = (0, 0, 220)  # BGR red strip
        mask = SaberDetector.color_debug_mask(frame)
        self.assertIsNotNone(mask)
        assert mask is not None
        gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        self.assertGreater(cv2.countNonZero(gray), 0)

    def test_farthest_color_point_along_blade(self):
        apply_saber_profile("redtoy")
        mask = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(mask, (10, 50), (90, 50), 255, 8)
        det = SaberDetector()
        tip = det._farthest_color_point_along_blade(mask, 10, 50, 90, 50)
        self.assertIsNotNone(tip)
        assert tip is not None
        self.assertGreater(tip[0], 70)


if __name__ == "__main__":
    unittest.main()
