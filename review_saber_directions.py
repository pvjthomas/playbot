"""
Review left/right attack direction on existing photos — no recollection needed.

Runs MediaPipe on saved images, shows what vision thinks, you confirm with L/R.

Label the **END pose** in each still — where the saber finishes in the image (peak
extension), not wind-up. Same rule as live `detect_attack()` and collection prompts.
See `directions.py` / `SABER-TRAINING.md`.

Run after prepare_saber_yolo_dataset.py (uses the same image files):
  python review_saber_directions.py --saber redtoy

Modes:
  spot      — sample images vision labels left/right (default)
  strike    — only strike_left / strike_right collection poses
  mismatches — vision disagrees with filename pose hint
  all       — every image (slow)

Keys:
  l — IMAGE left   (saber/strike toward left side of picture)
  r — IMAGE right
  h — high   c — center   n — none / not L-R
  s — skip   b — back     q — quit (progress saved)

Progress → projects/models/saber_dataset/direction_review/_progress.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2

from directions import ATTACK_SPECS
from overlays import AttackOverlay
from vision import AttackVision

YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
RAW_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "raw"
REVIEW_DIR = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "direction_review"
PROGRESS_NAME = "_progress.json"
LR_KEYS = {
    ord("l"): "left",
    ord("L"): "left",
    ord("r"): "right",
    ord("R"): "right",
    ord("h"): "high",
    ord("c"): "center",
    ord("n"): "none",
}


def parse_args():
    p = argparse.ArgumentParser(description="Review L/R direction on saved photos")
    p.add_argument("--saber", default="redtoy")
    p.add_argument(
        "--source",
        default=None,
        help=f"Image root (default: {YOLO_BASE} train+valid, else raw/<saber>/)",
    )
    p.add_argument(
        "--mode",
        choices=("spot", "strike", "mismatches", "all"),
        default="spot",
        help="Which images to show (default: spot-check vision left/right)",
    )
    p.add_argument(
        "--per-bucket",
        type=int,
        default=6,
        help="Max images per predicted L/R bucket in spot mode",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _list_images(root: Path, saber: str) -> list[Path]:
    images: list[Path] = []
    if (root / "train" / "images").is_dir():
        for split in ("train", "valid"):
            img_dir = root / split / "images"
            if img_dir.is_dir():
                images.extend(
                    p for p in sorted(img_dir.glob("*"))
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png")
                )
        return images

    raw = RAW_BASE / saber
    if raw.is_dir():
        for folder in ("horizontal", "vertical", "diagonal", "other"):
            d = raw / folder
            if d.is_dir():
                images.extend(
                    p for p in sorted(d.glob("*"))
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png")
                )
    return images


def filename_hint(stem: str) -> str | None:
    """Collection pose hint from filename (image-frame semantics)."""
    markers = (
        ("strike_left", "left"),
        ("_d_l2r_", "left"),
        ("_d_l2r", "left"),
        ("strike_right", "right"),
        ("_d_r2l_", "right"),
        ("_d_r2l", "right"),
        ("strike_high", "high"),
        ("strike_center", "center"),
        ("neg_", "none"),
    )
    for token, direction in markers:
        if token in stem:
            return direction
    return None


def _classify_all(images: list[Path], vision: AttackVision) -> list[dict]:
    records: list[dict] = []
    for i, path in enumerate(images):
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        predicted = vision.detect_attack(frame)
        hint = filename_hint(path.stem)
        records.append(
            {
                "path": str(path),
                "name": path.name,
                "predicted": predicted,
                "filename_hint": hint,
            }
        )
        if (i + 1) % 20 == 0:
            print(f"  scanned {i + 1}/{len(images)}...")
    return records


def _build_queue(records: list[dict], mode: str, per_bucket: int, seed: int) -> list[dict]:
    rng = random.Random(seed)

    if mode == "all":
        return records

    if mode == "strike":
        return [r for r in records if r["filename_hint"] in ("left", "right")]

    if mode == "mismatches":
        out = [
            r
            for r in records
            if r["filename_hint"] in ("left", "right")
            and r["predicted"] != r["filename_hint"]
            and r["predicted"] in ("left", "right", "none", "high", "center")
        ]
        rng.shuffle(out)
        return out

    # spot — sample from vision left/right buckets; fill gaps from strike filenames
    left_bucket = [r for r in records if r["predicted"] == "left"]
    right_bucket = [r for r in records if r["predicted"] == "right"]
    if len(right_bucket) < per_bucket:
        seen = {r["path"] for r in left_bucket + right_bucket}
        extras = [
            r
            for r in records
            if r["filename_hint"] == "right" and r["path"] not in seen
        ]
        rng.shuffle(extras)
        right_bucket.extend(extras[: per_bucket - len(right_bucket)])
    if len(left_bucket) < per_bucket:
        seen = {r["path"] for r in left_bucket + right_bucket}
        extras = [
            r
            for r in records
            if r["filename_hint"] == "left" and r["path"] not in seen
        ]
        rng.shuffle(extras)
        left_bucket.extend(extras[: per_bucket - len(left_bucket)])
    rng.shuffle(left_bucket)
    rng.shuffle(right_bucket)
    queue = left_bucket[:per_bucket] + right_bucket[:per_bucket]
    rng.shuffle(queue)
    return queue


def _load_progress(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"labels": {}, "index": 0}


def _save_progress(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _draw_lr_guides(frame) -> None:
    h, w = frame.shape[:2]
    cv2.putText(frame, "IMAGE LEFT", (8, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 120, 0), 2)
    cv2.putText(
        frame,
        "IMAGE RIGHT",
        (w - 140, h // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 120, 255),
        2,
    )
    cv2.line(frame, (w // 2, 0), (w // 2, h), (80, 80, 80), 1)


def _draw_review_overlay(
    frame,
    record: dict,
    user_label: str | None,
    idx: int,
    total: int,
) -> None:
    predicted = record["predicted"]
    hint = record["filename_hint"]
    match = ""
    if hint in ("left", "right") and predicted in ("left", "right"):
        match = "MATCH" if hint == predicted else "MISMATCH"

    lines = [
        f"{idx + 1}/{total}  vision={predicted!r}  filename_hint={hint!r}  {match}",
        f"Your label: {user_label or '(pending)'}",
        "l=IMAGE left  r=IMAGE right  h/c/n=other  s=skip  b=back  q=quit",
        ATTACK_SPECS["left"]["image_meaning"][:72],
    ]
    y = frame.shape[0] - 90
    for line in lines:
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 200), 1)
        y += 22


def _print_summary(records: list[dict], labels: dict[str, str]) -> None:
    pred_lr = sum(1 for r in records if r["predicted"] in ("left", "right"))
    labeled = len(labels)
    agree = sum(
        1
        for r in records
        if labels.get(r["path"]) == r["predicted"]
        and r["predicted"] in ("left", "right", "high", "center", "none")
    )
    hint_agree = sum(
        1
        for r in records
        if r["filename_hint"] in ("left", "right")
        and labels.get(r["path"]) == r["filename_hint"]
    )
    hint_total = sum(1 for r in records if r["filename_hint"] in ("left", "right") and r["path"] in labels)
    print(
        f"\nSummary: {pred_lr} images with L/R vision labels, "
        f"you labeled {labeled}, vision agrees {agree}, "
        f"filename agrees {hint_agree}/{hint_total}"
    )


def main():
    args = parse_args()
    source = Path(args.source) if args.source else YOLO_BASE
    images = _list_images(source, args.saber)
    if not images:
        raise SystemExit(
            f"No images under {source}\n"
            f"Run: python prepare_saber_yolo_dataset.py --saber {args.saber}"
        )

    progress_path = REVIEW_DIR / PROGRESS_NAME
    progress = _load_progress(progress_path)
    labels: dict[str, str] = progress.get("labels", {})

    print(f"Scanning {len(images)} images with AttackVision (static)...")
    vision = AttackVision(static_image_mode=True)
    overlay = AttackOverlay()
    records = _classify_all(images, vision)

    by_pred: dict[str, int] = {}
    for r in records:
        by_pred[r["predicted"]] = by_pred.get(r["predicted"], 0) + 1
    print("Vision counts:", ", ".join(f"{k}={v}" for k, v in sorted(by_pred.items())))

    queue = _build_queue(records, args.mode, args.per_bucket, args.seed)
    if not queue:
        vision.close()
        raise SystemExit(f"No images for mode={args.mode!r}")

    idx = min(progress.get("index", 0), len(queue) - 1)
    print(f"\nDirection review — {len(queue)} images (mode={args.mode})")
    print("Where does the saber FINISH in this photo (END pose)? Press L or R.")
    print()

    window = "Direction Review (L/R)"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    try:
        while 0 <= idx < len(queue):
            record = queue[idx]
            path = Path(record["path"])
            frame = cv2.imread(str(path))
            if frame is None:
                idx += 1
                continue

            direction = vision.detect_attack(frame)
            preview = overlay.render(
                frame,
                direction,
                pose=vision.last_landmarks,
            )

            _draw_lr_guides(preview)
            user_label = labels.get(record["path"])
            _draw_review_overlay(preview, {**record, "predicted": direction}, user_label, idx, len(queue))
            cv2.imshow(window, preview)

            k = cv2.waitKey(0) & 0xFF
            if k == ord("q"):
                break
            if k == ord("b"):
                idx = max(0, idx - 1)
                continue
            if k == ord("s"):
                idx += 1
                continue
            if k in LR_KEYS:
                label = LR_KEYS[k]
                labels[record["path"]] = label
                hint = record["filename_hint"]
                note = ""
                if hint in ("left", "right"):
                    note = " (matches filename)" if label == hint else f" (filename was {hint})"
                print(f"  {path.name}: you={label!r} vision={direction!r}{note}")
                idx += 1
                progress["labels"] = labels
                progress["index"] = idx
                progress["mode"] = args.mode
                progress["queue"] = [r["path"] for r in queue]
                _save_progress(progress_path, progress)
                continue
    finally:
        vision.close()
        progress["labels"] = labels
        progress["index"] = idx
        _save_progress(progress_path, progress)
        cv2.destroyAllWindows()

    _print_summary(queue, labels)
    print(f"Progress saved: {progress_path}")
    print("Next: python review_saber_labels.py --saber redtoy  (YOLO box review)")


if __name__ == "__main__":
    main()
