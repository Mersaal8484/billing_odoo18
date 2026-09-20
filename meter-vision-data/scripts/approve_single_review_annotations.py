"""Create a clearly marked single-review OCR annotation export."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    records = payload.get("images", [])
    approved = 0
    for item in records:
        reviews = [review for review in item.get("reviews", []) if review]
        if len(reviews) != 1 or not reviews[0].get("reading"):
            continue
        review = reviews[0]
        item["reading"] = review["reading"]
        item["display_bbox"] = review.get("display_bbox") or item.get("display_bbox")
        item["label_state"] = "single_review"
        item["training_eligible"] = True
        item["annotation_notes"] = "اعتماد مرحلي بمراجع واحد؛ يحتاج مراجعة ثانية قبل اعتماد gold."
        approved += 1
    payload["review_policy"] = "single_reviewer_temporary"
    payload["approved_count"] = approved
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "approved": approved, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
