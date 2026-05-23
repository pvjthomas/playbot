"""
Saber detection preview — body-attached grip→tip, not wired to main fight loop.

Run (MacBook webcam + red toy saber):
  cd projects/lightsaber
  source .venv/bin/activate
  python saber_preview.py --saber redtoy --camera laptop

Keys:
  q — quit
  m — toggle color mask debug (tune red HSV for redtoy)
"""

from __future__ import annotations

import argparse
import time

import cv2

import config
from camera import add_camera_cli, configure_camera_from_args, open_camera
from overlays import AttackOverlay
from saber_detector import SaberDetector, draw_saber_overlay
from saber_profiles import apply_saber_profile, list_profiles
from vision import AttackVision


def parse_args():
    parser = argparse.ArgumentParser(description="Saber grip→tip preview")
    add_camera_cli(parser)
    parser.add_argument(
        "--saber",
        default="redtoy",
        help=f"Saber profile ({', '.join(list_profiles())}); default: redtoy",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    if args.camera is None:
        config.CAMERA_SOURCE = "laptop"
    profile = apply_saber_profile(args.saber)

    camera = open_camera()
    vision = AttackVision()
    saber_det = SaberDetector()
    overlay = AttackOverlay()
    t_prev = time.monotonic()
    show_mask = False

    print(f"Saber preview — profile={profile!r}, camera={config.CAMERA_SOURCE!r}")
    print("Hold saber in different orientations. Grip at wrist, blade along forearm.")
    print("Keys: q=quit  m=toggle red color mask (debug HSV)")

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

            for extra in sabers[1:]:
                preview = draw_saber_overlay(preview, extra)

            if show_mask:
                mask_vis = SaberDetector.color_debug_mask(frame)
                if mask_vis is not None:
                    h = preview.shape[0]
                    mask_vis = cv2.resize(mask_vis, (preview.shape[1], h))
                    preview = cv2.vconcat([preview, mask_vis])

            cv2.imshow("Saber Preview", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("m"):
                show_mask = not show_mask
                print(f"color mask debug: {'on' if show_mask else 'off'}")
    finally:
        vision.close()
        saber_det.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
