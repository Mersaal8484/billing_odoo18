"""Optional, review-only digit-CNN reader for roller registers.

The checkpoint is intentionally opt-in because the current bootstrap corpus is
single-reviewed and uses weak grid segmentation.  Its output can speed a human
reviewer up, but can never auto-approve a field reading.
"""

import os
from functools import lru_cache
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


@lru_cache(maxsize=2)
def _load(path: str):
    checkpoint = torch.load(path, map_location="cpu")
    model = DigitCNN()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def _grid(display: Image.Image, count: int):
    width, height = display.size
    left, right = round(width * 0.035), width - round(width * 0.035)
    top, bottom = round(height * 0.12), height - round(height * 0.12)
    inner_width = right - left
    return [display.crop((left + round(inner_width * index / count), top,
                         left + round(inner_width * (index + 1) / count), bottom)) for index in range(count)]


def recognize(image: Image.Image, expected_digits: int | None):
    path = os.getenv("METER_VISION_EXPERIMENTAL_DIGIT_CNN", "").strip()
    if not path or not Path(path).is_file():
        return None, 0.0, ["EXPERIMENTAL_DIGIT_CNN_NOT_CONFIGURED"]
    if not expected_digits:
        return None, 0.0, ["EXPERIMENTAL_DIGIT_CNN_NEEDS_REGISTER_WIDTH"]
    try:
        cells = _grid(ImageOps.grayscale(image), expected_digits)
        tensors = []
        for cell in cells:
            normalized = ImageOps.autocontrast(cell, cutoff=1).resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
            tensors.append(torch.from_numpy(np.asarray(normalized, dtype="float32") / 255.0).unsqueeze(0))
        with torch.no_grad():
            probabilities = _load(path)(torch.stack(tensors)).softmax(dim=1)
        reading = "".join(map(str, probabilities.argmax(dim=1).tolist()))
        # A high neural score is not real-world confidence at this stage.
        confidence = min(0.75, float(probabilities.max(dim=1).values.mean()))
        return reading, round(confidence, 4), ["EXPERIMENTAL_DIGIT_CNN", "EXPERIMENTAL_WEIGHT_REVIEW_REQUIRED"]
    except (OSError, RuntimeError, KeyError, ValueError):
        return None, 0.0, ["EXPERIMENTAL_DIGIT_CNN_FAILED"]
