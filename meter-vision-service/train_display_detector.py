"""Train and evaluate a local YOLO display-window detector.

This is a bootstrap trainer.  It must not replace the manual display crop in
production until the held-out IoU gate and double-review data requirements are
met.
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, help="YOLO dataset.yaml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--weights", default="yolo11n.pt")
    args = parser.parse_args()
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise SystemExit("Install optional training dependencies first: pip install ultralytics") from error

    args.output.mkdir(parents=True, exist_ok=True)
    model = YOLO(args.weights)
    model.train(
        data=str(args.dataset.resolve()), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, workers=0, project=str(args.output), name="run",
        exist_ok=True, pretrained=True, seed=42, deterministic=True,
    )
    metrics = model.val(data=str(args.dataset.resolve()), imgsz=args.imgsz, batch=args.batch, workers=0)
    summary = {
        "epochs": args.epochs, "imgsz": args.imgsz, "batch": args.batch,
        "weights": args.weights, "results_dir": str(getattr(model.trainer, "save_dir", args.output / "run")),
        "map50": float(metrics.box.map50), "map50_95": float(metrics.box.map),
        "warning": "Bootstrap detector from single-review labels; do not enable auto-approval.",
    }
    (args.output / "training-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
