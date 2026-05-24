"""
Import hand-drawn bounding boxes from green (or custom) rectangle outlines.

After drawing in manual_annotate/:
  python import_manual_bboxes.py --saber redtoy
  python import_manual_bboxes.py --saber redtoy --preview   # check before writing

Writes labels to yolo_manual/ (clean images copied from yolo/, labels from color).
Train with:
  python train_saber.py --saber redtoy
(review_saber_labels.py --source ../models/saber_dataset/yolo_manual)
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2

from manual_bbox_color import (
    PRESET_COLORS,
    annotation_mask,
    extract_yolo_bbox_from_image,
    parse_color,
    yolo_line,
)

YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
ANNOTATE_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "manual_annotate"
OUT_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo_manual"
PREVIEW_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "manual_import_preview"
CLASS_NAME = "lightsaber"


def parse_args():
    p = argparse.ArgumentParser(description="Import Paint/ImageJ colored bbox annotations")
    p.add_argument("--saber", default="redtoy")
    p.add_argument("--annotated", default=None, help=f"Drawn images (default: {ANNOTATE_BASE})")
    p.add_argument("--images", default=None, help=f"Clean training images (default: {YOLO_BASE})")
    p.add_argument("--out", default=None, help=f"Output YOLO dataset (default: {OUT_BASE})")
    p.add_argument(
        "--color",
        default="green",
        help=f"Annotation stroke color: {', '.join(PRESET_COLORS)} or #RRGGBB or R,G,B",
    )
    p.add_argument("--tolerance", type=int, default=48, help="RGB match tolerance per channel")
    p.add_argument("--preview", action="store_true", help="Write preview overlays, do not replace out/")
    p.add_argument("--apply", action="store_true", help="Write to --out (required unless --preview)")
    p.add_argument(
        "--labeled-only",
        action="store_true",
        help="Only copy images where a green box was detected (for small test sets)",
    )
    p.add_argument(
        "--min-green-pixels",
        type=int,
        default=1500,
        help="With --labeled-only: require at least this many green stroke pixels (default 1500)",
    )
    return p.parse_args()


def _draw_yolo_box(frame, label_text: str, color=(0, 255, 0)):
    h, w = frame.shape[:2]
    parts = label_text.strip().split()
    if len(parts) < 5:
        return frame
    _, cx, cy, bw, bh = parts[0], *map(float, parts[1:5])
    x1 = int((cx - bw / 2) * w)
    y1 = int((cy - bh / 2) * h)
    x2 = int((cx + bw / 2) * w)
    y2 = int((cy + bh / 2) * h)
    out = frame.copy()
    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    cv2.putText(out, "imported", (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return out


def main():
    args = parse_args()
    if not args.preview and not args.apply:
        print("Use --apply to write yolo_manual/, or --preview to inspect detections first.")
        raise SystemExit(2)

    annotate_root = Path(args.annotated) if args.annotated else ANNOTATE_BASE
    image_root = Path(args.images) if args.images else YOLO_BASE
    out_root = PREVIEW_BASE if args.preview else (Path(args.out) if args.out else OUT_BASE)
    color_bgr = parse_color(args.color)

    stats = {"labeled": 0, "negative": 0, "missed": 0, "train": 0, "valid": 0, "skipped_unlabeled": 0}

    for split in ("train", "valid"):
        ann_dir = annotate_root / split
        clean_dir = image_root / split / "images"
        if not ann_dir.is_dir():
            continue
        out_img = out_root / split / "images"
        out_lbl = out_root / split / "labels"
        out_img.mkdir(parents=True, exist_ok=True)
        out_lbl.mkdir(parents=True, exist_ok=True)

        for ann_path in sorted(ann_dir.glob("*")):
            if ann_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            clean_path = clean_dir / ann_path.name
            if not clean_path.is_file():
                print(f"  skip (no clean image): {ann_path.name}")
                continue

            annotated = cv2.imread(str(ann_path))
            clean = cv2.imread(str(clean_path))
            if annotated is None or clean is None:
                stats["missed"] += 1
                continue

            box = extract_yolo_bbox_from_image(
                annotated,
                color_bgr,
                tolerance=args.tolerance,
            )
            green_px = cv2.countNonZero(annotation_mask(annotated, color_bgr, args.tolerance))

            if args.labeled_only and (box is None or green_px < args.min_green_pixels):
                stats["skipped_unlabeled"] += 1
                continue

            if args.apply or args.preview:
                shutil.copy2(clean_path, out_img / ann_path.name)

            if box is None:
                stats["negative"] += 1
                (out_lbl / f"{ann_path.stem}.txt").write_text("", encoding="utf-8")
                print(f"  no box: {ann_path.name} (empty label — negative or fix color)")
            else:
                line = yolo_line(box)
                (out_lbl / f"{ann_path.stem}.txt").write_text(line, encoding="utf-8")
                stats["labeled"] += 1
                area = box[2] * box[3]
                print(f"  ok {ann_path.name}  box={area:.0%}")

            if args.preview and box is not None:
                prev = _draw_yolo_box(clean, line)
                cv2.imwrite(str(out_root / split / f"{ann_path.stem}_preview.jpg"), prev)

            stats[split] += 1

    if args.apply or args.preview:
        out_root.joinpath("data.yaml").write_text(
            f"""# {'Preview' if args.preview else 'Manual'} bbox import — import_manual_bboxes.py
path: {out_root.resolve()}
train: train/images
val: valid/images
names:
  0: {CLASS_NAME}
""",
            encoding="utf-8",
        )

    print(
        f"\nDone — labeled={stats['labeled']}  empty={stats['negative']}  "
        f"missed={stats['missed']}  skipped_unlabeled={stats['skipped_unlabeled']}"
    )
    print(f"  train={stats['train']}  valid={stats['valid']}")
    if args.preview:
        print(f"Previews: {out_root}")
        print("If boxes look good: python import_manual_bboxes.py --saber redtoy --apply")
    else:
        print(f"Dataset: {out_root}")
        print("  python review_saber_labels.py --saber redtoy --source ../models/saber_dataset/yolo_manual")
        print("  python train_saber.py --saber redtoy")


if __name__ == "__main__":
    main()
