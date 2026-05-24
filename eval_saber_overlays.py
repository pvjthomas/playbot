#!/usr/bin/env python3
"""Draw GT vs YOLO prediction overlays and build an HTML review gallery."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = SCRIPT_DIR / "../models/saber_runs/redtoy_25shot-2/weights/best.pt"
DEFAULT_DATA = SCRIPT_DIR / "../models/saber_dataset/yolo_manual"
DEFAULT_OUT = SCRIPT_DIR / "../models/saber_dataset/yolo_25shot_eval"


def yolo_norm_to_xyxy(box: list[float], w: int, h: int) -> tuple[int, int, int, int]:
    cx, cy, bw, bh = box
    x1 = int((cx - bw / 2) * w)
    y1 = int((cy - bh / 2) * h)
    x2 = int((cx + bw / 2) * w)
    y2 = int((cy + bh / 2) * h)
    return x1, y1, x2, y2


def iou_xywhn(a: list[float], b: list[float]) -> float:
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / (union + 1e-9)


def read_gt(label_path: Path) -> list[float] | None:
    if not label_path.exists():
        return None
    line = label_path.read_text().strip().splitlines()
    if not line:
        return None
    parts = line[0].split()
    if len(parts) < 5:
        return None
    return list(map(float, parts[1:5]))


def draw_box(
    img: np.ndarray,
    box: list[float],
    color: tuple[int, int, int],
    label: str,
    thickness: int = 3,
) -> None:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = yolo_norm_to_xyxy(box, w, h)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    y_text = max(th + 6, y1 - 6)
    cv2.rectangle(img, (x1, y_text - th - 8), (x1 + tw + 8, y_text + 2), color, -1)
    cv2.putText(img, label, (x1 + 4, y_text - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)


def predict_best(model: YOLO, img_path: Path, conf: float, imgsz: int) -> tuple[list[float] | None, float]:
    result = model.predict(str(img_path), conf=conf, imgsz=imgsz, verbose=False)[0]
    if result.boxes is None or len(result.boxes) == 0:
        return None, 0.0
    idx = int(result.boxes.conf.argmax())
    box = result.boxes[idx].xywhn[0].tolist()
    score = float(result.boxes.conf[idx])
    return box, score


def render_overlay(
    img_path: Path,
    gt: list[float],
    pred: list[float] | None,
    conf: float,
    iou: float,
    conf_threshold: float,
) -> np.ndarray:
    img = cv2.imread(str(img_path))
    if img is None:
        raise FileNotFoundError(img_path)

    draw_box(img, gt, (0, 220, 0), "GT (manual)")
    if pred is not None:
        draw_box(img, pred, (0, 0, 255), f"pred {conf:.3f}")
        status = "HIT" if iou >= 0.5 else ("OK" if iou >= 0.25 else "MISS")
        color = (0, 200, 0) if iou >= 0.5 else ((0, 180, 255) if iou >= 0.25 else (0, 0, 255))
    else:
        status = "NO DET"
        color = (0, 0, 255)

    banner = f"{status}  IoU={iou:.2f}  conf>={conf_threshold:.2f}"
    cv2.rectangle(img, (0, 0), (img.shape[1], 36), (20, 20, 20), -1)
    cv2.putText(img, banner, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return img


def make_contact_sheet(thumbs: list[np.ndarray], cols: int = 5, thumb_w: int = 320) -> np.ndarray:
    if not thumbs:
        raise ValueError("no thumbnails")
    resized = []
    for t in thumbs:
        h, w = t.shape[:2]
        scale = thumb_w / w
        resized.append(cv2.resize(t, (thumb_w, int(h * scale))))
    rows = []
    for i in range(0, len(resized), cols):
        chunk = resized[i : i + cols]
        while len(chunk) < cols:
            chunk.append(np.zeros_like(resized[0]))
        rows.append(cv2.hconcat(chunk))
    max_w = max(r.shape[1] for r in rows)
    padded = []
    for r in rows:
        if r.shape[1] < max_w:
            pad = np.zeros((r.shape[0], max_w - r.shape[1], 3), dtype=r.dtype)
            r = cv2.hconcat([r, pad])
        padded.append(r)
    return cv2.vconcat(padded)


def write_gallery_html(out_dir: Path, records: list[dict], conf: float) -> None:
    cards = []
    for rec in records:
        rel = html.escape(rec["preview"])
        title = html.escape(rec["name"])
        meta = html.escape(
            f"{rec['split']} · IoU {rec['iou']:.2f} · conf {rec['conf']:.3f} · {rec['status']}"
        )
        tone = "hit" if rec["iou"] >= 0.5 else ("warn" if rec["iou"] >= 0.25 else "miss")
        cards.append(
            f'<a class="card {tone}" href="{rel}">'
            f'<img src="{rel}" loading="lazy" alt="{title}"/>'
            f"<motion><div class='meta'><strong>{title}</strong><span>{meta}</span></div>"
            f"</a>"
        )
    cards_html = "".join(c.replace("<motion>", "") for c in cards)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Saber 25-shot eval — conf {conf:.2f}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #111; color: #eee; }}
    h1 {{ font-size: 1.4rem; font-weight: 600; }}
  .legend {{ margin: 12px 0 20px; color: #aaa; }}
  .legend span {{ margin-right: 16px; }}
  .legend .gt {{ color: #0f0; }}
  .legend .pred {{ color: #f44; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .card {{ display: block; text-decoration: none; color: inherit; border: 1px solid #333; border-radius: 8px; overflow: hidden; background: #1a1a1a; }}
  .card.hit {{ border-color: #2a6; }}
  .card.warn {{ border-color: #a80; }}
  .card.miss {{ border-color: #a33; }}
  .card img {{ width: 100%; display: block; }}
  .meta {{ padding: 10px 12px; font-size: 0.85rem; }}
  .meta strong {{ display: block; margin-bottom: 4px; word-break: break-all; }}
  .meta span {{ color: #aaa; }}
  .sheet {{ max-width: 100%; margin-top: 32px; border: 1px solid #333; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>Saber detector — 25 manual labels</h1>
  <p class="legend">
    <span class="gt">■ Green = your manual box (GT)</span>
    <span class="pred">■ Red = model prediction</span>
    · conf ≥ {conf:.2f} · imgsz 640
  </p>
  <motion><motion><div class="grid">
    {cards_html}
  </div>
  <h2 style="margin-top:32px;font-size:1.1rem">Contact sheet</h2>
  <img class="sheet" src="contact_sheet.jpg" alt="all overlays"/>
</body>
</html>
"""
    page = page.replace("<motion><motion>", "")
    (out_dir / "index.html").write_text(page)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--conf", type=float, default=0.01)
    parser.add_argument("--conf-compare", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    out_dir = args.out.resolve()
    previews = out_dir / "previews"
    previews.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(args.model.resolve()))
    records: list[dict] = []
    thumbs: list[np.ndarray] = []

    for split in ("train", "valid"):
        img_dir = args.data / split / "images"
        lbl_dir = args.data / split / "labels"
        for img_path in sorted(img_dir.glob("*.jpg")):
            gt = read_gt(lbl_dir / f"{img_path.stem}.txt")
            if gt is None:
                continue

            pred, score = predict_best(model, img_path, args.conf, args.imgsz)
            iou = iou_xywhn(gt, pred) if pred else 0.0
            overlay = render_overlay(img_path, gt, pred, score, iou, args.conf)

            preview_name = f"{split}_{img_path.stem}.jpg"
            preview_rel = f"previews/{preview_name}"
            cv2.imwrite(str(previews / preview_name), overlay)
            thumbs.append(overlay)

            pred_default, score_default = predict_best(model, img_path, args.conf_compare, args.imgsz)
            records.append(
                {
                    "split": split,
                    "name": img_path.name,
                    "preview": preview_rel,
                    "iou": iou,
                    "conf": score,
                    "status": "HIT" if iou >= 0.5 else ("OK" if iou >= 0.25 else "MISS"),
                    "detected_default_conf": pred_default is not None,
                    "conf_default": score_default,
                }
            )

    sheet = make_contact_sheet(thumbs)
    cv2.imwrite(str(out_dir / "contact_sheet.jpg"), sheet)
    write_gallery_html(out_dir, records, args.conf)

    summary = {
        "n": len(records),
        "conf": args.conf,
        "conf_compare": args.conf_compare,
        "mean_iou": sum(r["iou"] for r in records) / len(records),
        "iou_ge_0.5": sum(1 for r in records if r["iou"] >= 0.5),
        "iou_ge_0.25": sum(1 for r in records if r["iou"] >= 0.25),
        "misses_default_conf": sum(1 for r in records if not r["detected_default_conf"]),
        "per_image": records,
        "gallery": str(out_dir / "index.html"),
        "contact_sheet": str(out_dir / "contact_sheet.jpg"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Wrote {len(records)} overlays → {out_dir}")
    print(f"Open gallery: {out_dir / 'index.html'}")
    print(
        f"conf={args.conf}: mean IoU={summary['mean_iou']:.2f}, "
        f"hits={summary['iou_ge_0.5']}/{summary['n']}"
    )


if __name__ == "__main__":
    main()
