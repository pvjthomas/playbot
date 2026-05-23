"""Developer 2 — pose calibration helper (stub)."""

from contracts import RobotPose
from poses import JOINT_POSES, get_pose


class MovementTrainer:
    """Record and test poses on hardware — stub for hackathon milestone 2."""

    def list_poses(self) -> list[RobotPose]:
        return list(JOINT_POSES.keys())

    def describe(self, name: RobotPose) -> str:
        pose = get_pose(name)
        joints = ", ".join(f"{j:.1f}" for j in pose.joints)
        return f"{name}: [{joints}]"

    def run_pose_sequence(self, robot, names: list[RobotPose]):
        """Step through poses slowly (stub — prints sequence)."""
        for name in names:
            print(f"[trainer] next pose: {name}")
            robot.move_to_pose(name)
