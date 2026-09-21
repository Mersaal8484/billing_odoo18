"""Export reviewed display boxes as an EXIF-free YOLO detection dataset."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


APPROVED_STATES = {"single_review", "double_review", "gold"}


def split_for(group: str) -> str:
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "test" if bucket < 15 else "val" if bucket < 25 else "train"


def main():
    parser = argparse.ArgumentParser(description="Export reviewed display boxes as YOLO labels")
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = []
    for item in payload.get("images", []):
        if item.get("label_state") not in APPROVED_STATES or not item.get("display_bbox"):
            continue
        source = args.root / Path(item.get("source_path", ""))
        if not source.exists():
            continue
        group = item.get("group_id") or item.get("meter_number") or item["image_id"]
        split = split_for(group)
        key = hashlib.sha256(item["image_id"].encode("utf-8")).hexdigest()[:20]
        image_path = args.output / "images" / split / f"{key}.jpg"
        label_path = args.output / "labels" / split / f"{key}.txt"
        try:
            with Image.open(source) as raw:
                image = ImageOps.exif_transpose(raw).convert("RGB")
                width, height = image.size
                box = item["display_bbox"]
                left, top = max(0, box["x"]), max(0, box["y"])
                right, bottom = min(width, box["x"] + box["w"]), min(height, box["y"] + box["h"])
                if right <= left or bottom <= top:
                    continue
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(image_path, format="JPEG", quality=95, optimize=True)
        except (OSError, ValueError):
            continue
        center_x = (left + right) / 2 / width
        center_y = (top + bottom) / 2 / height
        normalized_w = (right - left) / width
        normalized_h = (bottom - top) / height
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text(f"0 {center_x:.8f} {center_y:.8f} {normalized_w:.8f} {normalized_h:.8f}\n", encoding="utf-8")
        rows.append({
            "image_id": item["image_id"], "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "meter_family": item.get("meter_family", "unknown"), "label_state": item["label_state"],
            "split": split, "source": "local-field-image", "label_quality": item["label_state"],
        })
    args.output.mkdir(parents=True, exist_ok=True)
    # Ultralytics resolves ``path: .`` against the caller's working directory,
    # not against this YAML file.  Persist the generated dataset's own path so
    # training is reproducible from any working directory.
    config = (
        f"path: {args.output.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\nnames:\n  0: display\n"
    )
    (args.output / "dataset.yaml").write_text(config, encoding="utf-8")
    manifest = {
        "dataset_id": "meter-display-detector", "version": "v0.1.0",
        "created_at": datetime.now(timezone.utc).isoformat(), "images": rows,
        "splits": {"strategy": "grouped_by_meter_or_route", "group_key": "meter_id_hash"},
        "privacy": {"pii_removed": False, "exif_removed": True, "consent_recorded": False},
        "training_warning": "Single-review labels are bootstrap-only; require double review before production promotion.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = Counter(row["split"] for row in rows)
    print(json.dumps({"records": len(rows), "splits": dict(counts), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
