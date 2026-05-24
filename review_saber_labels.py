"""
Review auto-labels before training — y/n per image.

Run after prepare_saber_yolo_dataset.py:
  python review_saber_labels.py --saber redtoy

Keys:
  y — approve label (keep box, or keep as negative if no box)
  n — reject (exclude from reviewed training set)
  b — previous image
  q — quit (progress saved)

Approved images → projects/models/saber_dataset/yolo_reviewed/
Then train: python train_saber.py --saber redtoy
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2

YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
REVIEWED_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo_reviewed"
PROGRESS_NAME = "_review_progress.json"
CLASS_NAME = "lightsaber"


def parse_args():
    p = argparse.ArgumentParser(description="Review YOLO auto-labels (y/n)")
    p.add_argument("--saber", default="redtoy", help="Used for progress file naming only")
    p.add_argument(
        "--source",
        default=None,
        help=f"YOLO folder to review (default: {YOLO_BASE})",
    )
    return p.parse_args()


def _list_pairs(yolo_root: Path) -> list[tuple[str, Path, Path]]:
    """(split, image_path, label_path) in stable order."""
    pairs: list[tuple[str, Path, Path]] = []
    for split in ("train", "valid"):
        img_dir = yolo_root / split / "images"
        lbl_dir = yolo_root / split / "labels"
        if not img_dir.is_dir():
            continue
        for img in sorted(img_dir.glob("*")):
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            lbl = lbl_dir / f"{img.stem}.txt"
            pairs.append((split, img, lbl))
    return pairs


def _read_label(lbl_path: Path) -> str | None:
    if not lbl_path.is_file():
        return None
    text = lbl_path.read_text(encoding="utf-8").strip()
    return text if text else ""


def _yolo_to_xyxy(line: str, w: int, h: int) -> tuple[int, int, int, int] | None:
    parts = line.split()
    if len(parts) < 5:
        return None
    _, cx, cy, bw, bh = parts[0], *map(float, parts[1:5])
    x1 = int((cx - bw / 2) * w)
    y1 = int((cy - bh / 2) * h)
    x2 = int((cx + bw / 2) * w)
    y2 = int((cy + bh / 2) * h)
    return max(0, x1), max(0, y1), min(w - 1, x2), min(h - 1, y2)


def _draw_preview(frame, label_text: str | None) -> None:
    h, w = frame.shape[:2]
    if label_text:
        box = _yolo_to_xyxy(label_text, w, h)
        if box:
            x1, y1, x2, y2 = box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                "lightsaber (auto)",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
    else:
        cv2.putText(
            frame,
            "NEGATIVE — no box (no saber)",
            (12, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 200, 255),
            2,
        )


def _load_progress(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"decisions": {}, "index": 0}


def _save_progress(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _apply_decisions(
    pairs: list[tuple[str, Path, Path]],
    decisions: dict[str, str],
    out_root: Path,
) -> dict[str, int]:
    for split in ("train", "valid"):
        shutil.rmtree(out_root / split, ignore_errors=True)
        (out_root / split / "images").mkdir(parents=True)
        (out_root / split / "labels").mkdir(parents=True)

    stats = {"approved": 0, "rejected": 0, "pending": 0}
    for split, img, lbl in pairs:
        key = str(img)
        decision = decisions.get(key)
        if decision is None:
            stats["pending"] += 1
            continue
        if decision == "reject":
            stats["rejected"] += 1
            continue
        dst_img = out_root / split / "images" / img.name
        dst_lbl = out_root / split / "labels" / f"{img.stem}.txt"
        shutil.copy2(img, dst_img)
        label_text = _read_label(lbl)
        dst_lbl.write_text("" if label_text is None else (label_text + "\n"), encoding="utf-8")
        stats["approved"] += 1

    out_root.joinpath("data.yaml").write_text(
        f"""# Approved subset from review_saber_labels.py
path: {out_root.resolve()}
train: train/images
val: valid/images
names:
  0: {CLASS_NAME}
""",
        encoding="utf-8",
    )
    return stats


def main():
    args = parse_args()
    source = Path(args.source) if args.source else YOLO_BASE
    if not source.is_dir():
        raise SystemExit(f"No dataset at {source}\nRun: python prepare_saber_yolo_dataset.py --saber {args.saber}")

    pairs = _list_pairs(source)
    if not pairs:
        raise SystemExit(f"No images in {source}")

    progress_path = source / PROGRESS_NAME
    progress = _load_progress(progress_path)
    decisions: dict[str, str] = progress.get("decisions", {})
    idx = min(progress.get("index", 0), len(pairs) - 1)

    out_root = REVIEWED_BASE
    approved = sum(1 for v in decisions.values() if v == "approve")
    rejected = sum(1 for v in decisions.values() if v == "reject")

    print(f"Review auto-labels — {len(pairs)} images in {source}")
    print(f"Approved: {approved}  Rejected: {rejected}  Pending: {len(pairs) - approved - rejected}")
    print("Keys: y=approve  n=reject  b=back  q=quit (writes yolo_reviewed/)")
    print()

    window = "Label Review"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    try:
        while 0 <= idx < len(pairs):
            split, img_path, lbl_path = pairs[idx]
            frame = cv2.imread(str(img_path))
            if frame is None:
                idx += 1
                continue

            label_text = _read_label(lbl_path)
            preview = frame.copy()
            _draw_preview(preview, label_text)

            key = str(img_path)
            prior = decisions.get(key)
            status = {"approve": "APPROVED", "reject": "REJECTED"}.get(prior, "pending")
            area_pct = ""
            if label_text:
                parts = label_text.split()
                if len(parts) >= 5:
                    area_pct = f"  box={float(parts[3]) * float(parts[4]):.0%}"
            cv2.putText(
                preview,
                f"{idx + 1}/{len(pairs)} [{split}] {status}{area_pct}",
                (12, preview.shape[0] - 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (200, 200, 200),
                2,
            )
            cv2.putText(
                preview,
                "y=approve  n=reject  b=back  q=quit",
                (12, preview.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 200),
                2,
            )
            cv2.imshow(window, preview)
            k = cv2.waitKey(0) & 0xFF

            if k == ord("q"):
                break
            if k == ord("b"):
                idx = max(0, idx - 1)
                continue
            if k == ord("y"):
                decisions[key] = "approve"
                print(f"  approve {img_path.name}")
                idx += 1
            elif k == ord("n"):
                decisions[key] = "reject"
                print(f"  reject  {img_path.name}")
                idx += 1
            else:
                continue

            progress["decisions"] = decisions
            progress["index"] = idx
            _save_progress(progress_path, progress)
            stats = _apply_decisions(pairs, decisions, out_root)
            if idx % 10 == 0 or k == ord("q"):
                print(f"  reviewed set: {stats['approved']} approved, {stats['rejected']} rejected")

    finally:
        progress["decisions"] = decisions
        progress["index"] = idx
        _save_progress(progress_path, progress)
        stats = _apply_decisions(pairs, decisions, out_root)
        cv2.destroyAllWindows()

    print(f"\nDone. Reviewed dataset: {out_root}")
    print(f"  approved: {stats['approved']}  rejected: {stats['rejected']}  pending: {stats['pending']}")
    print("Train on approved only:")
    print("  python train_saber.py --saber redtoy")


if __name__ == "__main__":
    main()
