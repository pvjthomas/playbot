"""
Lightsaber as a tubular segment: grip (wrist) → tip.

Phase 1 (now): forearm direction from MediaPipe + optional color tip refine.
Phase 2 (later): custom YOLO weights in SABER_MODEL, matched to nearest wrist.

Tip visibility: ``_saber_from_arm`` may place tip outside the image (unclamped).
Color refine stops at frame edges. YOLO merge extrapolates tip from grip + bbox angle.
``SaberLine`` has no tip-visible flag yet — see task-vision.md § Tip in/out of frame.

Not used in main.py fight loop until team enables it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import cv2
import mediapipe as mp
import numpy as np

import config
from contracts import Frame

_LEFT_ELBOW = 13
_RIGHT_ELBOW = 14
_LEFT_WRIST = 15
_RIGHT_WRIST = 16

Orientation = Literal["horizontal", "vertical", "diagonal", "unknown"]
Hand = Literal["left", "right"]


@dataclass
class SaberLine:
    """Grip at wrist; tip extends along blade (tubular object axis)."""

    grip_x: int
    grip_y: int
    tip_x: int
    tip_y: int
    hand: Hand
    orientation: Orientation
    confidence: float = 0.0

    @property
    def angle_deg(self) -> float:
        dx = self.tip_x - self.grip_x
        dy = self.tip_y - self.grip_y
        return math.degrees(math.atan2(dy, dx))

    @property
    def length_px(self) -> float:
        dx = self.tip_x - self.grip_x
        dy = self.tip_y - self.grip_y
        return math.hypot(dx, dy)


def orientation_from_angle(angle_deg: float) -> Orientation:
    """Classify blade angle: horizontal, vertical, or diagonal."""
    a = abs(angle_deg) % 180
    if a > 90:
        a = 180 - a
    if a <= config.SABER_HORIZONTAL_MAX_DEG:
        return "horizontal"
    if a >= config.SABER_VERTICAL_MIN_DEG:
        return "vertical"
    return "diagonal"


class SaberDetector:
    """
    Attach saber to body: wrist = grip, blade extends along forearm (wrist − elbow).

    Pass landmarks from AttackVision.last_landmarks to avoid running pose twice.
    """

    def __init__(self):
        self._pose = None
        self._yolo = None
        if config.SABER_USE_OWN_POSE:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        if config.SABER_MODEL:
            try:
                from ultralytics import YOLO

                self._yolo = YOLO(config.SABER_MODEL)
            except Exception as exc:
                print(f"[saber] YOLO model not loaded: {exc}")

    def detect_saber(self, frame: Frame, landmarks=None) -> SaberLine | None:
        sabers = self.detect_all(frame, landmarks)
        return sabers[0] if sabers else None

    def detect_all(self, frame: Frame, landmarks=None) -> list[SaberLine]:
        if frame is None:
            return []

        if landmarks is None:
            landmarks = self._get_landmarks(frame)
        if landmarks is None:
            return []

        h, w = frame.shape[:2]
        candidates: list[SaberLine] = []

        for hand, elbow_i, wrist_i in (
            ("left", _LEFT_ELBOW, _LEFT_WRIST),
            ("right", _RIGHT_ELBOW, _RIGHT_WRIST),
        ):
            line = self._saber_from_arm(landmarks, hand, elbow_i, wrist_i, w, h, frame)
            if line is not None:
                candidates.append(line)

        if self._yolo is not None:
            candidates = self._merge_yolo(frame, candidates)

        candidates.sort(key=lambda s: s.confidence, reverse=True)
        return candidates

    def _get_landmarks(self, frame: Frame):
        if self._pose is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        return result.pose_landmarks

    def _saber_from_arm(self, pose_landmarks, hand, elbow_i, wrist_i, w, h, frame):
        lm = pose_landmarks.landmark
        elbow = lm[elbow_i]
        wrist = lm[wrist_i]

        reach = math.hypot(wrist.x - elbow.x, wrist.y - elbow.y)
        if reach < config.SABER_MIN_FOREARM_REACH:
            return None

        # Blade continues past wrist: direction elbow → wrist
        dx = wrist.x - elbow.x
        dy = wrist.y - elbow.y
        length_norm = math.hypot(dx, dy)
        if length_norm < 1e-6:
            return None
        ux, uy = dx / length_norm, dy / length_norm

        grip_x = int(wrist.x * w)
        grip_y = int(wrist.y * h)
        blade_norm = config.SABER_BLADE_LENGTH_RATIO
        tip_x = int((wrist.x + ux * blade_norm) * w)
        tip_y = int((wrist.y + uy * blade_norm) * h)

        color_tip = False
        if config.SABER_USE_COLOR_TIP:
            refined = self._refine_tip_with_color(frame, grip_x, grip_y, tip_x, tip_y)
            if refined is not None:
                tip_x, tip_y = refined
                color_tip = True

        angle = math.degrees(math.atan2(tip_y - grip_y, tip_x - grip_x))
        orient = orientation_from_angle(angle)
        conf = min(1.0, reach / 0.25)
        if color_tip:
            conf = min(1.0, conf + 0.2)

        return SaberLine(
            grip_x=grip_x,
            grip_y=grip_y,
            tip_x=tip_x,
            tip_y=tip_y,
            hand=hand,
            orientation=orient,
            confidence=conf,
        )

    def _refine_tip_with_color(
        self, frame: Frame, gx: int, gy: int, tx: int, ty: int
    ) -> tuple[int, int] | None:
        """Find blade tip via HSV (e.g. red toy) along forearm direction."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = self._color_mask(hsv)
        if mask is None:
            return self._refine_tip_brightness(frame, gx, gy, tx, ty)

        tip = self._farthest_color_point_along_blade(mask, gx, gy, tx, ty)
        if tip is not None:
            return tip
        return None

    @staticmethod
    def _color_mask(hsv: np.ndarray) -> np.ndarray | None:
        ranges = getattr(config, "SABER_COLOR_HSV_RANGES", None)
        if ranges:
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for lo, hi in ranges:
                mask |= cv2.inRange(hsv, np.array(lo, dtype=np.uint8), np.array(hi, dtype=np.uint8))
            return mask
        if config.SABER_TIP_HSV_LOW is not None and config.SABER_TIP_HSV_HIGH is not None:
            lo = np.array(config.SABER_TIP_HSV_LOW, dtype=np.uint8)
            hi = np.array(config.SABER_TIP_HSV_HIGH, dtype=np.uint8)
            return cv2.inRange(hsv, lo, hi)
        return None

    @staticmethod
    def color_debug_mask(frame: Frame) -> np.ndarray | None:
        """BGR preview of active color mask (for tuning redtoy HSV)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = SaberDetector._color_mask(hsv)
        if mask is None:
            return None
        return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    def _farthest_color_point_along_blade(
        self,
        mask: np.ndarray,
        gx: int,
        gy: int,
        tx: int,
        ty: int,
    ) -> tuple[int, int] | None:
        """Tip = farthest matching pixel from grip, searched along forearm ray."""
        dx, dy = tx - gx, ty - gy
        length = math.hypot(dx, dy)
        if length < 8:
            return None
        ux, uy = dx / length, dy / length
        radius = int(getattr(config, "SABER_COLOR_SEARCH_RADIUS_PX", 35))
        min_pixels = int(getattr(config, "SABER_MIN_COLOR_PIXELS", 20))
        h, w = mask.shape[:2]

        best_pt: tuple[int, int] | None = None
        best_dist = 0.0
        steps = max(24, int(length // 4))

        for i in range(1, steps + 1):
            t = i / steps
            cx = int(gx + dx * t)
            cy = int(gy + dy * t)
            if not (0 <= cx < w and 0 <= cy < h):
                break

            x0 = max(0, cx - radius)
            x1 = min(w, cx + radius + 1)
            y0 = max(0, cy - radius)
            y1 = min(h, cy + radius + 1)
            patch = mask[y0:y1, x0:x1]
            if patch.size == 0 or cv2.countNonZero(patch) < min_pixels // steps:
                continue

            ys, xs = np.where(patch > 0)
            for x, y in zip(xs, ys, strict=False):
                px, py = x0 + int(x), y0 + int(y)
                along = (px - gx) * ux + (py - gy) * uy
                if along < 10:
                    continue
                perp = abs((px - gx) * (-uy) + (py - gy) * ux)
                if perp > radius * 1.2:
                    continue
                if along > best_dist:
                    best_dist = along
                    best_pt = (px, py)

        return best_pt

    @staticmethod
    def _refine_tip_brightness(
        frame: Frame, gx: int, gy: int, tx: int, ty: int
    ) -> tuple[int, int] | None:
        steps = 20
        best_score = -1.0
        best_pt = None
        for i in range(1, steps + 1):
            t = i / steps
            x = int(gx + (tx - gx) * t)
            y = int(gy + (ty - gy) * t)
            if not (0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]):
                break
            b, g, r = frame[y, x]
            score = float(r) + float(g) * 0.5
            if score > best_score:
                best_score = score
                best_pt = (x, y)
        if best_score > 0 and best_pt is not None:
            return best_pt
        return None

    def _merge_yolo(self, frame: Frame, arm_lines: list[SaberLine]) -> list[SaberLine]:
        """When trained, snap YOLO bbox long axis to nearest wrist grip."""
        results = self._yolo(frame, verbose=False)[0]
        if not results.boxes:
            return arm_lines

        out: list[SaberLine] = []
        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            bw, bh = x2 - x1, y2 - y1
            if bw >= bh:
                angle = 0.0 if x2 > x1 else 180.0
            else:
                angle = 90.0 if y2 > y1 else -90.0

            nearest = None
            best_d = 1e9
            for s in arm_lines:
                d = math.hypot(s.grip_x - cx, s.grip_y - cy)
                if d < best_d:
                    best_d = d
                    nearest = s
            if nearest is None or best_d > config.SABER_YOLO_MAX_GRIP_DIST_PX:
                continue

            length = nearest.length_px or 80
            rad = math.radians(angle)
            tip_x = int(nearest.grip_x + math.cos(rad) * length)
            tip_y = int(nearest.grip_y + math.sin(rad) * length)
            orient = orientation_from_angle(angle)
            out.append(
                SaberLine(
                    grip_x=nearest.grip_x,
                    grip_y=nearest.grip_y,
                    tip_x=tip_x,
                    tip_y=tip_y,
                    hand=nearest.hand,
                    orientation=orient,
                    confidence=float(box.conf[0]),
                )
            )
        return out or arm_lines

    def close(self):
        if self._pose is not None:
            self._pose.close()


def draw_saber_overlay(frame: Frame, saber: SaberLine | None, *, color: tuple[int, int, int] | None = None) -> Frame:
    """Draw grip→tip line and orientation label (BGR)."""
    if saber is None:
        return frame
    out = frame.copy()
    line_color = color or (0, 255, 0)
    if getattr(config, "SABER_PROFILE", "") == "redtoy":
        line_color = color or (0, 0, 255)
    cv2.line(out, (saber.grip_x, saber.grip_y), (saber.tip_x, saber.tip_y), line_color, 3)
    cv2.circle(out, (saber.grip_x, saber.grip_y), 6, (0, 200, 255), -1)
    cv2.circle(out, (saber.tip_x, saber.tip_y), 6, line_color, -1)
    label = f"saber {saber.hand} {saber.orientation} {saber.angle_deg:.0f}deg"
    profile = getattr(config, "SABER_PROFILE", "")
    if profile:
        label = f"{profile} {label}"
    cv2.putText(
        out,
        label,
        (saber.grip_x + 8, saber.grip_y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        line_color,
        2,
    )
    return out
