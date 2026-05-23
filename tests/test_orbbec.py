"""Orbbec stub tests — no camera hardware required."""

import unittest
from unittest import mock

import numpy as np

import config
from orbbec_depth import DepthAttackHints, depth_at, depth_delta_from_baseline, median_depth_in_roi
from orbbec_frames import depth_uint16_to_mm, render_depth_preview
from orbbec_sdk import sdk_status
from orbbec_vision import DepthAugmentedAttackVision


class TestOrbbecDepth(unittest.TestCase):
    def test_depth_at_valid_pixel(self):
        depth = np.full((10, 10), 1500.0, dtype=np.float32)
        self.assertEqual(depth_at(depth, 5, 5), 1500.0)

    def test_depth_at_invalid(self):
        depth = np.full((10, 10), np.nan, dtype=np.float32)
        self.assertIsNone(depth_at(depth, 5, 5))

    def test_median_depth_in_roi(self):
        depth = np.ones((20, 20), dtype=np.float32) * 1000.0
        depth[5:15, 5:15] = 2000.0
        self.assertEqual(median_depth_in_roi(depth, 5, 5, 15, 15), 2000.0)

    def test_lunge_hint_when_closer(self):
        depth = np.full((100, 100), 2000.0, dtype=np.float32)
        depth[40:60, 40:60] = 1700.0
        old = config.ORBBEC_LUNGE_DEPTH_DELTA_MM
        config.ORBBEC_LUNGE_DEPTH_DELTA_MM = 150
        try:
            hints = DepthAttackHints.from_frames(
                depth,
                torso_roi=(40, 40, 60, 60),
                baseline_mm=2000.0,
            )
            self.assertTrue(hints.lunge_toward_camera)
        finally:
            config.ORBBEC_LUNGE_DEPTH_DELTA_MM = old

    def test_depth_delta_positive_when_closer(self):
        depth = np.full((10, 10), 1200.0, dtype=np.float32)
        delta = depth_delta_from_baseline(depth, 2000.0, 0, 0, 10, 10)
        self.assertEqual(delta, 800.0)


class TestOrbbecFrames(unittest.TestCase):
    def test_uint16_to_mm(self):
        raw = np.array([[1000, 0]], dtype=np.uint16)
        mm = depth_uint16_to_mm(raw, 0.5)
        self.assertAlmostEqual(mm[0, 0], 500.0)
        self.assertTrue(np.isnan(mm[0, 1]))

    def test_render_depth_preview_shape(self):
        depth = np.linspace(500, 3000, 100, dtype=np.float32).reshape(10, 10)
        img = render_depth_preview(depth)
        self.assertEqual(img.shape, (10, 10, 3))


class TestOrbbecVision(unittest.TestCase):
    def test_fuse_depth_promotes_center_on_lunge(self):
        hints = DepthAttackHints(lunge_toward_camera=True)
        out = DepthAugmentedAttackVision._fuse_depth("none", hints)
        self.assertEqual(out, "center")

    def test_fuse_depth_keeps_mediapipe_label(self):
        hints = DepthAttackHints(lunge_toward_camera=True)
        out = DepthAugmentedAttackVision._fuse_depth("left", hints)
        self.assertEqual(out, "left")


class TestOrbbecSdk(unittest.TestCase):
    def test_sdk_status_returns_dataclass(self):
        status = sdk_status()
        self.assertIsInstance(status.installed, bool)

    def test_open_camera_uses_orbbec_when_enabled(self):
        old = config.ENABLE_ORBBEC_SDK
        config.ENABLE_ORBBEC_SDK = True
        try:
            with mock.patch("orbbec_camera.OrbbecCamera") as mock_cam:
                from camera import open_camera

                open_camera()
                mock_cam.assert_called_once()
        finally:
            config.ENABLE_ORBBEC_SDK = old

    def test_open_camera_default_is_opencv(self):
        old = config.ENABLE_ORBBEC_SDK
        config.ENABLE_ORBBEC_SDK = False
        try:
            with mock.patch("camera.Camera") as mock_cam:
                from camera import open_camera

                open_camera()
                mock_cam.assert_called_once()
        finally:
            config.ENABLE_ORBBEC_SDK = old


if __name__ == "__main__":
    unittest.main()
