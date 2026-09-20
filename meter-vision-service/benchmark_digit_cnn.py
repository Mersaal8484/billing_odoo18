"""Evaluate the experimental roller digit-CNN against a held-out display set."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn


IMAGE_SIZE = (48, 72)


class DigitCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 24, 3, padding=1), nn.BatchNorm2d(24), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(24, 48, 3, padding=1), nn.BatchNorm2d(48), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(48, 96, 3, padding=1), nn.BatchNorm2d(96), nn.ReLU(), nn.AdaptiveAvgPool2d((3, 2)),
        )
        self.classifier = nn.Sequential(nn.Flatten(), nn.Dropout(0.2), nn.Linear(96 * 3 * 2, 10))

    def forward(self, images):
        return self.classifier(self.features(images))


def crop_grid(display: Image.Image, count: int, margin_x=0.035, margin_y=0.12):
    width, height = display.size
    left, right = round(width * margin_x), width - round(width * margin_x)
    top, bottom = round(height * margin_y), height - round(height * margin_y)
    inner_width = right - left
    return [display.crop((left + round(inner_width * index / count), top,
                         left + round(inner_width * (index + 1) / count), bottom)) for index in range(count)]


def tensor(cell: Image.Image):
    image = ImageOps.autocontrast(ImageOps.grayscale(cell), cutoff=1).resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
    return torch.from_numpy(np.asarray(image, dtype="float32") / 255.0).unsqueeze(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "val", "test"), default="test")
    parser.add_argument("--meter-family", default="mechanical_roller")
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    model = DigitCNN()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows, digit_total, digit_correct = [], 0, 0
    for item in payload.get("images", []):
        if item.get("meter_family") != args.meter_family or not item.get("display_bbox"):
            continue
        group = item.get("group_id") or item.get("meter_number") or item["image_id"]
        bucket = int(__import__("hashlib").sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 100
        split = "test" if bucket < 15 else "val" if bucket < 25 else "train"
        if split != args.split:
            continue
        expected = item.get("reading", "").replace(".", "")
        source = args.root / Path(item["source_path"])
        if not expected or not source.exists():
            continue
        box = item["display_bbox"]
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("L")
            display = image.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
        cells = crop_grid(display, len(expected))
        with torch.no_grad():
            logits = model(torch.stack([tensor(cell) for cell in cells]))
            probabilities = logits.softmax(dim=1)
            digits = probabilities.argmax(dim=1).tolist()
            confidence = float(probabilities.max(dim=1).values.mean())
        predicted = "".join(map(str, digits))
        digit_total += len(expected)
        digit_correct += sum(left == right for left, right in zip(expected, predicted))
        rows.append({"image_id": item["image_id"], "expected": expected, "predicted": predicted,
                     "confidence": round(confidence, 4), "exact": predicted == expected})
    report = {"records": len(rows), "exact": sum(row["exact"] for row in rows),
              "exact_accuracy": sum(row["exact"] for row in rows) / max(1, len(rows)),
              "digit_accuracy": digit_correct / max(1, digit_total), "label_quality": "single_review_weak_grid",
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("records", "exact", "exact_accuracy", "digit_accuracy")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
