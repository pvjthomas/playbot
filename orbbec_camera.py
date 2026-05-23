"""
Orbbec SDK camera capture — RGB + depth (+ optional IR).

Stub-friendly: when ``ENABLE_ORBBEC_SDK`` is False or the SDK is not installed,
use ``camera.open_camera()`` which falls back to OpenCV/ffmpeg.

When enabled and the SDK loads, this module opens a ``Pipeline`` and returns
``OrbbecFrameSet`` instances for depth-augmented vision work.

Run standalone preview:
    python orbbec_preview.py
"""

from __future__ import annotations

import time

import numpy as np

import config
from orbbec_frames import OrbbecFrameSet, depth_uint16_to_mm, frame_to_bgr_image
from orbbec_sdk import OrbbecSdkUnavailableError, install_hint, require_sdk


class OrbbecCamera:
    """
    Orbbec Dabai / RGB-D capture via pyorbbecsdk.

    Implements the same ``read_frame`` / ``release`` surface as ``camera.Camera``
    so ``open_camera()`` can swap backends without changing the app loop.
    """

    def __init__(self):
        self._pipeline = None
        self._sdk = require_sdk()
        self._last_frameset: OrbbecFrameSet | None = None
        self._start_pipeline()

    def _start_pipeline(self) -> None:
        sdk = self._sdk
        pipeline = sdk.Pipeline()
        cfg = sdk.Config()

        if getattr(config, "ORBBEC_ENABLE_DEPTH", True):
            self._enable_depth_stream(pipeline, cfg, sdk)
        self._enable_color_stream(pipeline, cfg, sdk)
        if getattr(config, "ORBBEC_ENABLE_IR", False):
            self._enable_ir_stream(pipeline, cfg, sdk)

        pipeline.start(cfg)
        self._pipeline = pipeline
        print(f"[orbbec] Pipeline started — {install_hint()}")

    @staticmethod
    def _enable_color_stream(pipeline, cfg, sdk) -> None:
        profiles = pipeline.get_stream_profile_list(sdk.OBSensorType.COLOR_SENSOR)
        try:
            profile = profiles.get_default_video_stream_profile()
        except sdk.OBError as exc:
            raise RuntimeError(f"Orbbec color stream unavailable: {exc}") from exc
        cfg.enable_stream(profile)

    @staticmethod
    def _enable_depth_stream(pipeline, cfg, sdk) -> None:
        profiles = pipeline.get_stream_profile_list(sdk.OBSensorType.DEPTH_SENSOR)
        try:
            profile = profiles.get_default_video_stream_profile()
        except sdk.OBError as exc:
            raise RuntimeError(f"Orbbec depth stream unavailable: {exc}") from exc
        cfg.enable_stream(profile)

    @staticmethod
    def _enable_ir_stream(pipeline, cfg, sdk) -> None:
        profiles = pipeline.get_stream_profile_list(sdk.OBSensorType.IR_SENSOR)
        profile = profiles.get_default_video_stream_profile()
        cfg.enable_stream(profile)

    def read_frameset(self, timeout_ms: int = 1000) -> OrbbecFrameSet | None:
        if self._pipeline is None:
            return None

        frames = self._pipeline.wait_for_frames(timeout_ms)
        if frames is None:
            return None

        color = None
        depth_mm = None
        ir = None

        color_frame = frames.get_color_frame()
        if color_frame is not None:
            color = frame_to_bgr_image(color_frame)

        if getattr(config, "ORBBEC_ENABLE_DEPTH", True):
            depth_frame = frames.get_depth_frame()
            if depth_frame is not None:
                w = depth_frame.get_width()
                h = depth_frame.get_height()
                scale = depth_frame.get_depth_scale()
                raw = np.frombuffer(depth_frame.get_data(), dtype=np.uint16).reshape((h, w))
                depth_mm = depth_uint16_to_mm(raw, scale)

        if getattr(config, "ORBBEC_ENABLE_IR", False):
            ir_frame = frames.get_ir_frame()
            if ir_frame is not None:
                w = ir_frame.get_width()
                h = ir_frame.get_height()
                ir = np.frombuffer(ir_frame.get_data(), dtype=np.uint16).reshape((h, w))

        result = OrbbecFrameSet(
            color=color,
            depth_mm=depth_mm,
            ir=ir,
            timestamp_ms=time.monotonic() * 1000.0,
        )
        self._last_frameset = result
        return result

    @property
    def last_frameset(self) -> OrbbecFrameSet | None:
        return self._last_frameset

    def read_frame(self):
        """Color-only frame for the existing vision loop."""
        fs = self.read_frameset()
        return fs.color if fs else None

    def release(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None


def try_open_orbbec_camera() -> OrbbecCamera | None:
    """Return ``OrbbecCamera`` when SDK is available; ``None`` otherwise."""
    try:
        return OrbbecCamera()
    except OrbbecSdkUnavailableError:
        return None
