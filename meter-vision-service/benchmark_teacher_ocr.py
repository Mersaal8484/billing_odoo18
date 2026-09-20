"""Benchmark EasyOCR as a teacher against reviewed meter-display labels."""

import argparse
import json
import re
from pathlib import Path

import easyocr
import numpy as np
from PIL import Image, ImageOps


DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def candidate_from(results):
    candidates = []
    for _box, text, confidence in results:
        value = text.translate(DIGIT_MAP).replace(",", ".")
        for number in re.findall(r"\d+(?:\.\d+)?", value):
            candidates.append((number, float(confidence)))
    if not candidates:
        return None, 0.0
    return max(candidates, key=lambda item: (len(item[0].replace(".", "")), item[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--meter-family")
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    rows = []
    for item in payload.get("images", []):
        if args.meter_family and item.get("meter_family") != args.meter_family:
            continue
        if not item.get("reading") or not item.get("display_bbox"):
            continue
        source = args.root / Path(item["source_path"])
        if not source.exists():
            continue
        box = item["display_bbox"]
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            crop = image.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
            array = np.asarray(crop)
        predicted, confidence = candidate_from(reader.readtext(array, detail=1, allowlist="0123456789."))
        rows.append({"image_id": item["image_id"], "meter_family": item.get("meter_family"),
                     "expected": item["reading"], "predicted": predicted, "confidence": confidence,
                     "exact": predicted == item["reading"]})
    exact = sum(row["exact"] for row in rows)
    report = {"engine": "easyocr-1.7.2", "records": len(rows), "exact": exact,
              "exact_accuracy": exact / max(1, len(rows)), "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("engine", "records", "exact", "exact_accuracy")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
