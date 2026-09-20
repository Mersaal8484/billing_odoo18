"""Annotate the clearest new roller-meter images for second review."""

import json
from pathlib import Path
from PIL import Image


SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "datameter-clear-roller-batch-2026-09-21.json"

ROWS = {
    "account.analytic.meter(98).jpg": ({"x": 205, "y": 290, "w": 375, "h": 100}, "019221"),
    "account.analytic.meter(99).jpg": ({"x": 225, "y": 285, "w": 365, "h": 105}, "015278"),
    "account.analytic.meter(100).jpg": ({"x": 160, "y": 370, "w": 395, "h": 105}, "007121"),
    "account.analytic.meter(101).jpg": ({"x": 220, "y": 335, "w": 385, "h": 105}, "024491"),
    "account.analytic.meter(102).jpg": ({"x": 180, "y": 390, "w": 395, "h": 105}, "030086"),
    "account.analytic.meter(103).jpg": ({"x": 185, "y": 365, "w": 395, "h": 105}, "019595"),
}


def main():
    records = []
    for name, (bbox, reading) in ROWS.items():
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        records.append({
            "image_id": name,
            "source_path": path.as_posix(),
            "image_size": {"width": width, "height": height},
            "display_bbox": bbox,
            "meter_bbox": None,
            "meter_family": "mechanical_roller",
            "reading": reading,
            "meter_number": None,
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
            "annotation_notes": "قراءة أولية ظاهرة بصرياً؛ تحتاج مراجعة ثانية قبل اعتمادها للتدريب.",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "0.2.0", "images": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
