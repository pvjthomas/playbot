"""
Guided saber dataset collector — prompts you through each pose.

Run (auto capture every 3s — no spacebar):
  python collect_saber_trainer.py --saber redtoy --camera laptop --interval 3

Manual capture:
  python collect_saber_trainer.py --saber redtoy --camera laptop

Keys:
  SPACE — save photo (manual mode only)
  s     — skip rest of this prompt (next pose)
  b     — go back one prompt
  q     — quit session
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

import config
from camera import add_camera_cli, configure_camera_from_args, open_camera
from overlays import AttackOverlay
from saber_detector import SaberDetector, draw_saber_overlay
from saber_profiles import apply_saber_profile
from directions import print_direction_legend
from camera_mirror import (
    active_camera_source_key,
    get_mirror_preview,
    image_direction_cheat_sheet,
)
from saber_training_plan import session_for, session_summary
from vision import AttackVision

DATASET_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "raw"


def parse_args():
    p = argparse.ArgumentParser(description="Guided saber photo session for YOLO training")
    add_camera_cli(p)
    p.add_argument("--saber", default="redtoy", help="Saber id / session plan (default: redtoy)")
    p.add_argument(
        "--resume",
        action="store_true",
        help="Skip poses that already have enough images on disk",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=None,
        metavar="SEC",
        help="Auto-save every SEC seconds per pose (e.g. 3). Omit for manual SPACE capture.",
    )
    return p.parse_args()


def _count_existing(root: Path, pose_id: str) -> int:
    return len(list(root.glob(f"*_{pose_id}_*.jpg")))


def _draw_hud(
    frame,
    *,
    phase: str,
    prompt: str,
    pose_id: str,
    pose_index: int,
    pose_total: int,
    saved: int,
    target: int,
    counts: dict[str, int],
    session_total: int,
    session_saved: int,
    auto_interval: float | None = None,
    capture_in: float | None = None,
    mirror_hint: str | None = None,
) -> None:
    h, w = frame.shape[:2]
    hud_h = 140 if pose_id.startswith("strike_") else 118
    if auto_interval is not None:
        hud_h += 22
    if mirror_hint:
        hud_h += 18
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, hud_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    if auto_interval is not None:
        keys_line = f"[{phase}] Pose {pose_index}/{pose_total}  |  AUTO every {auto_interval:.1f}s  s=skip  b=back  q=quit"
    else:
        keys_line = f"[{phase}] Pose {pose_index}/{pose_total}  |  SPACE=save  s=skip  b=back  q=quit"
    cv2.putText(
        frame,
        keys_line,
        (12, 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 200),
        2,
    )
    cv2.putText(
        frame,
        f"This pose: {saved}/{target}   Session: {session_saved}/{session_total}",
        (12, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (200, 200, 200),
        1,
    )

    # Word-wrap prompt (~60 chars)
    words = prompt.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if len(trial) > 58 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    for i, text in enumerate(lines[:2]):
        cv2.putText(
            frame,
            text,
            (12, 78 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
        )

    if pose_id.startswith("strike_"):
        cv2.putText(
            frame,
            "HOLD end of strike (peak extension) — not wind-up | IMAGE left/right",
            (12, 128),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (0, 200, 255),
            1,
        )

    if auto_interval is not None and capture_in is not None:
        y = 128 if pose_id.startswith("strike_") else 106
        color = (0, 255, 0) if capture_in <= 0.3 else (0, 220, 255)
        cv2.putText(
            frame,
            f"Next capture in {max(0.0, capture_in):.1f}s",
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )

    summary = "  ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
    if mirror_hint:
        cv2.putText(
            frame,
            mirror_hint[:85],
            (12, hud_h - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (180, 220, 255),
            1,
        )
    cv2.putText(
        frame,
        summary,
        (12, h - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (180, 180, 180),
        1,
    )


def _save_frame(
    frame,
    *,
    saber_id: str,
    pose,
    dataset_root: Path,
    log_event,
) -> Path:
    ts = int(time.time() * 1000)
    filename = f"{saber_id}_{pose.label}_{pose.id}_{ts}.jpg"
    path = dataset_root / pose.label / filename
    cv2.imwrite(str(path), frame)
    log_event("save", pose.id, pose.label, str(path))
    return path


def main():
    args = parse_args()
    configure_camera_from_args(args)
    if args.camera is None:
        config.CAMERA_SOURCE = "laptop"
    apply_saber_profile(args.saber)

    saber_id = args.saber.strip().replace("/", "_")
    poses = session_for(saber_id)
    summary = session_summary(poses)
    dataset_root = DATASET_BASE / saber_id
    log_path = dataset_root / "_session_log.jsonl"

    for label in ("horizontal", "vertical", "diagonal", "other"):
        (dataset_root / label).mkdir(parents=True, exist_ok=True)

    print(f"Guided saber trainer — {saber_id}")
    print(f"Plan: {summary['poses']} prompts, {summary['total']} photos target")
    print(f"By folder: {summary['by_label']}")
    print(f"Saving to: {dataset_root}")
    if args.interval is not None and args.interval > 0:
        print(f"Auto capture every {args.interval:.1f}s — hold each pose, no spacebar needed.")
    else:
        print("Manual mode — press SPACE to save each photo.")
    print("Look at the preview window and follow each prompt.")
    print_direction_legend()
    source_key = active_camera_source_key()
    mirror_hint = image_direction_cheat_sheet(get_mirror_preview(source_key))

    camera = open_camera()
    vision = AttackVision()
    saber_det = SaberDetector()
    overlay = AttackOverlay()

    counts = {label: 0 for label in ("horizontal", "vertical", "diagonal", "other")}
    session_saved = 0
    pose_idx = 0

    def log_event(event: str, pose_id: str, label: str, path: str | None = None):
        entry = {
            "ts": time.time(),
            "event": event,
            "pose_id": pose_id,
            "label": label,
            "path": path,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    try:
        while pose_idx < len(poses):
            pose = poses[pose_idx]
            saved_this_pose = _count_existing(dataset_root / pose.label, pose.id) if args.resume else 0
            if args.resume and saved_this_pose >= pose.count:
                print(f"skip (resume) {pose.id} — already {saved_this_pose}/{pose.count}")
                pose_idx += 1
                continue

            print(f"\n--- Pose {pose_idx + 1}/{len(poses)} [{pose.phase}] ---")
            print(pose.prompt)
            print(f"Target: {pose.count} photos → folder '{pose.label}/'  (saved: {saved_this_pose})")

            next_capture_at = time.monotonic() + (args.interval or 0)
            if args.interval:
                print(f"  Hold pose — first capture in {args.interval:.1f}s")

            while saved_this_pose < pose.count:
                frame = camera.read_frame()
                if frame is None:
                    continue

                now = time.monotonic()
                auto_save = (
                    args.interval is not None
                    and args.interval > 0
                    and now >= next_capture_at
                )
                capture_in = (
                    max(0.0, next_capture_at - now) if args.interval else None
                )

                direction = vision.detect_attack(frame)
                landmarks = vision.last_landmarks
                sabers = saber_det.detect_all(frame, landmarks)
                preview = overlay.render_with_saber(
                    frame,
                    direction,
                    sabers[0] if sabers else None,
                    pose=landmarks,
                )
                for extra in sabers[1:]:
                    preview = draw_saber_overlay(preview, extra)

                _draw_hud(
                    preview,
                    phase=pose.phase,
                    prompt=pose.prompt,
                    pose_id=pose.id,
                    pose_index=pose_idx + 1,
                    pose_total=len(poses),
                    saved=saved_this_pose,
                    target=pose.count,
                    counts=counts,
                    session_total=summary["total"],
                    session_saved=session_saved,
                    auto_interval=args.interval,
                    capture_in=capture_in,
                    mirror_hint=mirror_hint,
                )

                cv2.imshow("Saber Trainer", preview)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    raise KeyboardInterrupt
                if key == ord("s"):
                    print(f"skipped remainder of {pose.id}")
                    break
                if key == ord("b"):
                    if pose_idx > 0:
                        pose_idx -= 1
                        print("back to previous pose")
                    break

                manual_save = args.interval is None and key == ord(" ")
                if not (manual_save or auto_save):
                    continue

                path = _save_frame(
                    frame,
                    saber_id=saber_id,
                    pose=pose,
                    dataset_root=dataset_root,
                    log_event=log_event,
                )
                saved_this_pose += 1
                session_saved += 1
                counts[pose.label] += 1
                print(f"  saved {path.name} ({saved_this_pose}/{pose.count})")
                if args.interval:
                    next_capture_at = time.monotonic() + args.interval

            pose_idx += 1

        print("\nSession complete!")
        print(f"Counts: {counts}")
        print(f"Total saved this run: {session_saved}")
        print(f"Log: {log_path}")
        print("\nNext: python prepare_saber_yolo_dataset.py --saber redtoy")
        print("       python train_saber.py --saber redtoy")

    except KeyboardInterrupt:
        print("\nStopped early.", counts)
    finally:
        vision.close()
        saber_det.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
