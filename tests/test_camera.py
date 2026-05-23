"""Camera resolution tests — no hardware required."""

import unittest
from unittest import mock

import config
from camera import find_piper_avfoundation_name, find_piper_camera_source, resolve_camera_source


class TestCameraResolve(unittest.TestCase):
    def test_numeric_source(self):
        self.assertEqual(resolve_camera_source("1"), 1)
        self.assertEqual(resolve_camera_source(2), 2)

    def test_dev_path(self):
        self.assertEqual(resolve_camera_source("/dev/video2"), "/dev/video2")

    def test_auto_falls_back_to_index(self):
        old = config.CAMERA_INDEX
        config.CAMERA_INDEX = 0
        try:
            with mock.patch("camera._piper_camera_reported", return_value=False):
                self.assertEqual(resolve_camera_source("auto"), 0)
        finally:
            config.CAMERA_INDEX = old

    def test_piper_uses_avfoundation_on_mac(self):
        with mock.patch("camera.platform.system", return_value="Darwin"), mock.patch(
            "camera.find_piper_avfoundation_name", return_value="Dabai DC1"
        ), mock.patch("camera._ffmpeg_path", return_value="/usr/bin/ffmpeg"):
            self.assertEqual(resolve_camera_source("piper"), "avfoundation:Dabai DC1")

    def test_laptop_alias(self):
        old = config.CAMERA_INDEX
        config.CAMERA_INDEX = 0
        try:
            self.assertEqual(resolve_camera_source("laptop"), 0)
        finally:
            config.CAMERA_INDEX = old

    def test_opencv_backend_skips_ffmpeg_on_mac(self):
        old = config.CAMERA_BACKEND
        old_idx = config.PIPER_OPENCV_INDEX
        config.CAMERA_BACKEND = "opencv"
        config.PIPER_OPENCV_INDEX = 2
        try:
            with mock.patch("camera.platform.system", return_value="Darwin"):
                self.assertEqual(find_piper_camera_source(), 2)
        finally:
            config.CAMERA_BACKEND = old
            config.PIPER_OPENCV_INDEX = old_idx

    def test_configured_piper_name(self):
        old = config.PIPER_CAMERA_NAME
        config.PIPER_CAMERA_NAME = "Dabai DC1"
        try:
            self.assertEqual(find_piper_avfoundation_name(), "Dabai DC1")
        finally:
            config.PIPER_CAMERA_NAME = old

    def test_pick_candidates_include_opencv_even_without_initial_read(self):
        from camera import CameraProbe, _pick_candidates

        def fake_probe(i, **kwargs):
            if i == 1:
                return CameraProbe(1, True, False, 1920, 1080, "AVFOUNDATION")
            return CameraProbe(i, False, False, 0, 0, "")

        with mock.patch("camera.platform.system", return_value="Darwin"), mock.patch(
            "camera.list_avfoundation_devices", return_value=[]
        ), mock.patch("camera.probe_camera", side_effect=fake_probe):
            candidates = _pick_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][1], 1)
        self.assertIn("warmup", candidates[0][0])


if __name__ == "__main__":
    unittest.main()
