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
        if self.safety.emergency_stop_active:
            print(f"[robot] blocked (move → {name})")
            return

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

    def close_can(self):
        """Close host CAN only — does not call DisableArm (arm keeps torque)."""
        if self._piper is not None and not self.safety.dry_run:
            try:
                self._piper.DisconnectPort()
            except Exception as exc:
                print(f"[robot] DisconnectPort warning: {exc}")
            print("[robot] Host CAN closed — motors still enabled on arm")
        self._connected = False

    def software_estop(self):
        """Software e-stop: DisableArm (cuts torque) then close CAN."""
        if self._piper is not None and not self.safety.dry_run:
            try:
                self._piper.DisableArm(7)
            except Exception as exc:
                print(f"[robot] DisableArm warning: {exc}")
            try:
                self._piper.DisconnectPort()
            except Exception as exc:
                print(f"[robot] DisconnectPort warning: {exc}")
            print("[robot] Software e-stop — motors disabled")
        self._connected = False

    def disconnect(self, *, disable: bool = False):
        """Close session. Default: close CAN only (keep torque). disable=True → software e-stop."""
        if disable:
            self.software_estop()
            return
        if self.safety.dry_run:
            print("[robot] Disconnected")
            self._connected = False
            return
        self.close_can()

    def emergency_stop(self):
        self.safety.trigger_emergency_stop()
        if self._piper is not None and not self.safety.dry_run:
            try:
                self._piper.DisableArm(7)
            except Exception as exc:
                print(f"[robot] DisableArm warning: {exc}")
            print("[robot] software e-stop — motors disabled")
        else:
            print("[robot] hold position (DRY_RUN)")

    @property
    def current_pose(self) -> RobotPose:
        return self._current_pose
