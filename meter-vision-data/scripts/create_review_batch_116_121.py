"""Review-only boxes for the 116-121 field-image batch."""

import json
from pathlib import Path

from PIL import Image


SOURCE = Path(r"D:\datameter")
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "datameter-review-batch-116-121.json"
)
ROWS = {
    "account.analytic.meter(116).jpg": (
        {"x": 172, "y": 425, "w": 460, "h": 75},
        "mechanical_roller",
        "003469",
        0.86,
    ),
    "account.analytic.meter(117).jpg": (
        {"x": 220, "y": 345, "w": 355, "h": 75},
        "mechanical_roller",
        None,
        0.30,
    ),
    "account.analytic.meter(118).jpg": (
        {"x": 165, "y": 382, "w": 430, "h": 82},
        "mechanical_roller",
        "255123",
        0.70,
    ),
    "account.analytic.meter(119).jpg": (
        {"x": 300, "y": 398, "w": 185, "h": 48},
        "mechanical_roller",
        "005229",
        0.62,
    ),
    "account.analytic.meter(120).jpg": (
        {"x": 388, "y": 398, "w": 355, "h": 85},
        "mechanical_roller",
        None,
        0.32,
    ),
    "account.analytic.meter(121).jpg": (
        {"x": 165, "y": 305, "w": 420, "h": 90},
        "mechanical_roller",
        "002195",
        0.91,
    ),
}


def main():
    rows = []
    for name, (bbox, family, reading, confidence) in ROWS.items():
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        rows.append(
            {
                "image_id": name,
                "source_path": path.as_posix(),
                "image_size": {"width": width, "height": height},
                "display_bbox": bbox,
                "meter_bbox": None,
                "meter_family": family,
                "reading": reading,
                "reading_confidence": confidence,
                "meter_number": None,
                "group_id": None,
                "label_state": "needs_review",
                "training_eligible": False,
                "annotation_notes": (
                    "مربع مراجعة أولي؛ القراءات الواضحة أولية وتحتاج مراجعة بشرية ثانية."
                ),
            }
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"schema_version": "0.2.0", "images": rows}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"records": len(rows), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
