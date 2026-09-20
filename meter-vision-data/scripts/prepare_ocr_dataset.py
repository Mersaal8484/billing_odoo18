"""Create reviewed display crops and a grouped train/val/test manifest."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


def split_for(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode()).hexdigest()[:8], 16) % 100
    return "test" if bucket < 15 else "val" if bucket < 25 else "train"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    records = payload.get("images", []) if isinstance(payload, dict) else payload
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in records:
        if item.get("label_state") not in {"double_review", "gold"} or not item.get("training_eligible"):
            continue
        source = Path(item.get("source_path", item["image_id"]))
        if not source.is_absolute():
            source = args.root / source
        if not source.exists():
            continue
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            box = item["display_bbox"]
            crop = image.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
            group = item.get("group_id") or item.get("meter_number") or item["image_id"]
            split = split_for(group)
            output_name = hashlib.sha256(item["image_id"].encode()).hexdigest()[:16] + ".png"
            destination = args.output / "crops" / split / output_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            crop.save(destination, format="PNG", optimize=True)
        rows.append({"image_id": item["image_id"], "crop": str(destination.relative_to(args.output)),
                     "reading": item["reading"], "meter_family": item.get("meter_family", "unknown"),
                     "group_id": group, "split": split})
    (args.output / "manifest.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    print(json.dumps({"records": len(rows), "output": str(args.output), "splits": {
        name: sum(row["split"] == name for row in rows) for name in ("train", "val", "test")}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
