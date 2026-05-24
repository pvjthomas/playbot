"""
Roboflow helpers for saber YOLO — upload raw images, download labeled export.

Requires: pip install -r requirements-vision.txt
          export ROBOFLOW_API_KEY=...   # https://app.roboflow.com/settings/api

Upload unlabeled (label in Roboflow web UI):
  python roboflow_saber.py upload --saber redtoy

Upload with auto red-HSV boxes as predictions to review in Roboflow:
  python roboflow_saber.py upload --saber redtoy --prelabel

After labeling + generating a version in Roboflow, download YOLOv8 export:
  python roboflow_saber.py download --project lightsaber-redtoy --version 1
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

RAW_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "raw"
YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
STAGING_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "roboflow_upload"
DEFAULT_PROJECT = "lightsaber-redtoy"


def _api_key() -> str:
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "Set ROBOFLOW_API_KEY (https://app.roboflow.com/settings/api)\n"
            "  export ROBOFLOW_API_KEY=your_key"
        )
    return key


def _collect_raw_images(raw_root: Path) -> list[Path]:
    paths: list[Path] = []
    for label_dir in sorted(raw_root.iterdir()):
        if not label_dir.is_dir() or label_dir.name.startswith("_"):
            continue
        paths.extend(sorted(label_dir.glob("*.jpg")))
        paths.extend(sorted(label_dir.glob("*.png")))
    return paths


def _stage_for_upload(saber_id: str, *, prelabel: bool) -> Path:
    """Flat folder for Roboflow upload (images + optional YOLO txt)."""
    raw_root = RAW_BASE / saber_id
    if not raw_root.is_dir():
        raise SystemExit(f"No images at {raw_root}\nRun: python collect_saber_trainer.py --saber {saber_id}")

    images = _collect_raw_images(raw_root)
    if not images:
        raise SystemExit(f"No .jpg/.png in {raw_root}")

    stage = STAGING_BASE / saber_id
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)

    if prelabel:
        from prepare_saber_yolo_dataset import _bbox_from_mask, _red_mask

        import cv2

        labeled = 0
        for src in images:
            dst = stage / src.name
            shutil.copy2(src, dst)
            is_neg = NEGATIVE_FOLDER in src.parts
            if is_neg:
                (stage / f"{src.stem}.txt").write_text("")
                continue
            frame = cv2.imread(str(src))
            if frame is None:
                continue
            mask = _red_mask(frame)
            box = _bbox_from_mask(mask, 0.002)
            if box:
                cx, cy, bw, bh = box
                (stage / f"{src.stem}.txt").write_text(
                    f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n"
                )
                labeled += 1
        (stage / "data.yaml").write_text(
            "names:\n  0: lightsaber\n",
            encoding="utf-8",
        )
        print(f"Staged {len(images)} images, {labeled} pre-labels (review in Roboflow)")
    else:
        for src in images:
            shutil.copy2(src, stage / src.name)
        print(f"Staged {len(images)} unlabeled images")

    return stage


NEGATIVE_FOLDER = "other"


def cmd_upload(args) -> None:
    import roboflow

    saber_id = args.saber.strip().replace("/", "_")
    stage = _stage_for_upload(saber_id, prelabel=args.prelabel)
    project_name = args.project or f"lightsaber-{saber_id}"

    rf = roboflow.Roboflow(api_key=_api_key())
    workspace = rf.workspace()

    print(f"Uploading {stage} → project {project_name!r} ...")
    workspace.upload_dataset(
        str(stage),
        project_name,
        num_workers=min(10, len(list(stage.glob('*.jpg'))) or 1),
        project_license="MIT",
        project_type="object-detection",
        batch_name=f"{saber_id}-mac-webcam",
        is_prediction=args.prelabel,
    )
    print(f"Done. Label at: https://app.roboflow.com/ → project {project_name!r}")
    print("After labeling: Generate → Export YOLOv8, or run:")
    print(f"  python roboflow_saber.py download --project {project_name} --version N")


def cmd_download(args) -> None:
    import roboflow

    rf = roboflow.Roboflow(api_key=_api_key())
    project = rf.workspace().project(args.project)
    version = project.version(int(args.version))
    out = YOLO_BASE if args.output is None else Path(args.output)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {args.project} v{args.version} (yolov8) → {out}")
    version.download("yolov8", location=str(out))
    print(f"Ready. Train locally: yolo detect train data={out / 'data.yaml'} model=yolov8n.pt")


def main():
    p = argparse.ArgumentParser(description="Roboflow upload/download for saber training")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("upload", help="Upload raw images to Roboflow for labeling")
    up.add_argument("--saber", default="redtoy")
    up.add_argument("--project", default=None, help=f"Roboflow project id (default: lightsaber-<saber>)")
    up.add_argument(
        "--prelabel",
        action="store_true",
        help="Upload auto red-HSV boxes as predictions to review (faster than from scratch)",
    )
    up.set_defaults(func=cmd_upload)

    dl = sub.add_parser("download", help="Download labeled YOLOv8 export from Roboflow")
    dl.add_argument("--project", default=DEFAULT_PROJECT)
    dl.add_argument("--version", required=True, type=int, help="Dataset version number in Roboflow")
    dl.add_argument("--output", default=None, help=f"Output dir (default: {YOLO_BASE})")
    dl.set_defaults(func=cmd_download)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
