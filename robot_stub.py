#!/usr/bin/env python3
"""
Milestone 1 demo — DRY_RUN robot responses without camera or CAN.

  python robot_stub.py              # cycle attack directions (fake vision)
  python robot_stub.py --poses      # step through every pose in poses.py
  python robot_stub.py --attacks    # one respond_to_attack per direction

No hardware motion. Safe on macOS without the VM.
"""

from __future__ import annotations

import argparse
import sys
import time

import config
from contracts import ATTACK_TO_POSE, AttackDirection
from poses import JOINT_POSES
from robot import PiperRobot
from safety import SafetyGuard

_ATTACK_DEMO: list[AttackDirection] = [
    "left",
    "right",
    "high",
    "center",
    "none",
]


def _demo_attacks(robot: PiperRobot, pause_sec: float) -> None:
    print(f"[stub] DRY_RUN={config.DRY_RUN} — cycling attacks (Ctrl+C to stop)")
    robot.connect()
    try:
        while True:
            for direction in _ATTACK_DEMO:
                if direction == "none":
                    time.sleep(pause_sec)
                    continue
                target = ATTACK_TO_POSE[direction]
                print(f"[stub] vision → {direction!r} → {target}")
                robot.respond_to_attack(direction)
                time.sleep(pause_sec)
    except KeyboardInterrupt:
        print("\n[stub] interrupted")


def _demo_all_attacks_once(robot: PiperRobot) -> None:
    robot.connect()
    for direction, target in ATTACK_TO_POSE.items():
        if target is None:
            print(f"[stub] {direction!r} → (no pose)")
            continue
        print(f"[stub] respond_to_attack({direction!r})")
        robot.respond_to_attack(direction)
        time.sleep(config.MOVEMENT_COOLDOWN_SEC)
    robot.disconnect()


def _demo_all_poses(robot: PiperRobot, pause_sec: float) -> None:
    robot.connect()
    for name in JOINT_POSES:
        print(f"[stub] move_to_pose({name!r})")
        robot.move_to_pose(name)
        time.sleep(pause_sec)
    robot.move_to_pose("HOME")
    robot.disconnect()
    print("[stub] all poses OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="DRY_RUN robot stub (Milestone 1)")
    parser.add_argument("--poses", action="store_true", help="Step through JOINT_POSES")
    parser.add_argument(
        "--attacks",
        action="store_true",
        help="Fire respond_to_attack once per direction",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.8,
        help="Seconds between steps (default 0.8)",
    )
    args = parser.parse_args()

    if not config.DRY_RUN:
        print("[stub] Refusing to run — set DRY_RUN=True in config.py", file=sys.stderr)
        return 2

    robot = PiperRobot(safety=SafetyGuard(dry_run=True))

    if args.poses:
        _demo_all_poses(robot, args.pause)
        return 0
    if args.attacks:
        _demo_all_attacks_once(robot)
        return 0

    _demo_attacks(robot, args.pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
