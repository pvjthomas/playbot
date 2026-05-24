"""
Interactive wrist / Orbbec orientation calibration.

Robot at guard (or --reference-pose); partner in frame. Adjust rotation/flips until
image axes match directions.py, then save.

  python camera_calibrate_orientation.py --camera piper
  python camera_calibrate_orientation.py --camera piper --mount toward_partner

Keys: r/R rotate CW/CCW  f/F flip H  v/V flip V  m cycle mount  y save  q quit
"""

from __future__ import annotations

import argparse
import sys

import cv2

import config
from camera import add_camera_args, configure_camera_from_args, open_camera
from camera_orientation import (
    MountFacing,
    OrientationCalibration,
    orientation_cheat_sheet,
    save_orientation,
    suggest_calibration_steps,
)


def _parse_mount(text: str) -> MountFacing:
    try:
        return MountFacing(text.strip().lower())
    except ValueError:
        return MountFacing.UNKNOWN


def main() -> int:
    p = argparse.ArgumentParser(description="Calibrate wrist camera rotation / flip")
    add_camera_args(p)
    p.add_argument(
        "--reference-pose",
        default="GUARD_CENTER",
        help="Robot pose name used during calibration (documentation only in v1)",
    )
    p.add_argument(
        "--mount",
        default="unknown",
        choices=[m.value for m in MountFacing],
        help="Lens facing when arm is in reference pose",
    )
    args = p.parse_args()
    configure_camera_from_args(args)

    mount = _parse_mount(args.mount)
    cal = OrientationCalibration(
        reference_pose=args.reference_pose,
        mount_facing=mount,
    )
    source = getattr(config, "CAMERA_SOURCE", "piper")

    print("--- Calibration checklist ---")
    for line in suggest_calibration_steps(mount):
        print(f"  • {line}")
    print("Keys: r/R rotate  f/F flipH  v/V flipV  m mount  y save  q quit")
    print(orientation_cheat_sheet(source))

    cam = open_camera()
    try:
        while True:
            frame = cam.read_frame()
            if frame is None:
                continue
            from camera_orientation import apply_orientation_transform

            preview = apply_orientation_transform(frame, cal)
            hud = orientation_cheat_sheet(source)
            cv2.putText(
                preview,
                f"rot={cal.rotation_deg} fh={cal.flip_h} fv={cal.flip_v} mount={cal.mount_facing.value}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                preview,
                hud[:90],
                (12, 56),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (200, 200, 200),
                1,
            )
            cv2.imshow("Calibrate orientation (preview = corrected)", preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                cal.rotation_deg = {0: 90, 90: 180, 180: 270, 270: 0}[cal.rotation_deg]
            elif key == ord("R"):
                cal.rotation_deg = {0: 270, 270: 180, 180: 90, 90: 0}[cal.rotation_deg]
            elif key == ord("f"):
                cal.flip_h = not cal.flip_h
            elif key == ord("v"):
                cal.flip_v = not cal.flip_v
            elif key == ord("m"):
                order = list(MountFacing)
                idx = order.index(cal.mount_facing)
                cal.mount_facing = order[(idx + 1) % len(order)]
            elif key == ord("y"):
                save_orientation(source, cal)
                print("Saved. Set CAMERA_APPLY_ORIENTATION_CORRECTION = True in config.py")
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
