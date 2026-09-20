"""Create review-only display boxes for the mechanical-meter review batch."""

import json
from pathlib import Path
from PIL import Image


SOURCE = Path(r"D:\datameter")
OUTPUT = Path(__file__).resolve().parents[1] / "reports" / "datameter-mechanical-review-annotations.json"

ROLLER = {
    "image (31).jpg", "image (32).jpg", "image (33).jpg", "image (35).jpg",
    "image (36).jpg", "image (37).jpg", "image (38).jpg", "image (39).jpg",
    "image (40).jpg", "image (41).jpg", "image (42).jpg", "image (43).jpg",
    "image (44).jpg", "image (45).jpg", "image (47).jpg", "image (50).jpg",
    "image (52).jpg", "image (55).jpg", "image (56).jpg", "image (57).jpg",
    "image (58).jpg", "image (59).jpg", "image (60).jpg", "image (61).jpg",
    "image (62).jpg", "image (63).jpg", "image (65).jpg", "image (66).jpg",
    "image (68).jpg", "image (70).jpg", "image (80).jpg", "image (81).jpg",
    "image (82).jpg", "image (83).jpg", "image (84).jpg", "image (85).jpg",
    "image (86).jpg", "image (87).jpg", "image (88).jpg", "image (89).jpg",
}
ROUND = {"image (46).jpg", "image (69).jpg", "image (71).jpg", "image (72).jpg",
         "image (73).jpg", "image (74).jpg", "image (75).jpg", "image (76).jpg",
         "image (77).jpg"}
OTHER = {"image (51).jpg", "image (54).jpg", "image (64).jpg", "image (67).jpg",
         "image (79).jpg"}
MANUAL_BOXES = {
    "image (31).jpg": {"x": 350, "y": 375, "w": 480, "h": 140},
    "image (50).jpg": {"x": 420, "y": 400, "w": 550, "h": 130},
    "image (55).jpg": {"x": 230, "y": 400, "w": 530, "h": 145},
    "image (65).jpg": {"x": 365, "y": 320, "w": 420, "h": 100},
    "image (85).jpg": {"x": 490, "y": 195, "w": 360, "h": 120},
}


def box_for(width, height, family):
    if family == "mechanical_round":
        return {"x": round(width * 0.25), "y": round(height * 0.17),
                "w": round(width * 0.50), "h": round(height * 0.23)}
    if width >= height:
        return {"x": round(width * 0.18), "y": round(height * 0.35),
                "w": round(width * 0.65), "h": round(height * 0.25)}
    return {"x": round(width * 0.12), "y": round(height * 0.14),
            "w": round(width * 0.76), "h": round(height * 0.30)}


def main():
    records = []
    for name in sorted(ROLLER | ROUND | OTHER):
        path = SOURCE / name
        if not path.exists():
            continue
        with Image.open(path) as image:
            width, height = image.size
        if min(width, height) < 600:
            continue
        family = "mechanical_roller" if name in ROLLER else "mechanical_round" if name in ROUND else "unknown"
        records.append({
            "image_id": name,
            "source_path": path.as_posix(),
            "image_size": {"width": width, "height": height},
            "display_bbox": MANUAL_BOXES.get(name, box_for(width, height, family)),
            "meter_bbox": None,
            "meter_family": family,
            "reading": None,
            "meter_number": None,
            "group_id": None,
            "label_state": "needs_review",
            "training_eligible": False,
            "annotation_notes": "مربع يدوي/أولي للقراءة الميكانيكية؛ يجب مراجعة الحدود والقراءة يدوياً قبل التدريب.",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"schema_version": "0.2.0", "images": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
