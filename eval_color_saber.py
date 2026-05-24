#!/usr/bin/env python3
"""Evaluate color saber detector vs manual labels; write HTML gallery."""

from __future__ import annotations

import argparse
import html
import json
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from color_saber_detector import ColorSaberDetector, load_calibration
from saber_label_io import iou_yolo_norm, iter_labeled_images, yolo_norm_to_xyxy

OUT_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "color_eval"


def draw_box(img, box, color, label: str) -> None:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = yolo_norm_to_xyxy(box, w, h)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    cv2.putText(img, label, (x1 + 4, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saber", default="redtoy")
    parser.add_argument("--split", default="train", choices=("train", "valid", "both"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cal = load_calibration(args.saber)
    detector = ColorSaberDetector(cal)
    pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=0)

    splits = ("train", "valid") if args.split == "both" else (args.split,)
    items = iter_labeled_images(splits)
    if not items:
        raise SystemExit("No labeled images in manual_annotate/")

    out_dir = args.out or (OUT_BASE / args.saber)
    preview_dir = out_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    records = []
    timings: list[float] = []

    for item in items:
        bgr = cv2.imread(str(item.clean_path))
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        lm = pose.process(rgb).pose_landmarks

        t0 = time.perf_counter()
        pred = detector.detect_bbox(bgr, lm)
        timings.append(time.perf_counter() - t0)

        iou = 0.0 if pred is None else iou_yolo_norm(item.box, pred)
        overlay = bgr.copy()
        draw_box(overlay, item.box, (0, 220, 0), "GT")
        if pred is not None:
            draw_box(overlay, pred, (0, 0, 255), "color")
        status = "HIT" if iou >= 0.5 else ("OK" if iou >= 0.25 else "MISS")
        cv2.putText(
            overlay,
            f"{status} IoU={iou:.2f}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 220, 255),
            2,
        )
        preview_name = f"{item.split}_{item.name}"
        cv2.imwrite(str(preview_dir / preview_name), overlay)
        records.append(
            {
                "split": item.split,
                "name": item.name,
                "iou": iou,
                "status": status,
                "detected": pred is not None,
                "preview": f"previews/{preview_name}",
            }
        )

    pose.close()
    detector.close()

    n = len(records)
    summary = {
        "saber": args.saber,
        "n": n,
        "mean_iou": sum(r["iou"] for r in records) / max(n, 1),
        "iou_ge_0.5": sum(1 for r in records if r["iou"] >= 0.5),
        "iou_ge_0.25": sum(1 for r in records if r["iou"] >= 0.25),
        "missed": sum(1 for r in records if not r["detected"]),
        "mean_ms": (sum(timings) / max(len(timings), 1)) * 1000,
        "per_image": records,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    cards = []
    for rec in records:
        tone = "hit" if rec["iou"] >= 0.5 else ("warn" if rec["iou"] >= 0.25 else "miss")
        cards.append(
            f'<a class="card {tone}" href="{html.escape(rec["preview"])}">'
            f'<img src="{html.escape(rec["preview"])}" loading="lazy"/>'
            f'<motion><div class="meta"><strong>{html.escape(rec["name"])}</strong>'
            f'<span>{rec["status"]} · IoU {rec["iou"]:.2f}</span></div></a>'
        )
    cards_html = "".join(c.replace("<motion>", "") for c in cards)
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>Color saber eval — {html.escape(args.saber)}</title>
<style>
body{{font-family:system-ui;background:#111;color:#eee;margin:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.card{{display:block;color:inherit;text-decoration:none;border:1px solid #333;border-radius:8px;overflow:hidden;background:#1a1a1a}}
.card.hit{{border-color:#2a6}}.card.warn{{border-color:#a80}}.card.miss{{border-color:#a33}}
.card img{{width:100%;display:block}}.meta{{padding:10px;font-size:.85rem}}.meta span{{color:#aaa}}
</style></head><body>
<h1>Color saber detector — {html.escape(args.saber)}</h1>
<p>Green = your manual box · Red = color detector · n={n} · mean IoU {summary["mean_iou"]:.2f} · {summary["mean_ms"]:.1f} ms/frame</p>
<div class="grid">{cards_html}</div></body></html>"""
    (out_dir / "index.html").write_text(page)

    print(f"Evaluated {n} images → {out_dir}")
    print(
        f"mean IoU={summary['mean_iou']:.2f}  "
        f"hits@0.5={summary['iou_ge_0.5']}/{n}  "
        f"hits@0.25={summary['iou_ge_0.25']}/{n}  "
        f"~{summary['mean_ms']:.1f} ms/frame (incl. pose for eval)"
    )
    print(f"Gallery: {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
