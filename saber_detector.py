"""
Lightsaber as a tubular segment: grip (wrist) → tip.

Phase 1 (now): forearm direction from MediaPipe + optional color tip refine.
Phase 2 (later): custom YOLO weights in SABER_MODEL, matched to nearest wrist.

Tip visibility: ``_saber_from_arm`` may place tip outside the image (unclamped).
Color refine stops at frame edges. YOLO merge uses bbox far corner + optional color refine.
``SaberLine`` has no tip-visible flag yet — see task-vision.md § Tip in/out of frame.

Not used in main.py fight loop until team enables it.

Saber detector TODO
-------------------
**Does YOLO need retraining on different positions?** Yes — for live swing eval the current
``redtoy_78shot`` weights are weak because training skews toward static full-blade poses.
Code fixes (bbox tip, cache blend, yolo-only fusion) help but do not replace missing labels.

Retrain when eval shows: wrong hand, missed box during fast swing, vertical/diagonal flip,
tip off-screen, or saber hidden during rest/withdraw.

**Poses to add (positive ``lightsaber`` class — not ``other/`` negatives):**

- **Partial blade at frame edge** — tip at left/right/top border, grip in frame (wide
  ``strike_left`` / ``strike_right`` / ``strike_high`` extensions). ``edge_partial`` exists
  in ``MULTICOLOR_SHORT_SESSION`` but not ``REDTOY_SESSION``; move ``neg_partial`` out of
  ``other/`` — it currently teaches "no saber".
- **Centerline blocked END** — saber held at body midline after cross-body strike (centerline
  eval ``end_at_centerline`` poses).
- **Withdraw / retreat** — saber pulling back from centerline toward left or right hip (horizontal
  travel, often lower velocity — matches off-hand asymmetry failures).
- **Mid-swing motion** — not only END holds: 2–3 frames per swipe at ~30 fps during actual
  travel (motion blur OK).
- **Rest / hidden** — saber at hip, behind back, pointing down (``rest_start`` eval trials);
  label visible blade only or empty ``other/`` when fully hidden.
- **Off-center body** — already in ``var_off_center``; add more for laptop webcam FOV.
- **Two-hand vs one-hand** at diagonal angles (off-hand ``strike_right`` uses left arm).

**Labeling rules:** bbox over **visible blade only** (clip at frame edge). Prefer manual boxes
or Roboflow over HSV auto-label on partial reds. See ``SABER-TRAINING.md``, ``DIRECTIONS.md``.

**Model / runtime (after more data):**

- [x] Axis todos with presets — ``SABER-AXIS-TODO.md``, ``--saber-axis`` on preview/eval
- [ ] ``tip_in_frame`` / ``truncated`` on ``SaberLine``; down-weight fusion when tip extrapolated
- [ ] YOLO ``conf`` / ``iou`` tuned per profile; log ``yolo_hit`` vs ``arm`` in eval (``saber_source``)
- [ ] Consider OBB or keypoint head if axis-aligned bbox keeps mis-estimating diagonal blades
- [ ] Optional: disable ``_saber_from_arm`` tip when YOLO loaded (blade from object, grip from wrist)
- [ ] Train on eval failure clips exported from ``swing_eval_logs/videos/`` (hard negatives/positives)

Collect: ``python collect_saber_trainer.py --saber redtoy --camera laptop --interval 3``
Plan poses: ``saber_training_plan.py`` · Train: ``SABER-TRAINING.md``
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
SaberSource = Literal["arm", "yolo", "yolo_cached"]


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
    source: SaberSource = "arm"
    tip_in_frame: bool = True
    truncated: bool = False
    axis_method: str = "arm"

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
        self._yolo_frame = 0
        self._yolo_cache: list[SaberLine] = []
        self._yolo_bbox_by_hand: dict[Hand, tuple[int, int, int, int]] = {}
        self._axis_smooth: dict[Hand, tuple[float, float, float]] = {}
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
        if not sabers:
            return None
        for saber in sabers:
            if saber.source in ("yolo", "yolo_cached"):
                return saber
        return sabers[0]

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
            every = max(1, int(getattr(config, "SABER_YOLO_EVERY_N_FRAMES", 3)))
            yolo_conf = float(getattr(config, "SABER_YOLO_CONFIDENCE", 0.35))
            self._yolo_frame += 1
            if self._yolo_frame >= every or not self._yolo_cache:
                self._yolo_frame = 0
                candidates = self._merge_yolo(frame, candidates)
                self._yolo_cache = [
                    s
                    for s in candidates
                    if s.source in ("yolo", "yolo_cached")
                    and s.confidence >= yolo_conf
                ] or [
                    s for s in candidates if s.source in ("yolo", "yolo_cached")
                ]
            else:
                candidates = self._refresh_cached_yolo(frame, candidates, self._yolo_cache)

        def _sort_key(s: SaberLine) -> tuple[int, float]:
            rank = {"yolo": 2, "yolo_cached": 1, "arm": 0}.get(s.source, 0)
            return (rank, s.confidence)

        candidates.sort(key=_sort_key, reverse=True)
        return candidates

    def _refresh_cached_yolo(
        self,
        frame: Frame,
        arm_lines: list[SaberLine],
        cached: list[SaberLine],
    ) -> list[SaberLine]:
        """Reuse last YOLO blade axis; move grip with wrist and blend toward forearm."""
        if not cached:
            return arm_lines

        blend = float(getattr(config, "SABER_YOLO_CACHE_BLEND", 0.35))
        color_each = bool(getattr(config, "SABER_AXIS_COLOR_EACH_FRAME", False))
        out: list[SaberLine] = []
        used: set[int] = set()
        yolo_hands: set[Hand] = set()
        for cached_line in cached:
            match_idx = None
            for i, arm in enumerate(arm_lines):
                if i in used:
                    continue
                if arm.hand == cached_line.hand:
                    match_idx = i
                    break
            if match_idx is None:
                best_d = 1e9
                for i, arm in enumerate(arm_lines):
                    if i in used:
                        continue
                    d = math.hypot(
                        arm.grip_x - cached_line.grip_x,
                        arm.grip_y - cached_line.grip_y,
                    )
                    if d < best_d:
                        best_d = d
                        match_idx = i
            if match_idx is None:
                continue
            used.add(match_idx)
            arm = arm_lines[match_idx]
            yolo_hands.add(arm.hand)

            bbox = self._yolo_bbox_by_hand.get(arm.hand)
            if color_each and bbox is not None and frame is not None:
                built = self._build_yolo_line(
                    frame,
                    bbox,
                    arm,
                    cached_line.confidence,
                    source="yolo_cached",
                )
                if built is not None:
                    out.append(built)
                    continue

            cdx = cached_line.tip_x - cached_line.grip_x
            cdy = cached_line.tip_y - cached_line.grip_y
            clen = math.hypot(cdx, cdy) or 1.0
            adx = arm.tip_x - arm.grip_x
            ady = arm.tip_y - arm.grip_y
            alen = math.hypot(adx, ady) or 1.0
            ux = (1.0 - blend) * (cdx / clen) + blend * (adx / alen)
            uy = (1.0 - blend) * (cdy / clen) + blend * (ady / alen)
            ulen = math.hypot(ux, uy) or 1.0
            ux, uy = ux / ulen, uy / ulen
            length = max(clen, alen * 0.85)
            tip_x = int(arm.grip_x + ux * length)
            tip_y = int(arm.grip_y + uy * length)
            angle = math.degrees(math.atan2(tip_y - arm.grip_y, tip_x - arm.grip_x))
            out.append(
                SaberLine(
                    grip_x=arm.grip_x,
                    grip_y=arm.grip_y,
                    tip_x=tip_x,
                    tip_y=tip_y,
                    hand=arm.hand,
                    orientation=orientation_from_angle(angle),
                    confidence=cached_line.confidence,
                    source="yolo_cached",
                    tip_in_frame=cached_line.tip_in_frame,
                    truncated=cached_line.truncated,
                    axis_method=cached_line.axis_method,
                )
            )
        for arm in arm_lines:
            if arm.hand not in yolo_hands:
                out.append(arm)
        return out or arm_lines

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
            source="arm",
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

    @staticmethod
    def _tip_from_bbox(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        grip_x: int,
        grip_y: int,
        forearm_ux: float,
        forearm_uy: float,
    ) -> tuple[int, int] | None:
        """Tip = bbox corner farthest from grip, preferring forearm direction."""
        corners = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
        min_align = float(getattr(config, "SABER_YOLO_MIN_GRIP_ALIGN", -0.15))
        best_pt: tuple[int, int] | None = None
        best_score = -1.0
        for cx, cy in corners:
            dx, dy = cx - grip_x, cy - grip_y
            dist = math.hypot(dx, dy)
            if dist < 8:
                continue
            align = (dx * forearm_ux + dy * forearm_uy) / dist
            if align < min_align:
                continue
            score = dist * (0.35 + 0.65 * max(0.0, align))
            if score > best_score:
                best_score = score
                best_pt = (cx, cy)
        if best_pt is not None:
            return best_pt
        return max(corners, key=lambda p: math.hypot(p[0] - grip_x, p[1] - grip_y))

    @staticmethod
    def _axis_from_color_roi(
        frame: Frame,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        grip_x: int,
        grip_y: int,
        hint_ux: float,
        hint_uy: float,
    ) -> tuple[float, float, int, int, bool, bool] | None:
        """
        Fit blade axis from HSV pixels inside YOLO bbox (PCA).

        Returns (ux, uy, tip_x, tip_y, tip_in_frame, truncated) or None.
        """
        fh, fw = frame.shape[:2]
        pad = 2
        rx1 = max(0, x1 - pad)
        ry1 = max(0, y1 - pad)
        rx2 = min(fw, x2 + pad)
        ry2 = min(fh, y2 + pad)
        if rx2 <= rx1 or ry2 <= ry1:
            return None

        roi = frame[ry1:ry2, rx1:rx2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = SaberDetector._color_mask(hsv)
        min_pixels = int(getattr(config, "SABER_MIN_COLOR_PIXELS", 20))
        if mask is None or cv2.countNonZero(mask) < min_pixels:
            return None

        ys, xs = np.where(mask > 0)
        coords = np.column_stack([xs.astype(np.float64) + rx1, ys.astype(np.float64) + ry1])
        if len(coords) < min_pixels:
            return None

        centered = coords - coords.mean(axis=0)
        if centered.shape[0] < 2:
            return None
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        axis = vt[0]
        if axis[0] * hint_ux + axis[1] * hint_uy < 0:
            axis = -axis
        norm = math.hypot(float(axis[0]), float(axis[1])) or 1.0
        ux, uy = float(axis[0] / norm), float(axis[1] / norm)

        grip = np.array([grip_x, grip_y], dtype=np.float64)
        rel = (coords - grip) @ np.array([ux, uy])
        in_bounds = (
            (coords[:, 0] >= 0)
            & (coords[:, 0] < fw)
            & (coords[:, 1] >= 0)
            & (coords[:, 1] < fh)
        )
        use = coords[in_bounds] if bool(getattr(config, "SABER_AXIS_TIP_IN_FRAME", False)) and in_bounds.any() else coords
        rel_use = (use - grip) @ np.array([ux, uy])
        tip_idx = int(np.argmax(rel_use))
        tip_x, tip_y = int(use[tip_idx, 0]), int(use[tip_idx, 1])
        tip_in_frame = 0 <= tip_x < fw and 0 <= tip_y < fh
        truncated = bool(in_bounds.any() and (~in_bounds).any())
        return ux, uy, tip_x, tip_y, tip_in_frame, truncated

    def _smooth_axis(
        self, hand: Hand, ux: float, uy: float, length: float
    ) -> tuple[float, float, float]:
        if not getattr(config, "SABER_AXIS_TEMPORAL", False):
            return ux, uy, length
        alpha = float(getattr(config, "SABER_AXIS_SMOOTH_ALPHA", 0.45))
        prev = self._axis_smooth.get(hand)
        if prev is None:
            self._axis_smooth[hand] = (ux, uy, length)
            return ux, uy, length
        pux, puy, plen = prev
        if pux * ux + puy * uy < 0:
            ux, uy = -ux, -uy
        sux = (1.0 - alpha) * pux + alpha * ux
        suy = (1.0 - alpha) * puy + alpha * uy
        slen = (1.0 - alpha) * plen + alpha * length
        ulen = math.hypot(sux, suy) or 1.0
        sux, suy = sux / ulen, suy / ulen
        self._axis_smooth[hand] = (sux, suy, slen)
        return sux, suy, slen

    def _build_yolo_line(
        self,
        frame: Frame,
        bbox: tuple[int, int, int, int],
        arm: SaberLine,
        confidence: float,
        *,
        source: SaberSource,
    ) -> SaberLine | None:
        x1, y1, x2, y2 = bbox
        fdx = arm.tip_x - arm.grip_x
        fdy = arm.tip_y - arm.grip_y
        flen = math.hypot(fdx, fdy) or 1.0
        hint_ux, hint_uy = fdx / flen, fdy / flen

        axis_method = "bbox"
        tip_in_frame = True
        truncated = False
        tip_x: int
        tip_y: int

        color_fit = None
        if getattr(config, "SABER_AXIS_COLOR_ROI", False) or getattr(
            config, "SABER_AXIS_COLOR_EACH_FRAME", False
        ):
            color_fit = self._axis_from_color_roi(
                frame, x1, y1, x2, y2, arm.grip_x, arm.grip_y, hint_ux, hint_uy
            )

        if color_fit is not None:
            ux, uy, tip_x, tip_y, tip_in_frame, truncated = color_fit
            axis_method = "color_pca"
            length = math.hypot(tip_x - arm.grip_x, tip_y - arm.grip_y)
        else:
            tip_pt = self._tip_from_bbox(
                x1, y1, x2, y2, arm.grip_x, arm.grip_y, hint_ux, hint_uy
            )
            if tip_pt is None:
                return None
            tip_x, tip_y = tip_pt
            if config.SABER_USE_COLOR_TIP:
                refined = self._refine_tip_with_color(
                    frame, arm.grip_x, arm.grip_y, tip_x, tip_y
                )
                if refined is not None:
                    tip_x, tip_y = refined
                    axis_method = "bbox+color_tip"
            length = math.hypot(tip_x - arm.grip_x, tip_y - arm.grip_y)
            fh, fw = frame.shape[:2]
            tip_in_frame = 0 <= tip_x < fw and 0 <= tip_y < fh
            ux = (tip_x - arm.grip_x) / max(length, 1.0)
            uy = (tip_y - arm.grip_y) / max(length, 1.0)

        ux, uy, length = self._smooth_axis(arm.hand, ux, uy, max(length, 1.0))
        tip_x = int(arm.grip_x + ux * length)
        tip_y = int(arm.grip_y + uy * length)
        fh, fw = frame.shape[:2]
        if getattr(config, "SABER_AXIS_TIP_IN_FRAME", False):
            tip_in_frame = 0 <= tip_x < fw and 0 <= tip_y < fh

        angle = math.degrees(math.atan2(tip_y - arm.grip_y, tip_x - arm.grip_x))
        return SaberLine(
            grip_x=arm.grip_x,
            grip_y=arm.grip_y,
            tip_x=tip_x,
            tip_y=tip_y,
            hand=arm.hand,
            orientation=orientation_from_angle(angle),
            confidence=confidence,
            source=source,
            tip_in_frame=tip_in_frame,
            truncated=truncated,
            axis_method=axis_method,
        )

    def _merge_yolo(self, frame: Frame, arm_lines: list[SaberLine]) -> list[SaberLine]:
        """Snap YOLO bbox blade axis to nearest wrist; keep arm fallback per hand."""
        conf = float(getattr(config, "SABER_YOLO_CONFIDENCE", 0.35))
        results = self._yolo(frame, verbose=False, conf=conf)[0]
        if not results.boxes:
            return arm_lines

        yolo_by_hand: dict[Hand, SaberLine] = {}
        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            nearest = None
            best_d = 1e9
            for s in arm_lines:
                d = math.hypot(s.grip_x - cx, s.grip_y - cy)
                if d < best_d:
                    best_d = d
                    nearest = s
            if nearest is None or best_d > config.SABER_YOLO_MAX_GRIP_DIST_PX:
                continue

            bbox = (x1, y1, x2, y2)
            line = self._build_yolo_line(
                frame,
                bbox,
                nearest,
                float(box.conf[0]),
                source="yolo",
            )
            if line is None:
                continue
            yolo_by_hand[nearest.hand] = line
            self._yolo_bbox_by_hand[nearest.hand] = bbox

        if not yolo_by_hand:
            return arm_lines

        out: list[SaberLine] = []
        for arm in arm_lines:
            out.append(yolo_by_hand.get(arm.hand, arm))
        return out

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
    if saber.source != "arm":
        label += f" [{saber.source}]"
    if saber.axis_method not in ("arm", ""):
        label += f" {saber.axis_method}"
    if saber.truncated or not saber.tip_in_frame:
        label += " trunc"
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
