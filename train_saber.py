"""Train YOLO saber detector from prepared or Roboflow-exported dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

YOLO_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo"
MANUAL_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo_manual"
REVIEWED_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_dataset" / "yolo_reviewed"
RUNS_BASE = Path(__file__).resolve().parents[1] / "models" / "saber_runs"


def _default_data_yaml() -> Path:
    reviewed = REVIEWED_BASE / "data.yaml"
    if reviewed.is_file():
        return reviewed
    manual = MANUAL_BASE / "data.yaml"
    if manual.is_file():
        return manual
    return YOLO_BASE / "data.yaml"


def parse_args():
    p = argparse.ArgumentParser(description="Train YOLOv8 saber detector")
    p.add_argument("--saber", default="redtoy")
    p.add_argument("--data", default=None, help="Path to data.yaml (default: ../models/saber_dataset/yolo/data.yaml)")
    p.add_argument("--model", default="yolov8n.pt")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--name", default=None, help="Run name (default: <saber>_v1)")
    return p.parse_args()


def main():
    args = parse_args()
    data = Path(args.data) if args.data else _default_data_yaml()
    if not data.is_file():
        raise SystemExit(
            f"Missing {data}\n"
            "  python prepare_saber_yolo_dataset.py --saber redtoy\n"
            "  python review_saber_labels.py --saber redtoy   (optional y/n review)"
        )

    from ultralytics import YOLO

    name = args.name or f"{args.saber}_v1"
    RUNS_BASE.mkdir(parents=True, exist_ok=True)

    print(f"Training {args.model} on {data} → {RUNS_BASE / name}")
    model = YOLO(args.model)
    model.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        project=str(RUNS_BASE),
        name=name,
    )
    best = RUNS_BASE / name / "weights" / "best.pt"
    # Ultralytics may append -2, -3 if name exists
    if not best.is_file():
        alt = sorted(RUNS_BASE.glob(f"{name}*/weights/best.pt"), key=lambda p: p.stat().st_mtime)
        if alt:
            best = alt[-1]
    print(f"\nDone. Best weights: {best}")
    try:
        rel = best.relative_to(Path(__file__).resolve().parent)
    except ValueError:
        rel = best
    print(f'Set in config: SABER_MODEL = "{rel}"')


if __name__ == "__main__":
    main()
