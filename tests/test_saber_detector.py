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

    def test_tip_from_bbox_prefers_far_aligned_corner(self):
        tip = SaberDetector._tip_from_bbox(10, 40, 200, 60, 50, 50, 1.0, 0.0)
        self.assertIsNotNone(tip)
        assert tip is not None
        self.assertGreater(tip[0], 150)
        self.assertAlmostEqual(tip[1], 50, delta=15)

    def test_tip_from_bbox_vertical_blade(self):
        tip = SaberDetector._tip_from_bbox(90, 10, 110, 180, 100, 170, 0.0, -1.0)
        self.assertIsNotNone(tip)
        assert tip is not None
        self.assertLess(tip[1], 50)

    def test_refresh_cached_yolo_blends_toward_arm(self):
        apply_saber_profile("redtoy")
        arm = SaberLine(
            grip_x=100,
            grip_y=100,
            tip_x=180,
            tip_y=100,
            hand="right",
            orientation="horizontal",
            confidence=1.0,
            source="arm",
        )
        cached = [
            SaberLine(
                grip_x=100,
                grip_y=100,
                tip_x=100,
                tip_y=20,
                hand="right",
                orientation="vertical",
                confidence=0.5,
                source="yolo",
            )
        ]
        det = SaberDetector()
        frame = __import__("numpy").zeros((240, 320, 3), dtype=__import__("numpy").uint8)
        out = det._refresh_cached_yolo(frame, [arm], cached)
        self.assertEqual(len(out), 1)
        refreshed = out[0]
        self.assertEqual(refreshed.source, "yolo_cached")
        self.assertGreater(refreshed.tip_y, 20)
        self.assertLess(refreshed.tip_y, 100)

    def test_axis_from_color_roi_diagonal(self):
        apply_saber_profile("redtoy")
        config.SABER_AXIS_TIP_IN_FRAME = True
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        for i in range(40, 160):
            y = 180 - i // 2
            frame[y - 2 : y + 3, i] = (0, 0, 220)
        fit = SaberDetector._axis_from_color_roi(
            frame, 35, 60, 165, 130, 50, 120, 1.0, -0.5
        )
        self.assertIsNotNone(fit)
        assert fit is not None
        ux, uy, tip_x, tip_y, tip_in_frame, _trunc = fit
        self.assertGreater(tip_x, 100)
        self.assertLess(tip_y, 120)
        self.assertTrue(tip_in_frame)
        self.assertGreater(ux * 1.0 + uy * (-0.5), 0.5)


if __name__ == "__main__":
    unittest.main()
