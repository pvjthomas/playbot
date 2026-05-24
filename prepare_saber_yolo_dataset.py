"""
Build YOLO train/val split from raw saber photos (auto bbox via pose + red HSV).

Run after collect_saber_trainer.py:
  python prepare_saber_yolo_dataset.py --saber redtoy
  python train_saber.py --saber redtoy

Negative images (folder ``other/``) get empty label files.

Auto-label strategy (saber-only boxes, not whole person):
  1. MediaPipe forearm → grip→tip line (``SaberDetector``)
  2. Tight axis-aligned bbox around that segment (+ small pad)
  3. Fallback: red pixels in a corridor along the blade only
  4. Last resort: largest red contour if small enough (< ``--max-area-ratio``)
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
from pathlib import Path

import cv2
import numpy as np

import config
from saber_detector import SaberDetector, SaberLine
from saber_profiles import apply_saber_profile
from vision import AttackVision


def _red_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = SaberDetector._color_mask(hsv)
    if mask is None:
        return np.zeros(frame.shape[:2], dtype=np.uint8)
    return mask

RAW_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "raw"
YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
NEGATIVE_LABEL = "other"
CLASS_NAME = "lightsaber"
MIN_BOX_AREA_RATIO = 0.002  # skip tiny red blobs
MAX_BOX_AREA_RATIO = 0.28  # reject person-sized red blobs
DEFAULT_PAD_RATIO = 0.16  # padding around grip→tip segment


def parse_args():
    p = argparse.ArgumentParser(description="Prepare YOLO dataset from raw saber images")
    p.add_argument("--saber", default="redtoy")
    p.add_argument("--val-fraction", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-area-ratio", type=float, default=MIN_BOX_AREA_RATIO)
    p.add_argument(
        "--max-area-ratio",
        type=float,
        default=MAX_BOX_AREA_RATIO,
        help="Reject mask-only boxes larger than this fraction of frame",
    )
    p.add_argument(
        "--pad-ratio",
        type=float,
        default=DEFAULT_PAD_RATIO,
        help="Padding around grip→tip line as fraction of blade length",
    )
    return p.parse_args()


def _bbox_from_saber_line(
    saber: SaberLine,
    w: int,
    h: int,
    *,
    pad_ratio: float = DEFAULT_PAD_RATIO,
) -> tuple[float, float, float, float] | None:
    """YOLO-normalized cx, cy, w, h — tight box around grip→tip only."""
    gx, gy, tx, ty = saber.grip_x, saber.grip_y, saber.tip_x, saber.tip_y
    length = max(20.0, math.hypot(tx - gx, ty - gy))
    pad = max(12, int(length * pad_ratio))
    x1 = max(0, min(gx, tx) - pad)
    y1 = max(0, min(gy, ty) - pad)
    x2 = min(w, max(gx, tx) + pad)
    y2 = min(h, max(gy, ty) + pad)
    if x2 - x1 < 8 or y2 - y1 < 8:
        cx_px = int((gx + tx) / 2)
        cy_px = int((gy + ty) / 2)
        half = max(16, pad)
        x1 = max(0, cx_px - half)
        y1 = max(0, cy_px - half)
        x2 = min(w, cx_px + half)
        y2 = min(h, cy_px + half)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return (x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h


def _bbox_from_blade_corridor(
    mask: np.ndarray,
    saber: SaberLine,
    min_area_ratio: float,
) -> tuple[float, float, float, float] | None:
    """Red pixels within a strip along the detected blade axis."""
    h, w = mask.shape[:2]
    gx, gy, tx, ty = saber.grip_x, saber.grip_y, saber.tip_x, saber.tip_y
    length = math.hypot(tx - gx, ty - gy)
    if length < 12:
        return None
    radius = max(10, int(getattr(config, "SABER_COLOR_SEARCH_RADIUS_PX", 35) * 0.85))
    corridor = np.zeros_like(mask)
    steps = max(16, int(length // 6))
    for i in range(steps + 1):
        t = i / steps
        cx = int(gx + (tx - gx) * t)
        cy = int(gy + (ty - gy) * t)
        cv2.circle(corridor, (cx, cy), radius, 255, -1)
    clipped = cv2.bitwise_and(mask, corridor)
    return _bbox_from_mask(clipped, min_area_ratio)


def _bbox_from_mask(mask: np.ndarray, min_area_ratio: float) -> tuple[float, float, float, float] | None:
    """Return YOLO-normalized cx, cy, w, h or None."""
    h, w = mask.shape[:2]
    min_area = h * w * min_area_ratio
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best = max(contours, key=cv2.contourArea)
    if cv2.contourArea(best) < min_area:
        return None
    x, y, bw, bh = cv2.boundingRect(best)
    cx = (x + bw / 2) / w
    cy = (y + bh / 2) / h
    return cx, cy, bw / w, bh / h


def auto_label_box(
    frame: np.ndarray,
    *,
    detector: SaberDetector,
    vision: AttackVision,
    min_area_ratio: float,
    max_area_ratio: float,
    pad_ratio: float,
) -> tuple[float, float, float, float] | None:
    """Best-effort saber-only YOLO box (not whole person)."""
    h, w = frame.shape[:2]
    vision.detect_attack(frame)
    sabers = detector.detect_all(frame, vision.last_landmarks)
    saber = sabers[0] if sabers else None

    if saber is not None:
        box = _bbox_from_saber_line(saber, w, h, pad_ratio=pad_ratio)
        if box is not None and box[2] * box[3] <= max_area_ratio:
            return box
        mask = _red_mask(frame)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        corridor_box = _bbox_from_blade_corridor(mask, saber, min_area_ratio)
        if corridor_box is not None and corridor_box[2] * corridor_box[3] <= max_area_ratio:
            return corridor_box

    mask = _red_mask(frame)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    box = _bbox_from_mask(mask, min_area_ratio)
    if box is None:
        return None
    if box[2] * box[3] > max_area_ratio:
        return None
    return box


def _collect_images(raw_root: Path) -> list[tuple[Path, bool]]:
    """(path, is_negative) pairs."""
    items: list[tuple[Path, bool]] = []
    for label_dir in sorted(raw_root.iterdir()):
        if not label_dir.is_dir() or label_dir.name.startswith("_"):
            continue
        is_neg = label_dir.name == NEGATIVE_LABEL
        for img in sorted(label_dir.glob("*.jpg")):
            items.append((img, is_neg))
        for img in sorted(label_dir.glob("*.png")):
            items.append((img, is_neg))
    return items


def main():
    args = parse_args()
    apply_saber_profile(args.saber)
    saber_id = args.saber.strip().replace("/", "_")
    raw_root = RAW_BASE / saber_id
    if not raw_root.is_dir():
        raise SystemExit(f"No raw images at {raw_root}\nRun: python collect_saber_trainer.py --saber {saber_id}")

    images = _collect_images(raw_root)
    if len(images) < 10:
        raise SystemExit(f"Only {len(images)} images — collect at least 10 first (target 60+).")

    out = YOLO_BASE
    for split in ("train", "valid"):
        shutil.rmtree(out / split, ignore_errors=True)
        (out / split / "images").mkdir(parents=True)
        (out / split / "labels").mkdir(parents=True)

    rng = random.Random(args.seed)
    rng.shuffle(images)
    n_val = max(1, int(len(images) * args.val_fraction))
    val_set = set(id(p) for p, _ in images[:n_val])

    stats = {"labeled": 0, "negative": 0, "skipped": 0, "train": 0, "valid": 0}

    vision = AttackVision(static_image_mode=True)
    detector = SaberDetector()
    try:
        for path, is_neg in images:
            split = "valid" if id(path) in val_set else "train"
            frame = cv2.imread(str(path))
            if frame is None:
                stats["skipped"] += 1
                continue

            stem = path.stem
            dst_img = out / split / "images" / f"{stem}{path.suffix}"
            dst_lbl = out / split / "labels" / f"{stem}.txt"
            shutil.copy2(path, dst_img)

            if is_neg:
                dst_lbl.write_text("")
                stats["negative"] += 1
            else:
                box = auto_label_box(
                    frame,
                    detector=detector,
                    vision=vision,
                    min_area_ratio=args.min_area_ratio,
                    max_area_ratio=args.max_area_ratio,
                    pad_ratio=args.pad_ratio,
                )
                if box is None:
                    stats["skipped"] += 1
                    dst_lbl.write_text("")
                else:
                    cx, cy, bw, bh = box
                    dst_lbl.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                    stats["labeled"] += 1
            stats[split] += 1
    finally:
        vision.close()
        detector.close()

    yaml_path = out / "data.yaml"
    yaml_path.write_text(
        f"""# Auto-generated by prepare_saber_yolo_dataset.py
path: {out.resolve()}
train: train/images
val: valid/images
names:
  0: {CLASS_NAME}
""",
        encoding="utf-8",
    )

    print(f"Prepared {len(images)} images → {out}")
    print(f"  train: {stats['train']}  valid: {stats['valid']}")
    print(f"  auto-labeled: {stats['labeled']}  negatives: {stats['negative']}  skipped: {stats['skipped']}")
    print(f"  data.yaml: {yaml_path}")
    if stats["labeled"] < 5:
        print("\nWARNING: very few auto-labels — check lighting or run saber_preview.py with 'm' (mask).")
    print("\nNext: python review_saber_labels.py --saber redtoy")
    print("       python train_saber.py --saber redtoy")


if __name__ == "__main__":
    main()
