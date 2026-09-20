"""Create a local, non-training inventory for a field image collection."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.source.iterdir(), key=lambda item: item.name.lower()):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except (OSError, ValueError):
            continue
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append({
            "image_id": path.name,
            "source_path": path.as_posix(),
            "sha256": sha256,
            "width": width,
            "height": height,
            "source_resolution": "original" if min(width, height) >= 600 else "thumbnail",
            "meter_family": "unknown",
            "display_bbox": None,
            "reading": None,
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "schema_version": "0.2.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source),
        "images": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "records": len(records),
        "original": sum(item["source_resolution"] == "original" for item in records),
        "thumbnail": sum(item["source_resolution"] == "thumbnail" for item in records),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
