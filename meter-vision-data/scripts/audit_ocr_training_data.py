"""Audit OCR annotations before any custom model training starts.

This intentionally fails closed: provisional or single-review labels are useful
for queue work, but must never silently become training truth.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image


APPROVED_STATES = {"single_review", "double_review", "gold"}


def load_records(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("images"), list):
            records.extend(payload["images"])
        elif isinstance(payload, dict) and payload.get("image_id"):
            records.append(payload)
    return records


def main():
    parser = argparse.ArgumentParser(description="Audit approved OCR training labels")
    parser.add_argument("annotations", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    records = load_records(args.annotations)
    states = Counter(item.get("label_state", "missing") for item in records)
    eligible = []
    problems = []
    for item in records:
        if item.get("label_state") not in APPROVED_STATES or not item.get("training_eligible"):
            continue
        source = Path(item.get("source_path", item.get("image_id", "")))
        if not source.is_absolute():
            source = args.root / source
        if not source.exists():
            problems.append({"image_id": item.get("image_id"), "error": "SOURCE_NOT_FOUND"})
            continue
        if not item.get("reading"):
            problems.append({"image_id": item.get("image_id"), "error": "READING_MISSING"})
            continue
        with Image.open(source) as image:
            if min(image.size) < 600:
                problems.append({"image_id": item.get("image_id"), "error": "LOW_SOURCE_RESOLUTION"})
                continue
        eligible.append(item)

    families = Counter(item.get("meter_family", "unknown") for item in eligible)
    result = {
        "records": len(records),
        "states": dict(states),
        "eligible": len(eligible),
        "families": dict(families),
        "problems": problems,
        "ready_for_training": bool(eligible) and not problems,
        "minimum_next_step": "اعتماد عينات بمراجعين اثنين وتسجيل القراءة الصحيحة قبل التدريب.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ready_for_training"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
