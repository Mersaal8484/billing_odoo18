import json
from pathlib import Path

from PIL import Image


SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "annotations" / "ocr" / "datameter-provisional.json"

# Coordinates are for the original high-resolution samples reviewed visually.
# They are proposals and remain needs_review until a human confirms them.
BOXES = {
    "image (1).jpg": ({"x": 355, "y": 323, "w": 430, "h": 115}, "00000590"),
    "image (2).jpg": ({"x": 100, "y": 145, "w": 405, "h": 105}, ""),
    "image (3).jpg": ({"x": 185, "y": 310, "w": 310, "h": 78}, ""),
    "image (4).jpg": ({"x": 228, "y": 425, "w": 300, "h": 82}, ""),
    "image (5).jpg": ({"x": 435, "y": 190, "w": 430, "h": 82}, ""),
    "image (7).jpg": ({"x": 120, "y": 295, "w": 445, "h": 98}, ""),
    "image (8).jpg": ({"x": 95, "y": 610, "w": 510, "h": 92}, ""),
}


def build():
    records = []
    for image_path in sorted(SOURCE.glob("*.jpg")):
        with Image.open(image_path) as image:
            width, height = image.size
        box, reading = BOXES.get(image_path.name, (None, ""))
        if min(width, height) <= 250 and not box:
            reason = "الصورة مصغرة؛ يلزم توفير الأصل عالي الدقة قبل التوسيم"
        elif not box:
            reason = "لم يتم اعتماد مربع الشاشة بعد"
        else:
            reason = "مربع أولي يحتاج مراجعة بشرية قبل التدريب"
        records.append({
            "image_id": image_path.name,
            "source_path": str(image_path),
            "image_size": {"width": width, "height": height},
            "display_bbox": box,
            "meter_bbox": None,
            "meter_family": "digital_lcd" if box else "unknown",
            "phase": "three_phase" if box else "unknown",
            "reading": reading,
            "meter_number": "",
            "label_state": "needs_review",
            "annotation_notes": reason,
        })
    payload = {
        "schema_version": "0.1.0",
        "source": "D:/datameter",
        "provisional": True,
        "images": records,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} records to {OUTPUT}")


if __name__ == "__main__":
    build()
