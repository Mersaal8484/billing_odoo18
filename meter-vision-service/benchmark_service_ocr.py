"""Measure the local specialized OCR against reviewed annotations."""

import argparse
import base64
import json
from pathlib import Path

from app.inference import analyze
from app.schemas import DisplayBBox, InferenceRequest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--meter-family")
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("images", []):
        if args.meter_family and item.get("meter_family") != args.meter_family:
            continue
        if not item.get("display_bbox") or not item.get("reading"):
            continue
        source = args.root / Path(item["source_path"])
        if not source.exists():
            continue
        reading = item["reading"]
        decimal_places = len(reading.split(".", 1)[1]) if "." in reading else 0
        result = analyze(InferenceRequest(
            request_id=item["image_id"],
            image_base64=base64.b64encode(source.read_bytes()).decode("ascii"),
            display_bbox=DisplayBBox(**item["display_bbox"]),
            meter_type_hint=item.get("meter_family"),
            expected_digits=len(reading.replace(".", "")),
            decimal_places=decimal_places,
        ))
        predicted = result.reading.value
        rows.append({"image_id": item["image_id"], "expected": reading, "predicted": predicted,
                     "confidence": result.reading.confidence, "exact": predicted == reading,
                     "flags": result.flags})
    exact = sum(row["exact"] for row in rows)
    report = {"records": len(rows), "exact": exact, "exact_accuracy": exact / max(1, len(rows)), "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("records", "exact", "exact_accuracy")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
