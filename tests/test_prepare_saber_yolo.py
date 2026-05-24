"""Auto-label bbox helpers."""

import math
import unittest
from types import SimpleNamespace

from prepare_saber_yolo_dataset import _bbox_from_saber_line, auto_label_box
from saber_detector import SaberLine
from saber_profiles import apply_saber_profile


class TestPrepareSaberYolo(unittest.TestCase):
    def test_saber_line_box_is_small(self):
        saber = SaberLine(
            grip_x=400,
            grip_y=300,
            tip_x=520,
            tip_y=280,
            hand="right",
            orientation="horizontal",
            confidence=0.9,
        )
        cx, cy, bw, bh = _bbox_from_saber_line(saber, 1280, 720, pad_ratio=0.16)
        self.assertLess(bw * bh, 0.15)

    def test_auto_label_rejects_person_sized_fallback(self):
        apply_saber_profile("redtoy")
        import numpy as np

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = (0, 0, 180)  # huge red field — old method would cover frame
        from saber_detector import SaberDetector
        from vision import AttackVision

        vision = AttackVision(static_image_mode=True)
        detector = SaberDetector()
        try:
            box = auto_label_box(
                frame,
                detector=detector,
                vision=vision,
                min_area_ratio=0.002,
                max_area_ratio=0.28,
                pad_ratio=0.16,
            )
            self.assertIsNone(box)
        finally:
            vision.close()
            detector.close()


if __name__ == "__main__":
    unittest.main()
