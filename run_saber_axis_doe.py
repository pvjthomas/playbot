#!/usr/bin/env python3
"""
Design-of-experiments runner for saber axis presets.

Replays one or more trial videos (or a webcam capture) under each preset in
``DOE_PRESET_ORDER`` and compares tracking quality metrics.

Metrics (higher composite = better unless noted):
  detect_rate     — fraction of frames with yolo / yolo_cached saber line
  color_pca_rate  — fraction of detections using color_pca axis (vs bbox)
  tip_in_frame    — fraction of detections with tip inside frame
  angle_jitter    — std dev of blade angle in degrees (lower is better)
  orient_flips    — count of horizontal/vertical/diagonal changes (lower is better)
  composite       — weighted score for ranking presets on this clip

Usage::

  cd projects/lightsaber
  python run_saber_axis_doe.py --saber redtoy --video swing_eval_logs/videos/session_*/trial_*.mp4
  python run_saber_axis_doe.py --saber redtoy --video-dir swing_eval_logs/videos/session_20260524_*/
  python run_saber_axis_doe.py --saber redtoy --camera laptop --seconds 5

Output: text table + ``swing_eval_logs/saber_axis_doe_<timestamp>.json``
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

import config
from camera import add_camera_cli, configure_camera_from_args, open_camera
from saber_axis_flags import DOE_PRESET_ORDER, apply_axis_preset
from saber_detector import SaberDetector, SaberLine
from saber_profiles import apply_saber_profile
from vision import AttackVision

LOG_DIR = Path(__file__).resolve().parent / "swing_eval_logs"


@dataclass
class PresetMetrics:
    preset: str
    frames: int
    detect_rate: float
    color_pca_rate: float
    tip_in_frame_rate: float
    angle_jitter_deg: float
    orient_flips: int
    composite: float


def _composite(
    detect_rate: float,
    color_pca_rate: float,
    tip_in_frame_rate: float,
    angle_jitter_deg: float,
    orient_flips: int,
    frames: int,
) -> float:
    flip_norm = orient_flips / max(frames - 1, 1)
    jitter_norm = min(angle_jitter_deg / 45.0, 1.0)
    return (
        0.30 * detect_rate
        + 0.20 * color_pca_rate
        + 0.15 * tip_in_frame_rate
        + 0.20 * (1.0 - jitter_norm)
        + 0.15 * (1.0 - flip_norm)
    )


def _run_on_frames(
    preset: str,
    frames: list[np.ndarray],
    *,
    saber_profile: str,
) -> PresetMetrics:
    apply_axis_preset(preset)
    apply_saber_profile(saber_profile)
    config.SABER_FUSE_YOLO_ONLY = True

    vision = AttackVision()
    detector = SaberDetector()
    angles: list[float] = []
    orientations: list[str] = []
    detections = 0
    color_pca = 0
    tip_ok = 0
    flips = 0
    last_orient: str | None = None

    try:
        for frame in frames:
            vision.detect_attack(frame)
            lm = vision.last_landmarks
            line = detector.detect_saber(frame, lm)
            if line is None or line.source == "arm":
                continue
            detections += 1
            angles.append(line.angle_deg)
            orientations.append(line.orientation)
            if line.axis_method == "color_pca":
                color_pca += 1
            if line.tip_in_frame:
                tip_ok += 1
            if last_orient is not None and line.orientation != last_orient:
                flips += 1
            last_orient = line.orientation
    finally:
        vision.close()
        detector.close()

    n = len(frames)
    detect_rate = detections / n if n else 0.0
    jitter = float(np.std(angles)) if len(angles) > 1 else 0.0
    return PresetMetrics(
        preset=preset,
        frames=n,
        detect_rate=round(detect_rate, 4),
        color_pca_rate=round(color_pca / detections, 4) if detections else 0.0,
        tip_in_frame_rate=round(tip_ok / detections, 4) if detections else 0.0,
        angle_jitter_deg=round(jitter, 2),
        orient_flips=flips,
        composite=round(
            _composite(
                detect_rate,
                color_pca / detections if detections else 0.0,
                tip_ok / detections if detections else 0.0,
                jitter,
                flips,
                n,
            ),
            4,
        ),
    )


def _load_video(path: Path, max_frames: int | None) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {path}")
    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
            if max_frames and len(frames) >= max_frames:
                break
    finally:
        cap.release()
    return frames


def _capture_live(seconds: float) -> list[np.ndarray]:
    camera = open_camera()
    frames: list[np.ndarray] = []
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            frame = camera.read_frame()
            if frame is not None:
                frames.append(frame)
    finally:
        camera.release()
    return frames


def _collect_videos(paths: list[Path], video_dir: Path | None) -> list[Path]:
    out: list[Path] = list(paths)
    if video_dir is not None:
        out.extend(sorted(video_dir.glob("**/*.mp4")))
    return [p for p in out if p.is_file()]


def _format_table(rows: list[PresetMetrics]) -> str:
    headers = (
        "preset",
        "detect",
        "color_pca",
        "tip_in",
        "jitter°",
        "flips",
        "composite",
    )
    lines = [
        f"{'preset':<14} {'detect':>7} {'color_pca':>9} {'tip_in':>7} "
        f"{'jitter°':>8} {'flips':>6} {'composite':>9}"
    ]
    for r in rows:
        lines.append(
            f"{r.preset:<14} {r.detect_rate:>7.2%} {r.color_pca_rate:>9.2%} "
            f"{r.tip_in_frame_rate:>7.2%} {r.angle_jitter_deg:>8.1f} "
            f"{r.orient_flips:>6} {r.composite:>9.3f}"
        )
    best = max(rows, key=lambda r: r.composite)
    lines.append(f"\nBest composite on this clip: {best.preset!r} ({best.composite:.3f})")
    baseline = next((r for r in rows if r.preset == "baseline"), None)
    if baseline and best.preset != "baseline":
        delta = best.composite - baseline.composite
        lines.append(
            f"  vs baseline: {delta:+.3f} composite "
            f"(jitter {baseline.angle_jitter_deg:.1f}° → {best.angle_jitter_deg:.1f}°)"
        )
    return "\n".join(lines)


def parse_args():
    p = argparse.ArgumentParser(description="DOE compare saber axis presets on video")
    add_camera_cli(p)
    p.add_argument("--saber", default="redtoy", help="Saber profile (default: redtoy)")
    p.add_argument(
        "--video",
        type=Path,
        action="append",
        default=[],
        help="Trial mp4 (repeatable); glob ok if shell expands",
    )
    p.add_argument(
        "--video-dir",
        type=Path,
        default=None,
        help="Directory of trial videos (recursive *.mp4)",
    )
    p.add_argument(
        "--seconds",
        type=float,
        default=0.0,
        help="If >0 and no --video, capture N seconds from --camera for DOE",
    )
    p.add_argument(
        "--presets",
        default=",".join(DOE_PRESET_ORDER),
        help=f"Comma-separated presets (default: full DOE order)",
    )
    p.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Cap frames per video (0 = all)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=LOG_DIR,
        help="Directory for DOE JSON report",
    )
    return p.parse_args()


def main():
    args = parse_args()
    configure_camera_from_args(args)
    videos = _collect_videos(args.video, args.video_dir)

    if not videos:
        if args.seconds <= 0:
            raise SystemExit(
                "Provide --video PATH, --video-dir DIR, or --seconds N with --camera"
            )
        print(f"Capturing {args.seconds:.1f}s from camera for DOE…")
        frames = _capture_live(args.seconds)
        clip_name = "live_capture"
    elif len(videos) == 1:
        cap = args.max_frames or None
        print(f"Loading {videos[0]} …")
        frames = _load_video(videos[0], cap)
        clip_name = videos[0].name
    else:
        frames = []
        cap = args.max_frames or None
        for v in videos:
            print(f"  loading {v.name}")
            frames.extend(_load_video(v, cap))
        clip_name = f"{len(videos)}_videos"

    if not frames:
        raise SystemExit("No frames to analyze")

    presets = [s.strip() for s in args.presets.split(",") if s.strip()]
    print(f"DOE: {len(frames)} frames × {len(presets)} presets\n")

    results: list[PresetMetrics] = []
    for preset in presets:
        print(f"  running {preset}…", flush=True)
        results.append(_run_on_frames(preset, frames, saber_profile=args.saber))

    print()
    print(_format_table(results))

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "clip": clip_name,
        "frames": len(frames),
        "saber_profile": args.saber,
        "presets": [asdict(r) for r in results],
        "recommended": max(results, key=lambda r: r.composite).preset,
    }
    out_path = args.out / f"saber_axis_doe_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
