"""
Fast saber detector — calibrated HSV + MediaPipe arm corridor (no YOLO).

Calibrate from manual labels:
  python calibrate_saber_color.py --saber redtoy

Preview:
  python saber_preview.py --saber redtoy --detector color --camera laptop
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from contracts import Frame
from saber_detector import SaberLine, orientation_from_angle
from saber_label_io import xyxy_to_yolo_norm, yolo_norm_to_xyxy

_CALIB_ROOT = Path(__file__).resolve().parents[1] / "models" / "saber_color"

_LEFT_ELBOW = 13
_RIGHT_ELBOW = 14
_LEFT_WRIST = 15
_RIGHT_WRIST = 16


@dataclass
class ColorCalibration:
    saber_id: str
    hsv_ranges_tight: list[tuple[tuple[int, int, int], tuple[int, int, int]]]
    hsv_ranges_loose: list[tuple[tuple[int, int, int], tuple[int, int, int]]]
    arm_corridor_radius_px: int = 55
    arm_extend_factor: float = 4.0
    min_pixels: int = 50
    median_box_area_norm: float = 0.095
    median_aspect: float = 2.2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColorCalibration:
        def ranges(key: str) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
            return [((int(lo[0]), int(lo[1]), int(lo[2])), (int(hi[0]), int(hi[1]), int(hi[2]))) for lo, hi in data[key]]

        return cls(
            saber_id=str(data.get("saber_id", "redtoy")),
            hsv_ranges_tight=ranges("hsv_ranges_tight"),
            hsv_ranges_loose=ranges("hsv_ranges_loose"),
            arm_corridor_radius_px=int(data.get("arm_corridor_radius_px", 55)),
            arm_extend_factor=float(data.get("arm_extend_factor", 4.0)),
            min_pixels=int(data.get("min_pixels", 50)),
            median_box_area_norm=float(data.get("median_box_area_norm", 0.095)),
            median_aspect=float(data.get("median_aspect", 2.2)),
        )

    def to_dict(self) -> dict[str, Any]:
        def pack(ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]]) -> list[list[list[int]]]:
            return [[list(lo), list(hi)] for lo, hi in ranges]

        return {
            "saber_id": self.saber_id,
            "hsv_ranges_tight": pack(self.hsv_ranges_tight),
            "hsv_ranges_loose": pack(self.hsv_ranges_loose),
            "arm_corridor_radius_px": self.arm_corridor_radius_px,
            "arm_extend_factor": self.arm_extend_factor,
            "min_pixels": self.min_pixels,
            "median_box_area_norm": self.median_box_area_norm,
            "median_aspect": self.median_aspect,
        }


def calibration_path(saber_id: str) -> Path:
    return _CALIB_ROOT / f"{saber_id.strip().lower()}_calibration.json"


def load_calibration(saber_id: str) -> ColorCalibration:
    path = calibration_path(saber_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No color calibration at {path}. Run: python calibrate_saber_color.py --saber {saber_id}"
        )
    return ColorCalibration.from_dict(json.loads(path.read_text()))


def save_calibration(cal: ColorCalibration) -> Path:
    _CALIB_ROOT.mkdir(parents=True, exist_ok=True)
    path = calibration_path(cal.saber_id)
    path.write_text(json.dumps(cal.to_dict(), indent=2) + "\n")
    return path


def _hsv_mask(hsv: np.ndarray, ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]]) -> np.ndarray:
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in ranges:
        mask |= cv2.inRange(hsv, np.array(lo, dtype=np.uint8), np.array(hi, dtype=np.uint8))
    return mask


def _arm_corridors(
    landmarks,
    h: int,
    w: int,
    *,
    radius_px: int,
    extend_factor: float,
) -> list[np.ndarray]:
    corridors: list[np.ndarray] = []
    for elbow_i, wrist_i in ((_LEFT_ELBOW, _LEFT_WRIST), (_RIGHT_ELBOW, _RIGHT_WRIST)):
        elbow = landmarks[elbow_i]
        wrist = landmarks[wrist_i]
        if elbow.visibility < 0.3 or wrist.visibility < 0.3:
            continue
        ex, ey = int(elbow.x * w), int(elbow.y * h)
        wx, wy = int(wrist.x * w), int(wrist.y * h)
        dx, dy = wx - ex, wy - ey
        tx, ty = int(wx + dx * extend_factor), int(wy + dy * extend_factor)
        corridor = np.zeros((h, w), dtype=np.uint8)
        cv2.line(corridor, (ex, ey), (tx, ty), 255, radius_px * 2)
        corridors.append(corridor)
    return corridors


class ColorSaberDetector:
    """
    Red saber via calibrated HSV inside pose arm corridors.

    Blade axis comes from the detected color blob (not forearm direction).
    """

    def __init__(
        self,
        calibration: ColorCalibration | str,
        *,
        use_own_pose: bool = False,
    ):
        if isinstance(calibration, str):
            calibration = load_calibration(calibration)
        self.cal = calibration
        self._pose = None
        if use_own_pose:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def close(self):
        if self._pose is not None:
            self._pose.close()

    def _landmarks(self, frame: Frame, landmarks=None):
        if landmarks is not None:
            return landmarks.landmark if hasattr(landmarks, "landmark") else landmarks
        if self._pose is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return None
        return result.pose_landmarks.landmark

    def detect_bbox(
        self,
        frame: Frame,
        landmarks=None,
    ) -> tuple[float, float, float, float] | None:
        """YOLO-normalized cx, cy, w, h or None."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        lm = self._landmarks(frame, landmarks)
        if lm is None:
            return self._fallback_full_frame(frame)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        tight = _hsv_mask(hsv, self.cal.hsv_ranges_tight)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        best_box: tuple[float, float, float, float] | None = None
        best_score = -1.0

        for corridor in _arm_corridors(
            lm,
            h,
            w,
            radius_px=self.cal.arm_corridor_radius_px,
            extend_factor=self.cal.arm_extend_factor,
        ):
            masked = cv2.bitwise_and(tight, corridor)
            masked = cv2.morphologyEx(masked, cv2.MORPH_CLOSE, kernel, iterations=2)
            ys, xs = np.where(masked > 0)
            if len(xs) < self.cal.min_pixels:
                continue
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            bw, bh = max(1, x2 - x1 + 1), max(1, y2 - y1 + 1)
            area_norm = (bw * bh) / (h * w)
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            area_penalty = abs(area_norm - self.cal.median_box_area_norm) / (
                self.cal.median_box_area_norm + 1e-9
            )
            score = len(xs) * min(aspect / self.cal.median_aspect, 2.0) * max(0.2, 1.0 - area_penalty)
            if score > best_score:
                best_score = score
                best_box = xyxy_to_yolo_norm(x1, y1, x2, y2, w, h)

        return best_box

    def _fallback_full_frame(self, frame: Frame) -> tuple[float, float, float, float] | None:
        """No pose — largest tight-red blob with saber-like aspect."""
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = _hsv_mask(hsv, self.cal.hsv_ranges_tight)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_score = -1.0
        frame_area = h * w
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.cal.min_pixels or area > frame_area * 0.35:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            if aspect < 1.3:
                continue
            score = area * min(aspect / 2.0, 2.0)
            if score > best_score:
                best_score = score
                best = xyxy_to_yolo_norm(x, y, x + bw, y + bh, w, h)
        return best

    def detect_saber(
        self,
        frame: Frame,
        landmarks=None,
    ) -> SaberLine | None:
        box = self.detect_bbox(frame, landmarks)
        if box is None:
            return None
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = yolo_norm_to_xyxy(box, w, h)
        bw, bh = x2 - x1, y2 - y1
        if bw >= bh:
            tip_x, tip_y = (x2, (y1 + y2) // 2) if bw >= bh else ((x1 + x2) // 2, y2)
        else:
            tip_x, tip_y = (x1 + x2) // 2, y2 if y2 > y1 else y1
        # grip = nearer wrist if pose available, else bbox end closer to image center bottom
        grip_x, grip_y = x1, (y1 + y2) // 2
        if bw < bh:
            grip_x, grip_y = (x1 + x2) // 2, y1
        lm = self._landmarks(frame, landmarks)
        if lm is not None:
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            wrists = []
            for i in (_LEFT_WRIST, _RIGHT_WRIST):
                if lm[i].visibility >= 0.3:
                    wrists.append((lm[i].x * w, lm[i].y * h))
            if wrists:
                wx, wy = min(wrists, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
                grip_x, grip_y = int(wx), int(wy)
                # tip = far bbox corner along long axis from grip
                corners = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
                tip_x, tip_y = max(corners, key=lambda p: (p[0] - grip_x) ** 2 + (p[1] - grip_y) ** 2)

        angle = math.degrees(math.atan2(tip_y - grip_y, tip_x - grip_x))
        hand = "right" if grip_x > w / 2 else "left"
        return SaberLine(
            grip_x=int(grip_x),
            grip_y=int(grip_y),
            tip_x=int(tip_x),
            tip_y=int(tip_y),
            hand=hand,
            orientation=orientation_from_angle(angle),
            confidence=0.75,
        )

    def debug_mask(self, frame: Frame, landmarks=None) -> np.ndarray | None:
        if frame is None:
            return None
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        tight = _hsv_mask(hsv, self.cal.hsv_ranges_tight)
        lm = self._landmarks(frame, landmarks)
        if lm is None:
            return cv2.cvtColor(tight, cv2.COLOR_GRAY2BGR)
        out = np.zeros_like(tight)
        for corridor in _arm_corridors(
            lm,
            h,
            w,
            radius_px=self.cal.arm_corridor_radius_px,
            extend_factor=self.cal.arm_extend_factor,
        ):
            out |= cv2.bitwise_and(tight, corridor)
        return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
