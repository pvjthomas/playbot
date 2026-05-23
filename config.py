"""Central configuration — edit here or override for demos."""

# --- Safety (Developer 2) ---
DRY_RUN = True
MOVEMENT_COOLDOWN_SEC = 0.35
CAN_INTERFACE = "can0"  # Linux SocketCAN only
CAN_BUSTYPE = "auto"  # auto | socketcan | gs_usb | slcan — auto: socketcan on Linux, gs_usb on macOS
CAN_CHANNEL = "auto"  # auto: can0 (Linux) or gs_usb index 0 (macOS)
CAN_BITRATE = 1000000  # PiPER bus (1 Mbps)
ROBOT_MOVE_SPEED_PERCENT = 30  # piper_sdk ModeCtrl speed (0–100); keep low for first LIVE tests

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
SABER_MODEL = ""  # path to trained yolov8 weights, e.g. ../models/lightsaber.pt
SABER_YOLO_MAX_GRIP_DIST_PX = 120

# --- App (Developer 3) ---
SHOW_PREVIEW = True
ENABLE_SOUNDS = False
ENABLE_DASHBOARD = False
WINDOW_TITLE = "AI Lightsaber Trainer"
EMERGENCY_STOP_KEY = "e"
QUIT_KEY = "q"
HOME_KEY = "h"
