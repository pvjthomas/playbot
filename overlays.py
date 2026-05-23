"""Developer 1 — draw HUD on preview frames."""

import cv2
import mediapipe as mp

from contracts import AttackDirection, Frame, OverlayRenderer

_DRAW = mp.solutions.drawing_utils
_DRAW_STYLE = mp.solutions.drawing_styles
_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS


class AttackOverlay:
    """Implements OverlayRenderer."""

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

        if pose is not None:
            _DRAW.draw_landmarks(
                out,
                pose,
                _CONNECTIONS,
                landmark_drawing_spec=_DRAW_STYLE.get_default_pose_landmarks_style(),
            )

        if direction == "none":
            label, color = "attack: none", (160, 160, 160)
        else:
            label, color = f"attack: {direction}", (0, 200, 255)

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
