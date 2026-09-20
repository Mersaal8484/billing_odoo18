"""Build per-digit crops from reviewed meter display annotations.

The source annotations identify the complete display and its verified reading.
For roller registers, the digits are laid out in a fixed horizontal grid, so a
labelled register can bootstrap digit-level training examples.  These examples
are deliberately marked *weakly segmented*: a human should later correct the
digit boxes for the final gold dataset.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps


def split_for(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "test" if bucket < 15 else "val" if bucket < 25 else "train"


def crop_grid(display: Image.Image, digit_count: int, margin_x: float, margin_y: float):
    """Yield equal-width digit cells from the readable inner display area."""
    width, height = display.size
    left = round(width * margin_x)
    right = width - left
    top = round(height * margin_y)
    bottom = height - top
    inner_width = right - left
    for index in range(digit_count):
        cell_left = left + round(inner_width * index / digit_count)
        cell_right = left + round(inner_width * (index + 1) / digit_count)
        yield display.crop((cell_left, top, cell_right, bottom))


def main():
    parser = argparse.ArgumentParser(description="Create weakly segmented digit crops from reviewed displays")
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--meter-family", default="mechanical_roller")
    parser.add_argument("--margin-x", type=float, default=0.035)
    parser.add_argument("--margin-y", type=float, default=0.12)
    args = parser.parse_args()

    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    records = payload.get("images", [])
    rows = []
    for item in records:
        if item.get("meter_family") != args.meter_family or not item.get("display_bbox") or not item.get("reading"):
            continue
        source = args.root / Path(item["source_path"])
        if not source.exists():
            continue
        digits = item["reading"].replace(".", "")
        if not digits.isdigit() or len(digits) < 3:
            continue
        box = item["display_bbox"]
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("L")
            display = image.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
        for position, (digit, cell) in enumerate(zip(digits, crop_grid(display, len(digits), args.margin_x, args.margin_y))):
            key = f"{item['image_id']}:{position}"
            filename = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20] + ".png"
            destination = args.output / "digits" / digit / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            cell.save(destination, format="PNG", optimize=True)
            rows.append({
                "sample_id": key,
                "image_id": item["image_id"],
                "reading": item["reading"],
                "position": position,
                "digit": digit,
                "crop": str(destination.relative_to(args.output)),
                "split": split_for(item.get("group_id") or item.get("meter_number") or item["image_id"]),
                "meter_family": item["meter_family"],
                "label_quality": "weak_grid_from_single_review",
            })
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8"
    )
    print(json.dumps({"digits": len(rows), "records": len({row['image_id'] for row in rows}), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
