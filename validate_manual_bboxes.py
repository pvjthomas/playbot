"""Quick check: how many manual green boxes import cleanly."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from manual_bbox_color import extract_yolo_bbox_from_image, parse_color

ANNOTATE_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "manual_annotate"


def main():
    p = argparse.ArgumentParser(description="Validate green manual bbox annotations")
    p.add_argument("--split", default="train", choices=("train", "valid", "both"))
    p.add_argument("--min-area", type=float, default=0.01, help="Min box area to count as OK (default 1%%)")
    args = p.parse_args()

    splits = ("train", "valid") if args.split == "both" else (args.split,)
    green = parse_color("green")
    ok, thin, miss = [], [], []

    for split in splits:
        folder = ANNOTATE_BASE / split
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.jpg")):
            img = cv2.imread(str(path))
            if img is None:
                continue
            box = extract_yolo_bbox_from_image(img, green)
            if box is None or box[2] * box[3] < 0.001:
                miss.append(path.name)
                continue
            aspect = min(box[2], box[3]) / max(box[2], box[3])
            area = box[2] * box[3]
            if area >= args.min_area and aspect >= 0.12:
                ok.append((path.name, area))
            else:
                thin.append((path.name, area, aspect))

    print(f"OK ({len(ok)}): full rectangle detected")
    for name, area in ok[:10]:
        print(f"  {name}  {area:.0%}")
    if len(ok) > 10:
        print(f"  ... +{len(ok) - 10} more")

    print(f"\nThin/partial ({len(thin)}): redraw with thicker 4-sided box")
    for name, area, aspect in thin[:8]:
        print(f"  {name}  area={area:.0%} aspect={aspect:.2f}")

    print(f"\nNo green box ({len(miss)}): not annotated yet")
    print("\nRetry import preview:")
    print("  python import_manual_bboxes.py --saber redtoy --preview")


if __name__ == "__main__":
    main()
