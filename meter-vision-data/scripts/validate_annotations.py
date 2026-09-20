"""Validate local OCR annotations before they are admitted to training."""

import argparse
import json
from pathlib import Path

from PIL import Image


def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("images"), list):
        return payload["images"]
    return [payload]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    errors, warnings, valid = [], [], 0
    seen = set()
    for index, item in enumerate(records(payload), 1):
        ident = item.get("image_id", f"row-{index}")
        source = item.get("source_path") or ident
        path = Path(source)
        if not path.is_absolute():
            path = args.root / path
        if not path.exists():
            errors.append(f"{ident}: source image not found: {path}")
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except (OSError, ValueError) as error:
            errors.append(f"{ident}: invalid image: {error}")
            continue
        if min(width, height) < 600:
            warnings.append(f"{ident}: thumbnail/low-resolution source {width}x{height}")
        bbox = item.get("display_bbox") or {}
        if not all(key in bbox for key in ("x", "y", "w", "h")):
            errors.append(f"{ident}: display_bbox is incomplete")
        elif bbox["x"] < 0 or bbox["y"] < 0 or bbox["w"] <= 0 or bbox["h"] <= 0 or bbox["x"] + bbox["w"] > width or bbox["y"] + bbox["h"] > height:
            errors.append(f"{ident}: display_bbox is outside {width}x{height}")
        reading = str(item.get("reading", "")).strip()
        if item.get("label_state") in {"double_review", "gold"} and not reading:
            errors.append(f"{ident}: reviewed record has no reading")
        group = item.get("group_id") or item.get("meter_number")
        if item.get("label_state") in {"double_review", "gold"} and not group:
            warnings.append(f"{ident}: no group_id; split may leak the same meter")
        if item.get("training_eligible") and item.get("label_state") not in {"double_review", "gold"}:
            errors.append(f"{ident}: training_eligible requires double_review or gold")
        key = item.get("sha256") or str(path).lower()
        if key in seen:
            errors.append(f"{ident}: duplicate source")
        seen.add(key)
        valid += 1
    print(json.dumps({"records": valid, "errors": errors, "warnings": warnings,
                      "ready": not errors}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
