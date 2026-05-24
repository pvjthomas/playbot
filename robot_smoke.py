#!/usr/bin/env python3
"""
Hardware smoke tests for PiPER (no camera). Linux VM or macOS host.

  python robot_smoke.py              # DRY_RUN pose sequence
  python robot_smoke.py --probe-can  # check can0 (Linux) or gs_usb (macOS)
  python robot_smoke.py --preflight  # firmware + CAN send + state (no motion)
  python robot_smoke.py --connect    # preflight, then LIVE enable + hold pose
  python robot_smoke.py --live --pose HOME --i-know

After a live test the arm holds at GUARD_CENTER (configurable):
  Enter   — close host CAN only; arm keeps torque (normal exit)
  Ctrl+C  — software e-stop (DisableArm, cuts torque)

macOS: see MAC-ROBOT.md (brew install libusb, pip install "python-can[gs-usb]").
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time

import config
from can_platform import is_darwin, print_mac_setup_hint, probe_gs_usb_open, resolve_can_profile
from contracts import RobotPose
from movement_trainer import MovementTrainer
from poses import JOINT_POSES
from robot import PiperRobot
from robot_preflight import run_preflight
from safety import SafetyGuard


def _can0_up() -> bool:
    try:
        out = subprocess.check_output(["ip", "link", "show", "can0"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return "state UP" in out or "UP," in out or "<UP," in out


def _probe_can() -> int:
    profile = resolve_can_profile()
    print(f"[probe] profile={profile.label}")

    if is_darwin():
        ok, detail = probe_gs_usb_open(profile.channel, config.CAN_BITRATE)
        if not ok:
            print(f"[probe] FAIL — gs_usb: {detail}")
            print_mac_setup_hint()
            return 1
        print(f"[probe] OK — {detail}")
        return 0

    try:
        subprocess.run(["ip", "link", "show", config.CAN_INTERFACE], check=True)
    except subprocess.CalledProcessError:
        print(f"[probe] FAIL — no {config.CAN_INTERFACE}. Pass USB-CAN to VM in UTM, then:")
        print("  bash ubuntu_shared/can-up.sh")
        print("  Or run on Mac host: see MAC-ROBOT.md")
        return 1
    if not _can0_up():
        print(f"[probe] {config.CAN_INTERFACE} exists but is DOWN — run can-up.sh")
        return 1
    print(f"[probe] OK — {config.CAN_INTERFACE} is UP")
    return 0


def _require_preflight() -> int:
    if _probe_can() != 0:
        return 1
    return run_preflight()


def _dry_run_sequence() -> int:
    safety = SafetyGuard(dry_run=True)
    robot = PiperRobot(safety=safety)
    trainer = MovementTrainer()
    robot.connect()
    for name in ("HOME", "BLOCK_LEFT", "BLOCK_RIGHT", "HOME"):
        print(f"[smoke] → {name}: {trainer.describe(name)}")
        robot.move_to_pose(name)
        time.sleep(0.4)
    robot.respond_to_attack("left")
    robot.emergency_stop()
    robot.move_to_pose("HOME")
    robot.disconnect()
    print("[smoke] DRY_RUN sequence OK")
    return 0


def _wait_for_enter_or_estop(robot: PiperRobot) -> None:
    """Enter = close CAN (keep torque). Ctrl+C = software e-stop (DisableArm)."""
    enter_pressed = threading.Event()

    def _read_enter() -> None:
        try:
            input()
            enter_pressed.set()
        except EOFError:
            pass

    threading.Thread(target=_read_enter, daemon=True).start()

    print("[smoke] Enter — close host CAN (arm keeps torque).")
    print("[smoke] Ctrl+C — software e-stop (DisableArm, cuts torque).")
    try:
        while not enter_pressed.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[smoke] Software e-stop (Ctrl+C)")
        robot.software_estop()
        raise SystemExit(130) from None

    print("[smoke] Enter — closing host CAN, motors stay enabled on arm.")
    robot.close_can()


def _finish_live_session(robot: PiperRobot, end_pose: RobotPose) -> None:
    print(f"[smoke] Moving to hold pose {end_pose}...")
    robot.move_to_pose(end_pose)
    settle = config.ROBOT_MOVE_SETTLE_SEC
    print(f"[smoke] Settling {settle:.1f}s at {end_pose}...")
    time.sleep(settle)
    print(f"[smoke] Holding {end_pose} — motors enabled.")
    _wait_for_enter_or_estop(robot)


def _live_connect_only(*, end_pose: RobotPose) -> int:
    if _require_preflight() != 0:
        return 1
    old = config.DRY_RUN
    config.DRY_RUN = False
    try:
        robot = PiperRobot(safety=SafetyGuard(dry_run=False))
        robot.connect()
        print("[smoke] LIVE connect OK (EnableArm + HOME sent)")
        _finish_live_session(robot, end_pose)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[smoke] LIVE connect FAILED: {exc}")
        return 1
    finally:
        config.DRY_RUN = old


def _live_pose(name: RobotPose, *, end_pose: RobotPose) -> int:
    if _require_preflight() != 0:
        return 1
    old = config.DRY_RUN
    config.DRY_RUN = False
    try:
        robot = PiperRobot(safety=SafetyGuard(dry_run=False))
        robot.connect()
        time.sleep(0.5)
        robot.move_to_pose(name)
        time.sleep(config.ROBOT_MOVE_SETTLE_SEC)
        _finish_live_session(robot, end_pose)
        print(f"[smoke] LIVE pose {name} OK")
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[smoke] LIVE pose FAILED: {exc}")
        return 1
    finally:
        config.DRY_RUN = old


def main() -> int:
    parser = argparse.ArgumentParser(description="PiPER robot smoke test (Linux VM or macOS)")
    parser.add_argument("--probe-can", action="store_true", help="Check can0 exists and is UP")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Firmware + CAN probe send + joint/status read (no motion)",
    )
    parser.add_argument("--connect", action="store_true", help="Preflight, then LIVE enable + hold")
    parser.add_argument("--live", action="store_true", help="Preflight, then LIVE joint motion")
    parser.add_argument("--pose", default="HOME", choices=list(JOINT_POSES.keys()))
    parser.add_argument(
        "--end-pose",
        default=config.ROBOT_SMOKE_END_POSE,
        choices=list(JOINT_POSES.keys()),
        help="Hold pose after live test (default: GUARD_CENTER)",
    )
    parser.add_argument(
        "--i-know",
        action="store_true",
        help="Required with --live: arm may move",
    )
    args = parser.parse_args()

    if args.probe_can:
        return _probe_can()
    if args.preflight:
        return _require_preflight()
    if args.connect:
        return _live_connect_only(end_pose=args.end_pose)
    if args.live:
        if not args.i_know:
            print("Refusing --live without --i-know (safety).")
            return 2
        return _live_pose(args.pose, end_pose=args.end_pose)
    return _dry_run_sequence()


if __name__ == "__main__":
    sys.exit(main())
