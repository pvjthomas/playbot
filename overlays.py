"""Developer 1 — draw HUD on preview frames."""

import cv2
import mediapipe as mp

from contracts import AttackDirection, Frame

_DRAW = mp.solutions.drawing_utils
_DRAW_STYLE = mp.solutions.drawing_styles
_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS

# BGR colors per attack direction
DIRECTION_COLORS: dict[AttackDirection, tuple[int, int, int]] = {
    "none": (160, 160, 160),
    "left": (255, 120, 0),
    "right": (0, 120, 255),
    "high": (0, 255, 255),
    "low": (255, 0, 180),
    "center": (0, 255, 120),
}


class AttackOverlay:
    def render(
        self,
        frame: Frame,
        direction: AttackDirection,
        *,
        fps: float | None = None,
        pose=None,
        robot_pose: str | None = None,
    ) -> Frame:
        out = frame.copy()
        color = DIRECTION_COLORS.get(direction, (200, 200, 200))

        if pose is not None:
            _DRAW.draw_landmarks(
                out,
                pose,
                _CONNECTIONS,
                landmark_drawing_spec=_DRAW_STYLE.get_default_pose_landmarks_style(),
            )

        label = f"attack: {direction}"
        cv2.putText(out, label, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        if fps is not None:
            cv2.putText(
                out,
                f"fps: {fps:.0f}",
                (12, 64),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (200, 200, 200),
                2,
            )

        if robot_pose:
            cv2.putText(
                out,
                f"robot: {robot_pose}",
                (12, 96),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2,
            )

        return out
