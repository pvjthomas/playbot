"""Central configuration — edit here or override for demos."""

# --- Safety (Developer 2) ---
DRY_RUN = True
MOVEMENT_COOLDOWN_SEC = 0.35
CAN_INTERFACE = "can0"  # Linux SocketCAN only
CAN_BUSTYPE = "auto"  # auto | socketcan | gs_usb | slcan — auto: socketcan on Linux, gs_usb on macOS
CAN_CHANNEL = "auto"  # auto: can0 (Linux) or gs_usb index 0 (macOS)
CAN_BITRATE = 1000000  # PiPER bus (1 Mbps)
ROBOT_MOVE_SPEED_PERCENT = 30  # piper_sdk ModeCtrl speed (0–100); keep low for first LIVE tests
ROBOT_MOVE_SETTLE_SEC = 3.0  # wait after JointCtrl before considering move done
ROBOT_SMOKE_END_POSE = "GUARD_CENTER"  # stable hold pose after live smoke tests

# --- Vision (Developer 1) ---
#
# Camera backends (see camera.py module docstring and README § Camera):
#   opencv — fast, direct OpenCV (laptop webcam; Piper on Linux via /dev/video*)
#   ffmpeg — macOS Piper only: opens "Dabai DC1" by name (correct device, lower FPS)
#   auto   — ffmpeg for Piper on Mac, opencv on Linux (default)
#
CAMERA_SOURCE = "piper"
CAMERA_BACKEND = "opencv"   # fast path — mapped via camera.py --pick-opencv
PIPER_CAMERA_NAME = "Dabai DC1"
PIPER_OPENCV_INDEX = 0      # from camera.py --pick-opencv (2026-05-23)
CAMERA_INDEX = 0              # laptop / fallback when CAMERA_SOURCE is "auto" without Piper
CAMERA_WIDTH = 1280           # opencv path: native was 1632x1224; lower if FPS still low
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
# Horizontal mirror (selfie flip) per camera — see camera_mirror.py, camera_calibrate_mirror.py
# True = raise RIGHT hand → appears on RIGHT side of screen (typical MacBook preview)
# False = raise RIGHT hand → appears on LEFT side of screen (true camera view)
# Run: python camera_calibrate_mirror.py --camera laptop
CAMERA_MIRROR_BY_SOURCE: dict[str, bool] = {}  # e.g. {"laptop": True, "piper": False}
CAMERA_APPLY_MIRROR_CORRECTION = False  # flip frames to canonical view when mirror_preview True
# Wrist / Orbbec install rotation (90/180/270) + flip — see camera_orientation.py
CAMERA_ORIENTATION_BY_SOURCE: dict[str, dict] = {}  # e.g. piper: rotation_deg, flip_h, mount_facing
CAMERA_APPLY_ORIENTATION_CORRECTION = False  # apply camera_orientation.json before vision
WRIST_CAM_REFERENCE_POSE = "GUARD_CENTER"  # calibrate orientation at this robot pose
USE_FAKE_ATTACKS = False  # True = cycle fake directions (no MediaPipe needed)
FAKE_ATTACK_CYCLE_SEC = 2.0

# Orbbec SDK (optional — depth / IR / D2C; see orbbec_*.py and requirements-orbbec.txt)
ENABLE_ORBBEC_SDK = False       # True or --orbbec-sdk → open_camera() uses OrbbecCamera
ORBBEC_ENABLE_DEPTH = True
ORBBEC_ENABLE_IR = False
ORBBEC_ENABLE_IMU = False       # stub — wire when IMU fusion is implemented
ORBBEC_DEPTH_MIN_MM = 200
ORBBEC_DEPTH_MAX_MM = 4000
ORBBEC_LUNGE_DEPTH_DELTA_MM = 150       # ROI closer than baseline → lunge hint
ORBBEC_OVERHEAD_DEPTH_DELTA_MM = 80     # head ROI nearer than torso → overhead hint
ENABLE_DEPTH_ATTACK_HINTS = False       # DepthAugmentedAttackVision fusion (stub)

