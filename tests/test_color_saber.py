"""Color saber calibration + label IOU helpers."""

import unittest

from saber_label_io import iou_yolo_norm


class TestSaberLabelIo(unittest.TestCase):
    def test_iou_identical(self):
        box = (0.5, 0.5, 0.2, 0.1)
        self.assertAlmostEqual(iou_yolo_norm(box, box), 1.0)

    def test_iou_disjoint(self):
        a = (0.2, 0.5, 0.1, 0.1)
        b = (0.8, 0.5, 0.1, 0.1)
        self.assertEqual(iou_yolo_norm(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
