"""Developer 1 — attack detection. Exposes detect_attack(frame)."""

import itertools
import time

import cv2
import mediapipe as mp

import config
from contracts import AttackDirection, AttackDetector, Frame

_NOSE = 0
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_WRIST = 15
_RIGHT_WRIST = 16

_FAKE_SEQUENCE: list[AttackDirection] = [
    "none",
    "left",
    "right",
    "high",
    "center",
    "none",
]


class AttackVision:
    """MediaPipe pose → AttackDirection. Implements AttackDetector."""

    def __init__(
        self,
        high_margin: float = 0.06,
        side_margin: float = 0.12,
        extension_min: float = 0.18,
    ):
        self.high_margin = high_margin
        self.side_margin = side_margin
        self.extension_min = extension_min
        self._last_landmarks = None
        self._pose = None
        self._fake_cycle = itertools.cycle(_FAKE_SEQUENCE)
        self._fake_next_at = time.monotonic()
        self._fake_current: AttackDirection = "none"

        if not config.USE_FAKE_ATTACKS:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def detect_attack(self, frame: Frame) -> AttackDirection:
        if config.USE_FAKE_ATTACKS:
            return self._fake_attack()
        return self._mediapipe_attack(frame)

    def _fake_attack(self) -> AttackDirection:
        now = time.monotonic()
        if now >= self._fake_next_at:
            self._fake_current = next(self._fake_cycle)
            self._fake_next_at = now + config.FAKE_ATTACK_CYCLE_SEC
        return self._fake_current

    def _mediapipe_attack(self, frame: Frame) -> AttackDirection:
        if self._pose is None:
            return "none"

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        self._last_landmarks = result.pose_landmarks

        if not result.pose_landmarks:
            return "none"

        return self._classify(result.pose_landmarks.landmark)

    def _classify(self, landmarks) -> AttackDirection:
        ls = landmarks[_LEFT_SHOULDER]
        rs = landmarks[_RIGHT_SHOULDER]
        lw = landmarks[_LEFT_WRIST]
        rw = landmarks[_RIGHT_WRIST]

        center_x = (ls.x + rs.x) / 2
        shoulder_y = min(ls.y, rs.y)

        left_reach = self._dist(lw, ls)
        right_reach = self._dist(rw, rs)
        if max(left_reach, right_reach) < self.extension_min:
            return "none"

        if lw.y < shoulder_y - self.high_margin or rw.y < shoulder_y - self.high_margin:
            return "high"

        if rw.x < center_x - self.side_margin and right_reach >= self.extension_min:
            return "left"

        if lw.x > center_x + self.side_margin and left_reach >= self.extension_min:
            return "right"

        # Stub: low/center — extend with hip/knee landmarks later
        if abs(lw.x - center_x) < self.side_margin * 0.5:
            return "center"

        return "none"

    @property
    def last_landmarks(self):
        return self._last_landmarks

    @staticmethod
    def _dist(a, b) -> float:
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def close(self):
        if self._pose is not None:
            self._pose.close()


def detect_attack(frame: Frame) -> AttackDirection:
    """Module-level helper — prefer AttackVision instance in main loop."""
    detector = AttackVision()
    try:
        return detector.detect_attack(frame)
    finally:
        detector.close()
