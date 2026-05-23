"""Shared Orbbec frame types and color/depth conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

Frame = np.ndarray


@dataclass
class OrbbecFrameSet:
    """Synchronized Orbbec streams for one capture tick."""

    color: Frame | None = None
    depth_mm: Frame | None = None  # float32, millimeters; 0/NaN = invalid
    ir: Frame | None = None
    timestamp_ms: float = 0.0


def depth_uint16_to_mm(raw: np.ndarray, scale: float) -> np.ndarray:
    """Convert raw depth buffer to float32 millimeters."""
    depth = raw.astype(np.float32) * float(scale)
    depth[depth <= 0] = np.nan
    return depth


def render_depth_preview(
    depth_mm: Frame,
    *,
    min_mm: float = 200.0,
    max_mm: float = 4000.0,
) -> Frame:
    """BGR colormap preview for HUD / orbbec_preview.py."""
    valid = np.isfinite(depth_mm)
    if not np.any(valid):
        return np.zeros((*depth_mm.shape, 3), dtype=np.uint8)

    clipped = np.clip(np.nan_to_num(depth_mm, nan=max_mm), min_mm, max_mm)
    norm = (clipped - min_mm) / max(max_mm - min_mm, 1e-6)
    depth_8 = (np.power(norm, 0.8) * 255).astype(np.uint8)
    colored = cv2.applyColorMap(depth_8, cv2.COLORMAP_JET)
    colored[~valid] = 0
    return colored


def frame_to_bgr_image(frame) -> Frame | None:
    """
    Convert a pyorbbecsdk VideoFrame to BGR numpy array.

    Minimal port of upstream ``examples/utils.py`` — extend when new formats appear.
    """
    sdk = __import__("pyorbbecsdk", fromlist=["OBFormat"])
    ob_format = sdk.OBFormat

    width = frame.get_width()
    height = frame.get_height()
    fmt = frame.get_format()
    data = np.asanyarray(frame.get_data())

    if fmt == ob_format.RGB:
        image = data.reshape((height, width, 3))
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if fmt == ob_format.BGR:
        return data.reshape((height, width, 3)).copy()
    if fmt == ob_format.MJPG:
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    if fmt == ob_format.YUYV:
        image = data.reshape((height, width, 2))
        return cv2.cvtColor(image, cv2.COLOR_YUV2BGR_YUYV)
    if fmt == ob_format.UYVY:
        image = data.reshape((height, width, 2))
        return cv2.cvtColor(image, cv2.COLOR_YUV2BGR_UYVY)

    # SDK filter path for less common formats
    convert_format = _determine_convert_format(frame, sdk)
    if convert_format is None:
        return None
    convert_filter = sdk.FormatConvertFilter()
    convert_filter.set_format_convert_format(convert_format)
    rgb_frame = convert_filter.process(frame)
    if rgb_frame is None:
        return None
    rgb = np.asanyarray(rgb_frame.get_data()).reshape((height, width, 3))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _determine_convert_format(frame, sdk):
    ob_format = sdk.OBFormat
    ob_convert = sdk.OBConvertFormat
    fmt = frame.get_format()
    mapping = {
        ob_format.I420: ob_convert.I420_TO_RGB888,
        ob_format.MJPG: ob_convert.MJPG_TO_RGB888,
        ob_format.YUYV: ob_convert.YUYV_TO_RGB888,
        ob_format.NV21: ob_convert.NV21_TO_RGB888,
        ob_format.NV12: ob_convert.NV12_TO_RGB888,
        ob_format.UYVY: ob_convert.UYVY_TO_RGB888,
    }
    return mapping.get(fmt)
