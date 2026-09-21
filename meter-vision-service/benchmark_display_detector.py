"""Measure automatic display detection against human-reviewed screen boxes."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps

from app.display_detector import auto_detect_display


def iou(left: dict, right: dict) -> float:
    x1 = max(left["x"], right["x"])
    y1 = max(left["y"], right["y"])
    x2 = min(left["x"] + left["w"], right["x"] + right["w"])
    y2 = min(left["y"] + left["h"], right["y"] + right["h"])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = left["w"] * left["h"] + right["w"] * right["h"] - intersection
    return intersection / union if union else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("images", []):
        expected = item.get("display_bbox")
        source = args.root / Path(item.get("source_path", ""))
        if not expected or not source.exists():
            continue
        try:
            with Image.open(source) as raw:
                prediction = auto_detect_display(ImageOps.exif_transpose(raw).convert("RGB"))
        except (OSError, ValueError):
            continue
        score = iou(expected, prediction) if prediction else 0.0
        rows.append({"image_id": item["image_id"], "expected": expected,
                     "predicted": prediction, "iou": round(score, 4),
                     "detected": prediction is not None, "matched": score >= 0.5})
    report = {
        "records": len(rows),
        "detected": sum(row["detected"] for row in rows),
        "detection_rate": sum(row["detected"] for row in rows) / max(1, len(rows)),
        "matched_iou_50": sum(row["matched"] for row in rows),
        "matched_iou_50_rate": sum(row["matched"] for row in rows) / max(1, len(rows)),
        "mean_iou": sum(row["iou"] for row in rows) / max(1, len(rows)),
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "records", "detection_rate", "matched_iou_50_rate", "mean_iou"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
