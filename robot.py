"""Developer 2 — PiPER robot controller (stub first)."""

import time

import config
from can_platform import connect_piper_interface, resolve_can_profile
from contracts import AttackDirection, RobotController, RobotPose, pose_for_attack
from poses import get_pose
from safety import SafetyGuard


def _joints_to_sdk(joints_deg: tuple[float, ...]) -> tuple[int, int, int, int, int, int]:
    """Piper SDK JointCtrl expects millidegrees (0.001°)."""
    return tuple(int(round(d * 1000)) for d in joints_deg)


class PiperRobot:
    """Implements RobotController. DRY_RUN=True by default."""

    def __init__(self, safety: SafetyGuard | None = None):
        self.safety = safety or SafetyGuard()
        self._piper = None
        self._connected = False
        self._current_pose: RobotPose = "HOME"

    def connect(self):
        if self.safety.dry_run:
            print("[robot] DRY_RUN — stub mode, no CAN motion")
            self._connected = True
            self.move_to_pose("HOME")
            return

        try:
            from piper_sdk import C_PiperInterface
        except ImportError as exc:
            raise ImportError("Install piper_sdk: pip install -r requirements.txt") from exc

        profile = resolve_can_profile()
        self._piper = connect_piper_interface(C_PiperInterface)
        self._piper.ConnectPort()
        self._piper.EnableArm(7)
        self._connected = True
        print(f"[robot] Connected ({profile.label})")
        self.move_to_pose("HOME")

    def disconnect(self):
        self._connected = False
        print("[robot] Disconnected")

    def respond_to_attack(self, direction: AttackDirection):
        target = pose_for_attack(direction)
        if target is None:
            return
        if not self.safety.may_move():
            print(f"[robot] blocked ({direction} → {target})")
            return
        self.move_to_pose(target)
        self.safety.record_move()

    def move_to_pose(self, name: RobotPose):
        pose = get_pose(name)
        self._current_pose = name
        joints = ", ".join(f"{j:.1f}" for j in pose.joints)
        mode = "DRY_RUN" if self.safety.dry_run else "LIVE"
        print(f"[robot] {mode} → {name}: J=[{joints}]")

        if not self.safety.hardware_enabled():
            return

        if self._piper is None:
            print("[robot] LIVE skipped — not connected")
            return

        speed = config.ROBOT_MOVE_SPEED_PERCENT
        self._piper.ModeCtrl(0x01, 0x01, speed, 0x00)
        j1, j2, j3, j4, j5, j6 = _joints_to_sdk(pose.joints)
        self._piper.JointCtrl(j1, j2, j3, j4, j5, j6)
        time.sleep(0.05)

    def emergency_stop(self):
        self.safety.trigger_emergency_stop()
        print("[robot] hold position")

    @property
    def current_pose(self) -> RobotPose:
        return self._current_pose