# MediaPipe strike tuning (meanings documented in vision.py)
HIGH_MARGIN = 0.06      # overhead → "high"
SIDE_MARGIN = 0.12      # cross-body reach → "left" / "right"
EXTENSION_MIN = 0.18    # min arm extension (filters "none")
# "center" uses SIDE_MARGIN * 0.4 in vision.py — both wrists at midline

# Temporal swing (swing_tracker.py — Milestone 2)
USE_TEMPORAL_SWING = False  # main.py: detect_swing + phase-based robot trigger (vs END-pose edges)
SWING_RESPOND_ON_BEGIN = True  # fire on begin phase; if False, mid/end only
SWING_HISTORY_SEC = 0.6           # landmark ring buffer window
SWING_WRIST_MERGE_DIST = 0.12       # two-hand grip midpoint when wrists close
SWING_BEGIN_VELOCITY = 0.35         # norm coords/s — motion starts
SWING_IDLE_VELOCITY = 0.12          # below this → swing cooling down
SWING_IDLE_FRAMES = 6               # consecutive slow frames before idle
SWING_BEGIN_MAX_SEC = 0.15          # max wind-up duration before mid
SWING_MID_SPEED_RATIO = 0.45        # fraction of session peak speed → mid
SWING_MID_EXT_RATIO = 0.72          # extension vs peak → likely past mid
SWING_END_EXT_RATIO = 0.88          # extension near peak → end phase
SWING_END_SPEED_RATIO = 0.50        # decelerating into end
SWING_DIRECTION_MIN = 0.06          # min displacement for direction label
SWING_AXIS_DOMINANCE = 1.35         # lateral vs vertical axis winner
SWING_THRUST_EXT_MIN = 0.05         # min extension gain for thrust
SWING_THRUST_LATERAL_MAX = 0.05    # max lateral travel for thrust
SWING_THRUST_VERTICAL_MAX = 0.08   # max vertical travel for thrust (not overhead)

ENABLE_YOLO = False
YOLO_EVERY_N_FRAMES = 5
YOLO_MODEL = "yolov8n.pt"
YOLO_CONFIDENCE = 0.5

# Optional: lightsaber grip→tip (saber_detector.py). Off in main fight loop.
ENABLE_SABER_DETECTION = False
SABER_PROFILE = ""  # set via --saber on CLI (e.g. redtoy); see saber_profiles.py
SABER_USE_OWN_POSE = False  # True if not sharing AttackVision landmarks
SABER_BLADE_LENGTH_RATIO = 0.35  # tip distance past wrist (normalized coords)
SABER_MIN_FOREARM_REACH = 0.12  # ignore resting arm
SABER_HORIZONTAL_MAX_DEG = 25  # |angle| ≤ this → horizontal
SABER_VERTICAL_MIN_DEG = 65  # |angle| ≥ this → vertical
SABER_USE_COLOR_TIP = False  # scan for color along blade (see SABER_COLOR_HSV_RANGES)
SABER_TIP_HSV_LOW = None  # legacy single-range HSV (use SABER_COLOR_HSV_RANGES instead)
SABER_TIP_HSV_HIGH = None
SABER_COLOR_HSV_RANGES = None  # list of (low, high) BGR HSV tuples, e.g. redtoy profile
SABER_COLOR_SEARCH_RADIUS_PX = 35  # lateral search width along forearm ray
SABER_MIN_COLOR_PIXELS = 20  # min red pixels to trust color tip over geometry
SABER_MODEL = "../models/saber_runs/redtoy_78shot/weights/best.pt"  # 78 manual green boxes
SABER_YOLO_MAX_GRIP_DIST_PX = 120

# --- App (Developer 3) ---
SHOW_PREVIEW = True
ENABLE_SOUNDS = False
ENABLE_DASHBOARD = False
WINDOW_TITLE = "AI Lightsaber Trainer"
EMERGENCY_STOP_KEY = "e"
QUIT_KEY = "q"
HOME_KEY = "h"
