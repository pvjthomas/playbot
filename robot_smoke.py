#!/usr/bin/env python3
"""
Hardware smoke tests for PiPER (no camera). Linux VM or macOS host.

  python robot_smoke.py              # DRY_RUN pose sequence
  python robot_smoke.py --probe-can  # check can0 (Linux) or gs_usb (macOS)
  python robot_smoke.py --connect    # live CAN connect only (no motion)
  python robot_smoke.py --live --pose HOME  # LIVE move (requires --i-know)

macOS: see MAC-ROBOT.md (brew install libusb, pip install "python-can[gs-usb]").
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

import config
from can_platform import is_darwin, print_mac_setup_hint, probe_gs_usb_open, resolve_can_profile
from contracts import RobotPose
from movement_trainer import MovementTrainer
from poses import JOINT_POSES
from robot import PiperRobot
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
        print("  bash projects/ubuntu_shared/can-up.sh")
        print("  Or run on Mac host: see MAC-ROBOT.md")
        return 1
    if not _can0_up():
        print(f"[probe] {config.CAN_INTERFACE} exists but is DOWN — run can-up.sh")
        return 1
    print(f"[probe] OK — {config.CAN_INTERFACE} is UP")
    return 0


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


def _live_connect_only() -> int:
    if _probe_can() != 0:
        return 1
    old = config.DRY_RUN
    config.DRY_RUN = False
    try:
        robot = PiperRobot(safety=SafetyGuard(dry_run=False))
        robot.connect()
        print("[smoke] LIVE connect OK (no joint motion sent)")
        robot.disconnect()
        return 0
    except Exception as exc:
        print(f"[smoke] LIVE connect FAILED: {exc}")
        return 1
    finally:
        config.DRY_RUN = old


def _live_pose(name: RobotPose) -> int:
    if _probe_can() != 0:
        return 1
    old = config.DRY_RUN
    config.DRY_RUN = False
    try:
        robot = PiperRobot(safety=SafetyGuard(dry_run=False))
        robot.connect()
        time.sleep(0.5)
        robot.move_to_pose(name)
        time.sleep(2.0)
        robot.move_to_pose("HOME")
        robot.disconnect()
        print(f"[smoke] LIVE pose {name} sent")
        return 0
    except Exception as exc:
        print(f"[smoke] LIVE pose FAILED: {exc}")
        return 1
    finally:
        config.DRY_RUN = old


def main() -> int:
    parser = argparse.ArgumentParser(description="PiPER robot smoke test (Linux VM or macOS)")
    parser.add_argument("--probe-can", action="store_true", help="Check can0 exists and is UP")
    parser.add_argument("--connect", action="store_true", help="LIVE connect only (no JointCtrl)")
    parser.add_argument("--live", action="store_true", help="LIVE joint motion")
    parser.add_argument("--pose", default="HOME", choices=list(JOINT_POSES.keys()))
    parser.add_argument(
        "--i-know",
        action="store_true",
        help="Required with --live: arm may move",
    )
    args = parser.parse_args()

    if args.probe_can:
        return _probe_can()
    if args.connect:
        return _live_connect_only()
    if args.live:
        if not args.i_know:
            print("Refusing --live without --i-know (safety).")
            return 2
        return _live_pose(args.pose)
    return _dry_run_sequence()


if __name__ == "__main__":
    sys.exit(main())
