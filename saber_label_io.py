"""
Load manual saber labels (green boxes) + clean training images.

Annotations: projects/models/saber_dataset/manual_annotate/{train,valid}/
Clean photos:  projects/models/saber_dataset/yolo/{train,valid}/images/
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

from manual_bbox_color import extract_yolo_bbox_from_image, parse_color

DATASET_ROOT = Path(__file__).resolve().parents[1] / "models" / "saber_dataset"
ANNOTATE_ROOT = DATASET_ROOT / "manual_annotate"
CLEAN_ROOT = DATASET_ROOT / "yolo"
ANNOTATION_COLOR = parse_color("green")


@dataclass(frozen=True)
class LabeledImage:
    split: str
    name: str
    clean_path: Path
    annotate_path: Path
    box: tuple[float, float, float, float]  # YOLO cx cy w h normalized


def yolo_norm_to_xyxy(box: tuple[float, float, float, float], w: int, h: int) -> tuple[int, int, int, int]:
    cx, cy, bw, bh = box
    x1 = int((cx - bw / 2) * w)
    y1 = int((cy - bh / 2) * h)
    x2 = int((cx + bw / 2) * w)
    y2 = int((cy + bh / 2) * h)
    return x1, y1, x2, y2


def xyxy_to_yolo_norm(x1: int, y1: int, x2: int, y2: int, w: int, h: int) -> tuple[float, float, float, float]:
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    return ((x1 + x2) / 2 / w, (y1 + y2) / 2 / h, bw / w, bh / h)


def iou_yolo_norm(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / (union + 1e-9)


def iter_labeled_images(splits: tuple[str, ...] = ("train", "valid")) -> list[LabeledImage]:
    """Pairs with a non-empty green bbox on the annotated copy."""
    out: list[LabeledImage] = []
    for split in splits:
        ann_dir = ANNOTATE_ROOT / split
        img_dir = CLEAN_ROOT / split / "images"
        if not ann_dir.is_dir() or not img_dir.is_dir():
            continue
        for ann_path in sorted(ann_dir.glob("*.jpg")):
            clean_path = img_dir / ann_path.name
            if not clean_path.is_file():
                continue
            ann_bgr = cv2.imread(str(ann_path))
            if ann_bgr is None:
                continue
            box = extract_yolo_bbox_from_image(ann_bgr, ANNOTATION_COLOR)
            if box is None or box[2] * box[3] < 1e-4:
                continue
            out.append(
                LabeledImage(
                    split=split,
                    name=ann_path.name,
                    clean_path=clean_path,
                    annotate_path=ann_path,
                    box=box,
                )
            )
    return out
