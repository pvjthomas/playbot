"""Camera mirror detection tests."""

import unittest
from types import SimpleNamespace
from unittest import mock

from camera_mirror import (
    active_camera_source_key,
    detect_mirror_from_landmarks,
    image_direction_cheat_sheet,
    normalize_source_key,
)

import config


def _lm(overrides: dict[int, dict] | None = None):
    """Build minimal landmark list (33 pose points)."""
    points = []
    for i in range(33):
        points.append(SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=0.0))
    for idx, vals in (overrides or {}).items():
        for k, v in vals.items():
            setattr(points[idx], k, v)
    return SimpleNamespace(landmark=points)


class TestCameraMirror(unittest.TestCase):
    def test_normalize_laptop(self):
        self.assertEqual(normalize_source_key("laptop"), "laptop")

    def test_active_key_prefers_logical_laptop_over_index(self):
        prev = config.CAMERA_SOURCE
        try:
            config.CAMERA_SOURCE = "laptop"
            self.assertEqual(active_camera_source_key(0), "laptop")
        finally:
            config.CAMERA_SOURCE = prev

    def test_mirror_selfie_right_hand_on_right(self):
        # Right wrist raised, on right side of image
        landmarks = _lm({
            11: {"x": 0.4, "y": 0.4, "visibility": 0.9},
            12: {"x": 0.6, "y": 0.4, "visibility": 0.9},
            15: {"x": 0.35, "y": 0.7, "visibility": 0.9},  # left wrist low
            16: {"x": 0.72, "y": 0.25, "visibility": 0.9},  # right wrist high, right
        })
        self.assertTrue(detect_mirror_from_landmarks(landmarks))

    def test_true_camera_right_hand_on_left(self):
        landmarks = _lm({
            11: {"x": 0.4, "y": 0.4, "visibility": 0.9},
            12: {"x": 0.6, "y": 0.4, "visibility": 0.9},
            15: {"x": 0.65, "y": 0.7, "visibility": 0.9},
            16: {"x": 0.28, "y": 0.25, "visibility": 0.9},
        })
        self.assertFalse(detect_mirror_from_landmarks(landmarks))

    def test_cheat_sheet_unknown(self):
        self.assertIn("IMAGE-LEFT", image_direction_cheat_sheet(None))


if __name__ == "__main__":
    unittest.main()
