"""Developer 2 — predefined joint poses (no IK)."""

from dataclasses import dataclass

from contracts import RobotPose

# Six joint angles in degrees (J1–J6). Calibrate on hardware.
JOINT_POSES: dict[RobotPose, tuple[float, float, float, float, float, float]] = {
    "HOME": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "GUARD_CENTER": (0.0, 30.0, -20.0, 40.0, 0.0, 0.0),
    "BLOCK_LEFT": (-35.0, 45.0, -60.0, 30.0, 15.0, 0.0),
    "BLOCK_RIGHT": (35.0, 45.0, 60.0, 30.0, -15.0, 0.0),
    "BLOCK_HIGH": (0.0, 55.0, -45.0, 70.0, 0.0, 0.0),
    "BLOCK_LOW": (0.0, 60.0, 30.0, 50.0, 0.0, 0.0),
    "DODGE_BACK": (0.0, -15.0, 10.0, 20.0, 0.0, 0.0),
    "COUNTER_TAP": (15.0, 40.0, -30.0, 45.0, 10.0, 0.0),
    "RESET": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
}


@dataclass(frozen=True)
class PoseDefinition:
    name: RobotPose
    joints: tuple[float, float, float, float, float, float]
    note: str = ""


def get_pose(name: RobotPose) -> PoseDefinition:
    if name not in JOINT_POSES:
        raise ValueError(f"Unknown pose: {name}")
    return PoseDefinition(name, JOINT_POSES[name])
