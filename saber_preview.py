"""
Saber detection preview — body-attached grip→tip, not wired to main fight loop.

Run (MacBook webcam + red toy saber):
  cd projects/lightsaber
  source .venv/bin/activate
  python saber_preview.py --saber redtoy --camera laptop
  python saber_preview.py --saber redtoy --detector yolo --camera laptop --saber-axis all

Keys:
  q — quit
  m — toggle color mask debug
"""

from __future__ import annotations

import argparse
import time

import cv2

import config
from camera import add_camera_cli, configure_camera_from_args, open_camera
from color_saber_detector import ColorSaberDetector, calibration_path
from overlays import AttackOverlay
from saber_axis_flags import apply_axis_preset, list_axis_presets
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
    parser.add_argument(
        "--detector",
        choices=("legacy", "yolo", "color"),
        default="legacy",
        help="legacy/yolo = saber_detector; color = calibrated HSV",
    )
    parser.add_argument(
        "--saber-axis",
        default="1_color_roi",
        metavar="PRESET",
        help="Axis todos: " + ", ".join(list_axis_presets()) + " — SABER-AXIS-TODO.md",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    if args.camera is None:
        config.CAMERA_SOURCE = "laptop"
    profile = apply_saber_profile(args.saber)
    enabled = apply_axis_preset(args.saber_axis)

    camera = open_camera()
    vision = AttackVision()
    color_det = None
    saber_det = None
    if args.detector == "color":
        if not calibration_path(args.saber).is_file():
            raise SystemExit(
                f"Missing color calibration. Run: python calibrate_saber_color.py --saber {args.saber}"
            )
        color_det = ColorSaberDetector(args.saber)
    else:
        saber_det = SaberDetector()

    overlay = AttackOverlay()
    t_prev = time.monotonic()
    show_mask = False

    print(
        f"Saber preview — profile={profile!r}, detector={args.detector}, "
        f"axis={args.saber_axis!r}, camera={config.CAMERA_SOURCE!r}"
    )
    if enabled:
        print(f"  axis flags: {', '.join(enabled)}")
    print("Keys: q=quit  m=toggle color mask debug")

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

            if color_det is not None:
                primary = color_det.detect_saber(frame, landmarks)
                sabers = [primary] if primary else []
            else:
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
                if color_det is not None:
                    mask_vis = color_det.debug_mask(frame, landmarks)
                else:
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
        if saber_det is not None:
            saber_det.close()
        if color_det is not None:
            color_det.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
