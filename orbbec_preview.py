"""RGB-D preview for Orbbec SDK development (optional hardware)."""

from __future__ import annotations

import time

import cv2

import config
from orbbec_depth import DepthAttackHints
from orbbec_frames import render_depth_preview
from orbbec_sdk import install_hint, sdk_available


def _run_preview() -> None:
    if not sdk_available():
        print(install_hint())
        return

    from orbbec_camera import OrbbecCamera

    cam = OrbbecCamera()
    t_prev = time.monotonic()
    print("Orbbec preview — color | depth. Press 'q' to quit.")

    try:
        while True:
            fs = cam.read_frameset()
            if fs is None or fs.color is None:
                continue

            now = time.monotonic()
            fps = 1.0 / max(now - t_prev, 1e-6)
            t_prev = now

            color = fs.color.copy()
            hints = DepthAttackHints.from_frames(fs.depth_mm)
            cv2.putText(
                color,
                f"fps {fps:.1f}  lunge={hints.lunge_toward_camera}  overhead={hints.overhead_depth_spike}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 120),
                2,
            )

            if fs.depth_mm is not None:
                depth_vis = render_depth_preview(
                    fs.depth_mm,
                    min_mm=config.ORBBEC_DEPTH_MIN_MM,
                    max_mm=config.ORBBEC_DEPTH_MAX_MM,
                )
                h = color.shape[0]
                depth_vis = cv2.resize(depth_vis, (color.shape[1], h))
                combined = cv2.hconcat([color, depth_vis])
            else:
                combined = color

            cv2.imshow("Orbbec Preview", combined)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    _run_preview()
