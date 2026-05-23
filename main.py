"""
Developer 3 — app entry point.

Wires vision → robot through contracts only.

Run:
    cd projects/lightsaber
    source .venv/bin/activate
    python main.py
    python main.py --camera piper    # Piper on Mac (correct Dabai, auto → ffmpeg)
    python main.py --camera laptop   # MacBook webcam (fast dev)

    See README.md § Camera for full command list.

Keys: q=quit  e=emergency stop  h=home
"""

import argparse
import time

import cv2

import config
from camera import Camera, add_camera_cli, configure_camera_from_args
from contracts import AttackDirection
from dashboard import ConsoleDashboard
from overlays import AttackOverlay
from robot import PiperRobot
from safety import SafetyGuard
from sounds import SoundEngine
from vision import AttackVision


def main():
    parser = argparse.ArgumentParser(description="AI Lightsaber Trainer")
    add_camera_cli(parser)
    args = parser.parse_args()
    configure_camera_from_args(args)

    camera = Camera()
    vision = AttackVision()
    overlay = AttackOverlay()
    safety = SafetyGuard()
    robot = PiperRobot(safety=safety)
    sounds = SoundEngine()
    dashboard = ConsoleDashboard()

    robot.connect()
    print(f"AI Lightsaber Trainer — DRY_RUN={config.DRY_RUN}")
    print(f"Keys: {config.QUIT_KEY}=quit  {config.EMERGENCY_STOP_KEY}=stop  {config.HOME_KEY}=home")

    last_direction: AttackDirection = "none"
    t_prev = time.monotonic()

    try:
        while True:
            frame = camera.read_frame()
            if frame is None:
                continue

            now = time.monotonic()
            fps = 1.0 / max(now - t_prev, 1e-6)
            t_prev = now

            direction = vision.detect_attack(frame)

            if direction != "none" and direction != last_direction:
                robot.respond_to_attack(direction)
                sounds.play_for_attack(direction)

            last_direction = direction
            dashboard.update(direction, robot.current_pose, fps)

            if config.SHOW_PREVIEW:
                preview = overlay.render(
                    frame,
                    direction,
                    fps=fps,
                    pose=vision.last_landmarks,
                    robot_pose=robot.current_pose,
                )
                cv2.imshow(config.WINDOW_TITLE, preview)
                key = cv2.waitKey(1) & 0xFF
                key_char = chr(key) if key != 255 else ""

                if key_char == config.QUIT_KEY:
                    break
                if key_char == config.EMERGENCY_STOP_KEY:
                    robot.emergency_stop()
                if key_char == config.HOME_KEY:
                    robot.move_to_pose("HOME")
    finally:
        vision.close()
        camera.release()
        robot.disconnect()
        sounds.shutdown()
        dashboard.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
