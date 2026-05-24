"""
Detect hand-drawn bounding boxes by annotation stroke color (Paint, ImageJ, etc.).

Use a pure, unlikely color for the rectangle outline — default bright green #00FF00.
"""

from __future__ import annotations

import re
from typing import Iterable

import cv2
import numpy as np

# BGR for OpenCV
PRESET_COLORS: dict[str, tuple[int, int, int]] = {
    "green": (0, 255, 0),
    "magenta": (255, 0, 255),
    "cyan": (255, 255, 0),
    "yellow": (0, 255, 255),
}


def parse_color(text: str) -> tuple[int, int, int]:
    """Parse 'green', '#00FF00', or '0,255,0' (RGB) → BGR tuple."""
    key = text.strip().lower()
    if key in PRESET_COLORS:
        return PRESET_COLORS[key]
    if key.startswith("#") and len(key) in (4, 7):
        hex_rgb = key[1:]
        if len(hex_rgb) == 3:
            hex_rgb = "".join(c * 2 for c in hex_rgb)
        r = int(hex_rgb[0:2], 16)
        g = int(hex_rgb[2:4], 16)
        b = int(hex_rgb[4:6], 16)
        return (b, g, r)
    parts = [int(x.strip()) for x in re.split(r"[,;\s]+", key) if x.strip()]
    if len(parts) == 3:
        r, g, b = parts
        return (b, g, r)
    raise ValueError(f"Unknown color {text!r}. Use green, #00FF00, or R,G,B")


def annotation_mask(
    bgr: np.ndarray,
    color_bgr: tuple[int, int, int],
    tolerance: int = 48,
) -> np.ndarray:
    """Binary mask of pixels matching the annotation color (with tolerance)."""
    diff = np.abs(bgr.astype(np.int16) - np.array(color_bgr, dtype=np.int16))
    return (np.all(diff <= tolerance, axis=2).astype(np.uint8)) * 255


def bbox_from_color_mask(
    mask: np.ndarray,
    *,
    min_area_ratio: float = 0.0005,
    max_area_ratio: float = 0.85,
    dilate_px: int = 4,
) -> tuple[float, float, float, float] | None:
    """
    YOLO-normalized cx, cy, w, h from colored stroke pixels.

    Hollow rectangle outlines work — we take the outer bounding rect of all
    matching pixels (stroke width makes box ~1–3 px generous).
    """
    h, w = mask.shape[:2]
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (dilate_px * 2 + 1, dilate_px * 2 + 1))
        mask = cv2.dilate(mask, k, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = h * w
    kept: list = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < frame_area * min_area_ratio:
            continue
        if area > frame_area * max_area_ratio:
            continue
        kept.append(cnt)

    if not kept:
        return None

    xs, ys, xe, ye = w, h, 0, 0
    for cnt in kept:
        x, y, bw, bh = cv2.boundingRect(cnt)
        xs = min(xs, x)
        ys = min(ys, y)
        xe = max(xe, x + bw)
        ye = max(ye, y + bh)

    bw = xe - xs
    bh = ye - ys
    if bw < 4 or bh < 4:
        return None
    return (xs + bw / 2) / w, (ys + bh / 2) / h, bw / w, bh / h


def extract_yolo_bbox_from_image(
    bgr: np.ndarray,
    color_bgr: tuple[int, int, int],
    *,
    tolerance: int = 48,
    min_area_ratio: float = 0.0005,
    max_area_ratio: float = 0.85,
) -> tuple[float, float, float, float] | None:
    mask = annotation_mask(bgr, color_bgr, tolerance)
    box = bbox_from_color_mask(
        mask,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
    )
    if box is not None and min(box[2], box[3]) / max(box[2], box[3], 1e-9) >= 0.08:
        return box

    # Paint/ImageJ anti-aliasing — retry looser RGB then HSV "green" band
    for tol in (min(tolerance + 24, 96),):
        mask2 = annotation_mask(bgr, color_bgr, tol)
        box2 = bbox_from_color_mask(mask2, min_area_ratio=min_area_ratio, max_area_ratio=max_area_ratio)
        if box2 is not None and min(box2[2], box2[3]) / max(box2[2], box2[3], 1e-9) >= 0.08:
            return box2

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hsv_mask = cv2.inRange(hsv, (35, 60, 60), (95, 255, 255))
    return bbox_from_color_mask(
        hsv_mask,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
    )


def yolo_line(box: Iterable[float]) -> str:
    cx, cy, bw, bh = box
    return f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n"
