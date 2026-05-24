"""Camera orientation transform tests — no hardware."""

import unittest

import numpy as np

from camera_orientation import (
    MountFacing,
    OrientationCalibration,
    apply_orientation_transform,
    apply_rotation,
    detect_up_from_landmarks,
    transform_landmark_norm,
)


class TestOrientationTransforms(unittest.TestCase):
    def test_rotate_90_clockwise_shape(self):
        frame = np.arange(12, dtype=np.uint8).reshape(3, 4)
        out = apply_rotation(frame, 90)
        self.assertEqual(out.shape, (4, 3))

    def test_flip_h(self):
        cal = OrientationCalibration(flip_h=True)
        frame = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        out = apply_orientation_transform(frame, cal)
        np.testing.assert_array_equal(out, np.array([[2, 1], [4, 3]]))

    def test_landmark_roundtrip_180(self):
        cal = OrientationCalibration(rotation_deg=180)
        x, y = 0.2, 0.7
        tx, ty = transform_landmark_norm(x, y, cal)
        self.assertAlmostEqual(tx, 0.8)
        self.assertAlmostEqual(ty, 0.3)

    def test_detect_up_horizontal_shoulders(self):
        class LM:
            def __init__(self, x, y, v=0.9):
                self.x, self.y, self.visibility = x, y, v

        class Landmarks:
            landmark = [None] * 33
            landmark[11] = LM(0.3, 0.4)
            landmark[12] = LM(0.7, 0.4)

        self.assertEqual(detect_up_from_landmarks(Landmarks()), 0)

    def test_mount_facing_enum(self):
        self.assertEqual(MountFacing.TOWARD_PARTNER.value, "toward_partner")


if __name__ == "__main__":
    unittest.main()
