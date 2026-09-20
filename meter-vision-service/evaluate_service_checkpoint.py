"""Evaluate the optional experimental checkpoint through service inference."""

import argparse
import base64
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "val", "test"), default=None)
    parser.add_argument("--meter-family")
    args = parser.parse_args()
    os.environ["METER_VISION_EXPERIMENTAL_CRNN"] = str(args.checkpoint.resolve())
    from app.inference import analyze
    from app.schemas import DisplayBBox, InferenceRequest

    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    records = payload.get("images", [])
    rows = []
    for item in records:
        if args.meter_family and item.get("meter_family") != args.meter_family:
            continue
        source = args.root / Path(item["source_path"])
        if not source.exists() or not item.get("display_bbox") or not item.get("reading"):
            continue
        result = analyze(InferenceRequest(
            request_id=item["image_id"],
            image_base64=base64.b64encode(source.read_bytes()).decode("ascii"),
            display_bbox=DisplayBBox(**item["display_bbox"]),
        ))
        predicted = result.reading.value
        rows.append({"image_id": item["image_id"], "expected": item["reading"], "predicted": predicted,
                     "exact": predicted == item["reading"], "flags": result.flags})
    exact = sum(row["exact"] for row in rows)
    output = {"records": len(rows), "exact": exact, "exact_accuracy": exact / max(1, len(rows)),
              "mismatches": [row for row in rows if not row["exact"]]}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
