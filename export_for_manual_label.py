"""
Copy YOLO images to a folder for hand-drawn bbox annotation (Paint / ImageJ).

Run:
  python export_for_manual_label.py --saber redtoy

Opens folder:
  projects/models/saber_dataset/manual_annotate/{train,valid}/

Draw ONE rectangle outline around the saber in bright green (#00FF00), save over
the same filename, then:
  python import_manual_bboxes.py --saber redtoy
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
ANNOTATE_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "manual_annotate"
README_NAME = "HOW_TO_ANNOTATE.txt"


def parse_args():
    p = argparse.ArgumentParser(description="Export images for Paint/ImageJ bbox drawing")
    p.add_argument("--saber", default="redtoy", help="Dataset id (for messaging only)")
    p.add_argument("--source", default=None, help=f"YOLO root (default: {YOLO_BASE})")
    p.add_argument("--open", action="store_true", help="Open export folder in Finder")
    return p.parse_args()


def _write_readme(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / README_NAME).write_text(
        """Manual saber bounding boxes (Paint / ImageJ / Preview)

1. Open an image from train/ or valid/ in your editor.
2. Draw ONE rectangle OUTLINE around the lightsaber only (not your whole body).
   Use a THICK outline (Paint brush size 3–5, or ImageJ line width ≥3).
   Make sure all FOUR sides of the rectangle are visible — not just one edge.
3. Use EXACTLY this color for the box:
      Bright green  —  RGB(0, 255, 0)  /  hex #00FF00
   Paint: Colors → Edit colors → pure green, use rectangle OUTLINE (not fill).
   ImageJ: Set foreground to RGB(0,255,0), Edit → Selection → Draw (or Draw Rect).
4. Save OVER the same file (same filename, same folder).
5. Repeat for each image. Skip negatives in other/ — leave without a green box.
6. Import labels (original photos stay in yolo/ for training):
      cd projects/lightsaber
      python import_manual_bboxes.py --saber redtoy
7. Review optional:
      python review_saber_labels.py --saber redtoy --source ../models/saber_dataset/yolo_manual
8. Train:
      python train_saber.py --saber redtoy

Tips:
- Do NOT fill the rectangle — outline only (filled also works but outline is easier).
- If detection misses your box, re-draw with brighter green or run import with --tolerance 64.
- Training uses clean images from yolo/; green strokes are read only for box coordinates.
""",
        encoding="utf-8",
    )


def main():
    args = parse_args()
    source = Path(args.source) if args.source else YOLO_BASE
    if not (source / "train" / "images").is_dir():
        raise SystemExit(f"No YOLO images at {source}\nRun: python prepare_saber_yolo_dataset.py --saber {args.saber}")

    out = ANNOTATE_BASE
    _write_readme(out)
    copied = 0
    for split in ("train", "valid"):
        src_dir = source / split / "images"
        dst_dir = out / split
        dst_dir.mkdir(parents=True, exist_ok=True)
        for img in sorted(src_dir.glob("*")):
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            dst = dst_dir / img.name
            if not dst.exists() or dst.stat().st_mtime < img.stat().st_mtime:
                shutil.copy2(img, dst)
            copied += 1

    print(f"Exported {copied} images → {out}")
    print(f"  Read: {out / README_NAME}")
    print("\nDraw bright green (#00FF00) rectangle outlines, save each file, then:")
    print("  python import_manual_bboxes.py --saber redtoy")

    if args.open and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
