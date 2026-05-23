"""
Collect saber training images — hold prop in different orientations.

Run:
  cd projects/lightsaber
  source .venv/bin/activate
  python collect_saber_data.py --saber redtoy --camera laptop

Keys:
  h — save as horizontal
  v — save as vertical
  d — save as diagonal
  o — save as other (or saber not visible / bad pose)
  q — quit

Images → ../models/saber_dataset/raw/<saber>/<label>/
Use for Roboflow / YOLO train later (see task-vision.md).
"""

import argparse
import time
from pathlib import Path

import cv2

from camera import add_camera_cli, configure_camera_from_args, open_camera
from overlays import AttackOverlay
from saber_detector import SaberDetector, draw_saber_overlay
from saber_profiles import apply_saber_profile
from vision import AttackVision

DATASET_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "raw"
LABELS = ("horizontal", "vertical", "diagonal", "other")
KEY_TO_LABEL = {ord("h"): "horizontal", ord("v"): "vertical", ord("d"): "diagonal", ord("o"): "other"}


def parse_args():
    p = argparse.ArgumentParser(description="Collect saber images for YOLO training")
    add_camera_cli(p)
    p.add_argument(
        "--saber",
        default="redtoy",
        help="Saber id for folder layout (default: redtoy)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    apply_saber_profile(args.saber)
    saber_id = args.saber.strip().replace("/", "_")
    dataset_root = DATASET_BASE / saber_id

    for label in LABELS:
        (dataset_root / label).mkdir(parents=True, exist_ok=True)

    camera = open_camera()
    vision = AttackVision()
    saber_det = SaberDetector()
    overlay = AttackOverlay()
    print(f"Saber dataset collector — {saber_id}")
    print("Save raw frames for YOLO. Green overlay is pose-only (often wrong); ignore it.")
    print("Keys: h=horizontal v=vertical d=diagonal o=other q=quit")
    print(f"Saving to: {dataset_root}")

    count = {label: 0 for label in LABELS}
    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue

            direction = vision.detect_attack(frame)
            landmarks = vision.last_landmarks
            sabers = saber_det.detect_all(frame, landmarks)
            preview = overlay.render_with_saber(
                frame, direction, sabers[0] if sabers else None, pose=landmarks
            )
            for extra in sabers[1:]:
                preview = draw_saber_overlay(preview, extra)
            cv2.putText(
                preview,
                "h horiz | v vert | d diag | o other | q quit",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )
            for i, label in enumerate(LABELS):
                cv2.putText(
                    preview,
                    f"{label}: {count[label]}",
                    (12, 55 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (200, 200, 200),
                    1,
                )
            cv2.imshow("Collect Saber Data", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key not in KEY_TO_LABEL:
                continue

            label = KEY_TO_LABEL[key]
            count[label] += 1
            ts = int(time.time() * 1000)
            path = dataset_root / label / f"{saber_id}_{label}_{ts}.jpg"
            cv2.imwrite(str(path), frame)
            print(f"saved {path.name} ({label}, total={count[label]})")
    finally:
        vision.close()
        saber_det.close()
        camera.release()
        cv2.destroyAllWindows()
        print("Done.", dict(count))


if __name__ == "__main__":
    main()
