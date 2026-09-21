"""Seed a human-review queue with automatic display and OCR proposals.

The output is deliberately *not* training data: proposed boxes and readings are
kept separate from the human ``reading`` field.  A reviewer must verify both
before changing ``label_state`` to ``single_review`` or ``double_review``.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = ROOT / "meter-vision-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.display_detector import auto_detect_display  # noqa: E402
from app.inference import analyze  # noqa: E402
from app.schemas import DisplayBBox, InferenceRequest  # noqa: E402


FAMILY_BY_FOLDER = {
    "lcd_single_row": "digital_lcd",
    "lcd_dual_row": "digital_lcd",
    "seven_segment": "digital_lcd",
    "mechanical_roller": "mechanical_roller",
    "mechanical_round": "mechanical_round",
    "unknown_needs_review": "unknown",
}


def build_queue(manifest_path: Path, output_path: Path) -> dict:
    """Create review records from a sanitized ingestion manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = []
    for item in manifest["images"]:
        image_path = ROOT / "meter-vision-data" / item["relative_path"]
        subtype = item["meter_family"]
        family = FAMILY_BY_FOLDER.get(subtype, "unknown")
        with Image.open(image_path) as image:
            width, height = image.size
            candidate_bbox = auto_detect_display(image)

        suggestion = None
        confidence = 0.0
        flags = []
        if candidate_bbox:
            result = analyze(InferenceRequest(
                request_id=item["image_id"],
                image_base64=base64.b64encode(image_path.read_bytes()).decode("ascii"),
                meter_type_hint=family if family != "unknown" else None,
                display_bbox=DisplayBBox(**candidate_bbox),
            ))
            suggestion = result.reading.value
            confidence = result.reading.confidence
            flags = result.flags

        records.append({
            "image_id": item["file_name"],
            "source_path": item["relative_path"],
            "image_size": {"width": width, "height": height},
            "display_bbox": candidate_bbox,
            "meter_bbox": None,
            "meter_family": family,
            "meter_subtype": subtype,
            "reading": "",
            "meter_number": "",
            "label_state": "needs_review",
            "training_eligible": False,
            "ocr_suggestion": suggestion,
            "ocr_confidence": confidence,
            "ocr_flags": flags,
            "annotation_notes": (
                "مربع الشاشة وقراءة OCR اقتراحان آليان فقط؛ راجعهما "
                "وعدلهما قبل أي اعتماد للتدريب."
            ),
        })

    payload = {
        "schema_version": "0.3.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": manifest_path.name,
        "provisional": True,
        "images": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "meter-vision-data" / "manifests" /
        "datameter-2026-09-22-provisional-classification.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "meter-vision-data" / "annotations" / "ocr" /
        "datameter-2026-09-22-seeded-review.json",
    )
    args = parser.parse_args()
    payload = build_queue(args.manifest, args.output)
    detected = sum(1 for row in payload["images"] if row["display_bbox"])
    suggested = sum(1 for row in payload["images"] if row["ocr_suggestion"])
    print(json.dumps({
        "records": len(payload["images"]),
        "display_candidates": detected,
        "ocr_suggestions": suggested,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
