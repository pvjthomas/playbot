"""
Calibrate whether the camera preview is horizontally mirrored (selfie flip).

Run:
  cd projects/lightsaber
  source .venv/bin/activate
  python camera_calibrate_mirror.py --camera laptop

Hold your anatomical RIGHT hand up (keep left arm down). Press SPACE when ready,
or wait for auto-detect. Result saved to camera_mirror.json.

Keys:
  SPACE — capture / re-run detection
  y     — confirm suggested setting
  n     — flip suggestion (manual override)
  q     — quit without saving
"""

from __future__ import annotations

import argparse
import time

import cv2
import mediapipe as mp

import config
from camera import add_camera_cli, configure_camera_from_args, open_camera
from camera_mirror import (
    active_camera_source_key,
    detect_mirror_from_landmarks,
    image_direction_cheat_sheet,
    save_mirror_preview,
)

_SAMPLES = 15


def parse_args():
    p = argparse.ArgumentParser(description="Calibrate camera mirror (right hand up)")
    add_camera_cli(p)
    p.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect when pose is stable (no SPACE needed)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    if args.camera is None:
        config.CAMERA_SOURCE = "laptop"

    source_key = active_camera_source_key()
    camera = open_camera()
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    print(f"Mirror calibration — source={source_key!r}")
    print("Raise your anatomical RIGHT hand. Keep LEFT arm at your side.")
    print("SPACE=detect  y=save  n=toggle mirror/non-mirror  q=quit")
    print()

    suggested: bool | None = None
    confidence = 0.0
    last_detect = 0.0
    user_choice: bool | None = None

    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            lm = result.pose_landmarks

            preview = frame.copy()
            if lm is not None:
                mp.solutions.drawing_utils.draw_landmarks(
                    preview,
                    lm,
                    mp.solutions.pose.POSE_CONNECTIONS,
                )

            cv2.putText(
                preview,
                "Raise RIGHT hand only (left arm down)",
                (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 200),
                2,
            )

            if suggested is None:
                hint = "Detecting... hold right hand up, then SPACE"
            else:
                mode = "MIRROR/selfie" if suggested else "TRUE camera (not mirrored)"
                hint = f"Detected: {mode} ({confidence:.0%} confidence)"
            cv2.putText(
                preview,
                hint,
                (12, 64),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cheat = image_direction_cheat_sheet(user_choice if user_choice is not None else suggested)
            cv2.putText(
                preview,
                cheat[:90],
                (12, 92),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (200, 200, 200),
                1,
            )
            cv2.putText(
                preview,
                "SPACE=detect  y=save  n=toggle  q=quit",
                (12, preview.shape[0] - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 200),
                2,
            )

            cv2.imshow("Mirror calibration", preview)
            key = cv2.waitKey(1) & 0xFF

            now = time.monotonic()
            if args.auto and lm is not None and now - last_detect > 0.2:
                vote = detect_mirror_from_landmarks(lm)
                if vote is not None:
                    samples = []
                    for _ in range(_SAMPLES):
                        f2 = camera.read_frame()
                        if f2 is None:
                            continue
                        r2 = pose.process(cv2.cvtColor(f2, cv2.COLOR_BGR2RGB))
                        if r2.pose_landmarks:
                            v = detect_mirror_from_landmarks(r2.pose_landmarks)
                            if v is not None:
                                samples.append(v)
                    if len(samples) >= 5:
                        suggested = sum(samples) > len(samples) / 2
                        confidence = max(sum(samples), len(samples) - sum(samples)) / len(samples)
                        last_detect = now

            if key == ord("q"):
                break
            if key == ord(" ") or key == ord("s"):
                samples = []
                for _ in range(_SAMPLES):
                    f2 = camera.read_frame()
                    if f2 is None:
                        continue
                    r2 = pose.process(cv2.cvtColor(f2, cv2.COLOR_BGR2RGB))
                    if r2.pose_landmarks:
                        v = detect_mirror_from_landmarks(r2.pose_landmarks)
                        if v is not None:
                            samples.append(v)
                if not samples:
                    print("Could not detect — right hand clearly up, left down?")
                    continue
                suggested = sum(samples) > len(samples) / 2
                confidence = max(sum(samples), len(samples) - sum(samples)) / len(samples)
                user_choice = suggested
                print(f"Detection: mirror_preview={suggested} ({confidence:.0%})")
            if key == ord("n") and suggested is not None:
                user_choice = not (user_choice if user_choice is not None else suggested)
                print(f"Toggled to mirror_preview={user_choice}")
            if key == ord("y"):
                final = user_choice if user_choice is not None else suggested
                if final is None:
                    print("Detect first (SPACE) or use --auto")
                    continue
                save_mirror_preview(
                    source_key,
                    final,
                    note="right-hand-up calibration",
                )
                print(image_direction_cheat_sheet(final))
                break
    finally:
        pose.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
