"""Apply the visual meter-family review for the first single-review batch."""

import argparse
import json
from collections import Counter
from pathlib import Path


DIGITAL_LCD = {
    "account.analytic.meter(13).jpg", "account.analytic.meter(14).jpg", "account.analytic.meter(18).jpg",
    "image (4).jpg", "image (5).jpg", "image (49).jpg", "image (53).jpg", "image (54).jpg",
    "image (7).jpg", "image (8).jpg", "image (78).jpg",
}
MECHANICAL_ROUND = {
    "account.analytic.meter(132).jpg", "image (46).jpg", "image (51).jpg", "image (67).jpg",
    "image (69).jpg", "image (71).jpg", "image (72).jpg", "image (73).jpg", "image (74).jpg",
    "image (75).jpg", "image (76).jpg", "image (77).jpg",
}


def family_for(name: str) -> str:
    if name in DIGITAL_LCD:
        return "digital_lcd"
    if name in MECHANICAL_ROUND:
        return "mechanical_round"
    return "mechanical_roller"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    for item in payload.get("images", []):
        item["meter_family"] = family_for(Path(item["image_id"]).name)
        item["family_review"] = "visual_batch_review_2026-09-21"
    payload["meter_family_policy"] = "visual classification; revise when a second reviewer is available"
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(Counter(item["meter_family"] for item in payload["images"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
