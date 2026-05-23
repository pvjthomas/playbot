"""Saber detector tests — run: python -m unittest discover -s tests -p 'test_saber*.py'"""

import math
import unittest

from saber_detector import SaberLine, orientation_from_angle


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


if __name__ == "__main__":
    unittest.main()
