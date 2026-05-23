"""
Developer 1 — attack detection. Exposes detect_attack(frame).

Strike directions (partner faces the webcam)
------------------------------------------------
All labels describe the *partner in frame* — the person the camera sees.
The PiPER arm blocks as if standing behind the camera, facing the partner.

  none   — No attack. Arms relaxed at sides, or pose not tracked.

  left   — Partner's right arm crosses toward the LEFT side of the image
           (a strike coming from your right-hand side toward your left).
           Detection: right wrist past body center, extended.

  right  — Partner's left arm crosses toward the RIGHT side of the image
           (a strike coming from your left-hand side toward your right).
           Detection: left wrist past body center, extended.

  high   — Overhead strike. Either wrist rises clearly above the shoulders
           (downward chop or overhead swing at the robot).
           Detection: wrist y above shoulder line.

  center — Straight-on threat: BOTH hands extended near the body's midline,
           aimed at the camera (thrust, push, or two-hand lunge — not a
           side swipe). Robot responds with GUARD_CENTER, not a side block.
           Detection: both wrists near center_x, arms extended.
           Tip: stand square to the camera, punch forward with both hands
           near your chest line — not the same as left/right.

  low    — Not implemented yet (planned: wrist below hips / waist strike).
           Always returns "none" for now.

Tuning (config.py):
  HIGH_MARGIN, SIDE_MARGIN, EXTENSION_MIN — see _classify() below.

Run vision-only preview:
  python vision.py
"""

# Quick reference for overlays / logs (same meanings as module doc above)
ATTACK_MEANINGS: dict[str, str] = {
    "none": "no attack — arms down or untracked",
    "left": "cross-body strike from partner's right arm → image left",
    "right": "cross-body strike from partner's left arm → image right",
    "high": "overhead — wrist above shoulders",
    "center": "straight thrust — both hands extended at body center",
    "low": "(not implemented) low line strike toward waist",
}

import itertools
import time

import cv2
import mediapipe as mp

import config
from contracts import AttackDirection, Frame

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
        high_margin: float | None = None,
        side_margin: float | None = None,
        extension_min: float | None = None,
    ):
        self.high_margin = config.HIGH_MARGIN if high_margin is None else high_margin
        self.side_margin = config.SIDE_MARGIN if side_margin is None else side_margin
        self.extension_min = (
            config.EXTENSION_MIN if extension_min is None else extension_min
        )
        self._last_landmarks = None
        self._last_direction: AttackDirection = "none"
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
            self._last_direction = self._fake_attack()
            return self._last_direction

        direction = self._mediapipe_attack(frame)
        self._last_direction = direction
        return direction

    @property
    def last_direction(self) -> AttackDirection:
        return self._last_direction

    def _fake_attack(self) -> AttackDirection:
        now = time.monotonic()
        if now >= self._fake_next_at:
            self._fake_current = next(self._fake_cycle)
            self._fake_next_at = now + config.FAKE_ATTACK_CYCLE_SEC
        return self._fake_current

    def _mediapipe_attack(self, frame: Frame) -> AttackDirection:
        if self._pose is None or frame is None:
            return "none"

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        self._last_landmarks = result.pose_landmarks

        if not result.pose_landmarks:
            return "none"

        return self._classify(result.pose_landmarks.landmark)

    def _classify(self, landmarks) -> AttackDirection:
        """
        Priority: none → high → left/right (side) → center (straight) → none.

        See module docstring for what each direction means to the robot.
        """
        ls = landmarks[_LEFT_SHOULDER]
        rs = landmarks[_RIGHT_SHOULDER]
        lw = landmarks[_LEFT_WRIST]
        rw = landmarks[_RIGHT_WRIST]

        center_x = (ls.x + rs.x) / 2
        shoulder_y = min(ls.y, rs.y)

        left_reach = self._dist(lw, ls)
        right_reach = self._dist(rw, rs)
        if max(left_reach, right_reach) < self.extension_min:
            return "none"  # arms at rest

        # high — overhead (see ATTACK_MEANINGS["high"])
        if lw.y < shoulder_y - self.high_margin or rw.y < shoulder_y - self.high_margin:
            return "high"

        # left — partner's right arm crosses to image-left
        if rw.x < center_x - self.side_margin and right_reach >= self.extension_min:
            return "left"

        # right — partner's left arm crosses to image-right
        if lw.x > center_x + self.side_margin and left_reach >= self.extension_min:
            return "right"

        # center — straight thrust: both wrists near midline, extended forward
        # (not a side swipe; triggers GUARD_CENTER on the robot)
        center_band = self.side_margin * 0.4
        if (
            abs(lw.x - center_x) < center_band
            and abs(rw.x - center_x) < center_band
            and left_reach >= self.extension_min * 0.8
            and right_reach >= self.extension_min * 0.8
        ):
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


def _run_vision_preview():
    """Vision-only loop — use while working on feature/vision branch."""
    from camera import Camera
    from overlays import AttackOverlay

    camera = Camera()
    detector = AttackVision()
    overlay = AttackOverlay()
    t_prev = time.monotonic()

    print("Vision preview — mock slow strikes. Press 'q' to quit.")
    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue

            now = time.monotonic()
            fps = 1.0 / max(now - t_prev, 1e-6)
            t_prev = now

            direction = detector.detect_attack(frame)
            preview = overlay.render(
                frame,
                direction,
                fps=fps,
                pose=detector.last_landmarks,
            )
            cv2.imshow("Vision Dev Preview", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        detector.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    _run_vision_preview()
