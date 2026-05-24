#!/usr/bin/env python3
"""
Learn HSV thresholds from manual green-box labels → color_saber_detector calibration.

Uses clean photos (yolo/train/images) + your green boxes (manual_annotate/train).

  python calibrate_saber_color.py --saber redtoy
  python eval_color_saber.py --saber redtoy
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from color_saber_detector import ColorCalibration, save_calibration
from saber_label_io import iter_labeled_images, yolo_norm_to_xyxy


def _collect_hsv_samples(items, *, inset_ratio: float = 0.08, min_sat: int = 55):
    hs: list[int] = []
    ss: list[int] = []
    vs: list[int] = []
    areas: list[float] = []
    aspects: list[float] = []

    for item in items:
        bgr = cv2.imread(str(item.clean_path))
        if bgr is None:
            continue
        h, w = bgr.shape[:2]
        x1, y1, x2, y2 = yolo_norm_to_xyxy(item.box, w, h)
        mx = int((x2 - x1) * inset_ratio)
        my = int((y2 - y1) * inset_ratio)
        x1, y1 = x1 + mx, y1 + my
        x2, y2 = x2 - mx, y2 - my
        if x2 <= x1 or y2 <= y1:
            continue
        roi = cv2.cvtColor(bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        px = roi.reshape(-1, 3)
        red = ((px[:, 0] <= 25) | (px[:, 0] >= 165)) & (px[:, 1] >= min_sat)
        px = px[red]
        if len(px) < 40:
            continue
        hs.extend(px[:, 0].astype(int).tolist())
        ss.extend(px[:, 1].astype(int).tolist())
        vs.extend(px[:, 2].astype(int).tolist())
        areas.append(item.box[2] * item.box[3])
        aspects.append(max(item.box[2], item.box[3]) / max(min(item.box[2], item.box[3]), 1e-9))

    if not hs:
        raise RuntimeError("No HSV samples — check manual_annotate green boxes and yolo/train/images")

    h_arr = np.array(hs, dtype=np.int32)
    s_arr = np.array(ss, dtype=np.int32)
    v_arr = np.array(vs, dtype=np.int32)

    low_hue = h_arr[h_arr <= 25]
    high_hue = h_arr[h_arr >= 165]

    s_lo = int(np.percentile(s_arr, 5))
    s_hi = int(np.percentile(s_arr, 95))
    v_lo = int(np.percentile(v_arr, 5))
    v_hi = int(np.percentile(v_arr, 95))

    tight_low = (
        (max(0, int(np.percentile(low_hue, 2))), max(0, s_lo - 5), max(0, v_lo - 5)),
        (min(25, int(np.percentile(low_hue, 98))), min(255, s_hi + 5), min(255, v_hi + 5)),
    )
    tight_high = (
        (max(165, int(np.percentile(high_hue, 2)) if len(high_hue) else 165), max(0, s_lo - 5), max(0, v_lo - 5)),
        (179, min(255, s_hi + 5), min(255, v_hi + 5)),
    )

    loose_pad_s = 35
    loose_pad_v = 25
    loose_low = (
        (0, max(0, s_lo - loose_pad_s), max(0, v_lo - loose_pad_v)),
        (22, min(255, s_hi + loose_pad_s), min(255, v_hi + loose_pad_v)),
    )
    loose_high = (
        (163, max(0, s_lo - loose_pad_s), max(0, v_lo - loose_pad_v)),
        (180, min(255, s_hi + loose_pad_s), min(255, v_hi + loose_pad_v)),
    )

    return ColorCalibration(
        saber_id="",
        hsv_ranges_tight=[tight_low, tight_high],
        hsv_ranges_loose=[loose_low, loose_high],
        median_box_area_norm=float(np.median(areas)),
        median_aspect=float(np.median(aspects)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saber", default="redtoy")
    parser.add_argument("--split", default="train", choices=("train", "valid", "both"))
    args = parser.parse_args()

    splits = ("train", "valid") if args.split == "both" else (args.split,)
    items = iter_labeled_images(splits)
    if not items:
        raise SystemExit("No labeled images found in manual_annotate/")

    cal = _collect_hsv_samples(items)
    cal = ColorCalibration(
        saber_id=args.saber.strip().lower(),
        hsv_ranges_tight=cal.hsv_ranges_tight,
        hsv_ranges_loose=cal.hsv_ranges_loose,
        median_box_area_norm=cal.median_box_area_norm,
        median_aspect=cal.median_aspect,
    )
    path = save_calibration(cal)
    print(f"Calibrated from {len(items)} labeled images → {path}")
    print(f"  tight HSV: {cal.hsv_ranges_tight}")
    print(f"  median box area: {cal.median_box_area_norm:.1%}  aspect: {cal.median_aspect:.2f}")
    print("\nNext:")
    print(f"  python eval_color_saber.py --saber {args.saber}")
    print(f"  python saber_preview.py --saber {args.saber} --detector color --camera laptop")


if __name__ == "__main__":
    main()
