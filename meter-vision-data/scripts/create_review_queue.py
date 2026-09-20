"""Build a safe review queue from originals without guessing labels or readings."""

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in sorted(args.source.iterdir(), key=lambda item: item.name.lower()):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        with Image.open(path) as image:
            width, height = image.size
        if min(width, height) < 600:
            continue
        rows.append({
            "image_id": path.name,
            "source_path": path.as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "width": width,
            "height": height,
            "review_priority": "high" if min(width, height) >= 800 else "medium",
            "review_bucket": "unclassified",
            "meter_family": None,
            "display_bbox": None,
            "reading": None,
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "schema_version": "0.2.0",
        "purpose": "manual_review_queue_only",
        "images": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(rows), "high": sum(r["review_priority"] == "high" for r in rows),
                      "medium": sum(r["review_priority"] == "medium" for r in rows),
                      "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
