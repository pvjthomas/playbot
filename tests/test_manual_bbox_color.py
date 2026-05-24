"""Manual green-box bbox import."""

import unittest

import numpy as np

from manual_bbox_color import (
    bbox_from_color_mask,
    extract_yolo_bbox_from_image,
    parse_color,
)


class TestManualBboxColor(unittest.TestCase):
    def test_parse_hex_green(self):
        self.assertEqual(parse_color("#00FF00"), (0, 255, 0))

    def test_hollow_rectangle_bbox(self):
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        cv2 = __import__("cv2")
        cv2.rectangle(img, (50, 40), (220, 160), (0, 255, 0), 3)
        box = extract_yolo_bbox_from_image(img, (0, 255, 0), tolerance=48)
        self.assertIsNotNone(box)
        cx, cy, bw, bh = box
        self.assertAlmostEqual(cx, (50 + 220) / 2 / 300, delta=0.05)
        self.assertAlmostEqual(cy, (40 + 160) / 2 / 200, delta=0.05)
        self.assertGreater(bw * bh, 0.05)
        self.assertLess(bw * bh, 0.6)

    def test_no_color_returns_none(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertIsNone(extract_yolo_bbox_from_image(img, (0, 255, 0)))


if __name__ == "__main__":
    unittest.main()
