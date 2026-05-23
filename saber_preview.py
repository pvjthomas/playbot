"""
Saber detection preview — body-attached grip→tip, not wired to main fight loop.

Run:
  cd projects/lightsaber
  source .venv/bin/activate
  python saber_preview.py

Shows:
  - MediaPipe skeleton
  - Green line: wrist (grip) → tip along forearm
  - Label: horizontal | vertical | diagonal

Collect training images: python collect_saber_data.py
"""

import time

import cv2

from camera import Camera
from overlays import AttackOverlay
from saber_detector import SaberDetector
from vision import AttackVision


def main():
    camera = Camera()
    vision = AttackVision()
    saber_det = SaberDetector()
    overlay = AttackOverlay()
    t_prev = time.monotonic()

    print("Saber preview — hold saber in different orientations.")
    print("Grip at wrist, blade along forearm. Press 'q' to quit.")

    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue

            now = time.monotonic()
            fps = 1.0 / max(now - t_prev, 1e-6)
            t_prev = now

            direction = vision.detect_attack(frame)
            landmarks = vision.last_landmarks
            sabers = saber_det.detect_all(frame, landmarks)
            primary = sabers[0] if sabers else None

            preview = overlay.render_with_saber(
                frame,
                direction,
                primary,
                fps=fps,
                pose=landmarks,
            )

            if len(sabers) > 1:
                from saber_detector import draw_saber_overlay

                for extra in sabers[1:]:
                    preview = draw_saber_overlay(preview, extra)

            cv2.imshow("Saber Preview", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        vision.close()
        saber_det.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
