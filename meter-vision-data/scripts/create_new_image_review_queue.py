"""Create a review queue for new, high-resolution field meter images.

This inventory deliberately does not guess a reading or a screen rectangle.
Those values are training truth only after a reviewer confirms them in the
annotation tool.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def normalized(path: str) -> str:
    return str(Path(path)).replace("\\", "/").lower()


def load_known(paths: list[Path]) -> set[str]:
    known = set()
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("images", []) if isinstance(payload, dict) else []
        for item in records:
            for value in (item.get("source_path"), item.get("image_id")):
                if value:
                    known.add(normalized(value))
    return known


def main():
    parser = argparse.ArgumentParser(description="Create a safe queue of unreviewed original meter photos")
    parser.add_argument("source", type=Path)
    parser.add_argument("--known", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--minimum-side", type=int, default=600)
    args = parser.parse_args()
    known = load_known(args.known)
    seen_hashes = set()
    records = []
    for path in sorted(args.source.iterdir(), key=lambda item: item.name.lower()):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} or not path.is_file():
            continue
        if normalized(path) in known or normalized(path.name) in known:
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
            if min(width, height) < args.minimum_side:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            continue
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        records.append({
            "image_id": path.name,
            "source_path": path.as_posix(),
            "image_size": {"width": width, "height": height},
            "display_bbox": None,
            "display_quad": None,
            "meter_bbox": None,
            "meter_family": "unknown",
            "reading": "",
            "meter_number": "",
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
            "annotation_notes": "صورة جديدة عالية الدقة؛ حدد الشاشة واقرأ العداد قبل اعتمادها للتدريب.",
        })
        if len(records) >= args.limit:
            break
    payload = {
        "schema_version": "0.2.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source),
        "images": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
