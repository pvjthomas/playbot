"""Central configuration — edit here or override for demos."""

# --- Safety (Developer 2) ---
DRY_RUN = True
MOVEMENT_COOLDOWN_SEC = 0.35
CAN_INTERFACE = "can0"

# --- Vision (Developer 1) ---
CAMERA_INDEX = 0
USE_FAKE_ATTACKS = False  # True = cycle fake directions (no MediaPipe needed)
FAKE_ATTACK_CYCLE_SEC = 2.0
ENABLE_YOLO = False
YOLO_EVERY_N_FRAMES = 5
YOLO_MODEL = "yolov8n.pt"
YOLO_CONFIDENCE = 0.5

# --- App (Developer 3) ---
SHOW_PREVIEW = True
ENABLE_SOUNDS = False
ENABLE_DASHBOARD = False
WINDOW_TITLE = "AI Lightsaber Trainer"
EMERGENCY_STOP_KEY = "e"
QUIT_KEY = "q"
HOME_KEY = "h"
