"""Review-only boxes for the next clear roller-meter images."""

import json
from pathlib import Path
from PIL import Image

SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "datameter-roller-batch-104-109.json"
BOXES = {
    "account.analytic.meter(104).jpg": {"x": 105, "y": 390, "w": 430, "h": 105},
    "account.analytic.meter(105).jpg": {"x": 285, "y": 365, "w": 300, "h": 100},
    "account.analytic.meter(106).jpg": {"x": 150, "y": 370, "w": 420, "h": 110},
    "account.analytic.meter(107).jpg": {"x": 245, "y": 420, "w": 360, "h": 110},
    "account.analytic.meter(108).jpg": {"x": 220, "y": 370, "w": 300, "h": 100},
    "account.analytic.meter(109).jpg": {"x": 190, "y": 350, "w": 390, "h": 130},
}


def main():
    rows = []
    for name, bbox in BOXES.items():
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        rows.append({"image_id": name, "source_path": path.as_posix(),
                     "image_size": {"width": width, "height": height},
                     "display_bbox": bbox, "meter_bbox": None,
                     "meter_family": "mechanical_roller", "reading": None,
                     "meter_number": None, "group_id": None,
                     "label_state": "needs_review", "training_eligible": False,
                     "annotation_notes": "مربع مراجعة أولي؛ القراءة متروكة للمراجعة البشرية."})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "0.2.0", "images": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(rows), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
