"""Review-only boxes for the next mixed meter batch."""

import json
from pathlib import Path
from PIL import Image

SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "datameter-review-batch-110-115.json"
ROWS = {
    "account.analytic.meter(110).jpg": ({"x": 190, "y": 450, "w": 380, "h": 105}, "mechanical_roller", "018098", 0.88),
    "account.analytic.meter(111).jpg": ({"x": 195, "y": 325, "w": 360, "h": 105}, "mechanical_roller", "13142", 0.92),
    "account.analytic.meter(112).jpg": ({"x": 150, "y": 450, "w": 450, "h": 160}, "mechanical_round", None, 0.25),
    "account.analytic.meter(113).jpg": ({"x": 205, "y": 385, "w": 410, "h": 125}, "mechanical_round", "000548", 0.72),
    "account.analytic.meter(114).jpg": ({"x": 220, "y": 450, "w": 420, "h": 150}, "mechanical_roller", "003642", 0.65),
    "account.analytic.meter(115).jpg": ({"x": 245, "y": 370, "w": 450, "h": 155}, "digital_lcd", "00014303", 0.78),
}


def main():
    rows = []
    for name, (bbox, family, reading, confidence) in ROWS.items():
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        rows.append({"image_id": name, "source_path": path.as_posix(),
                     "image_size": {"width": width, "height": height},
                     "display_bbox": bbox, "meter_bbox": None,
                     "meter_family": family, "reading": reading,
                     "reading_confidence": confidence,
                     "meter_number": None, "group_id": None,
                     "label_state": "needs_review", "training_eligible": False,
                     "annotation_notes": "مربع مراجعة أولي؛ القراءة متروكة للمراجعة البشرية."})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "0.2.0", "images": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(rows), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
