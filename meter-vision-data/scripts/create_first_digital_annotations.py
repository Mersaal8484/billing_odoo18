"""Create a small, review-only first batch for clear Holley LCD images."""

import json
from pathlib import Path
from PIL import Image


SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "datameter-first-digital-annotations.json"

# Coordinates are deliberately review-only.  No reading is invented here.
BOXES = {
    "image (1).jpg": (345, 235, 425, 115),
    "image (2).jpg": (115, 105, 410, 155),
    "image (3).jpg": (180, 300, 330, 100),
    "image (4).jpg": (225, 410, 330, 105),
    "image (7).jpg": (115, 220, 610, 190),
    "image (8).jpg": (85, 365, 575, 180),
    "image (49).jpg": (250, 300, 780, 210),
    "image (53).jpg": (185, 285, 800, 260),
    "image (78).jpg": (385, 245, 570, 170),
}


def main():
    records = []
    for name, (x, y, w, h) in BOXES.items():
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        records.append({
            "image_id": name,
            "source_path": path.as_posix(),
            "image_size": {"width": width, "height": height},
            "display_bbox": {"x": x, "y": y, "w": w, "h": h},
            "meter_bbox": None,
            "meter_family": "digital_lcd",
            "reading": None,
            "meter_number": None,
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
            "annotation_notes": "مربع أولي للشاشة فقط؛ يجب مراجعة الحدود والقراءة يدوياً قبل التدريب.",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "0.2.0", "images": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
