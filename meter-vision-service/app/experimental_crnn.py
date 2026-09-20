"""Optional loader for the local experimental CRNN checkpoint."""

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn


VOCAB = "0123456789."
BLANK = len(VOCAB)


class CRNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d((2, 1)),
        )
        self.rnn = nn.LSTM(64 * 6, 64, bidirectional=True, num_layers=1)
        self.classifier = nn.Linear(128, len(VOCAB) + 1)

    def forward(self, images):
        features = self.features(images)
        batch, channels, height, width = features.shape
        sequence = features.permute(3, 0, 1, 2).contiguous().view(width, batch, channels * height)
        return self.classifier(self.rnn(sequence)[0])


@lru_cache(maxsize=2)
def _load(path: str):
    model = CRNN()
    checkpoint = torch.load(path, map_location="cpu")
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def recognize(image: Image.Image):
    path = os.getenv("METER_VISION_EXPERIMENTAL_CRNN", "").strip()
    if not path or not Path(path).exists():
        return None, 0.0, ["EXPERIMENTAL_CRNN_NOT_CONFIGURED"]
    try:
        with ImageOps.grayscale(image) as gray:
            gray = gray.resize((192, 48), Image.Resampling.LANCZOS)
            tensor = torch.from_numpy(np.asarray(gray, dtype="float32") / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = _load(path)(tensor)
        values = logits.argmax(2)[:, 0].tolist()
        result, previous = [], None
        for value in values:
            if value != BLANK and value != previous:
                result.append(VOCAB[value])
            previous = value
        reading = "".join(result)
        if not reading:
            return None, 0.0, ["EXPERIMENTAL_CRNN_NO_READING"]
        return reading, 0.25, ["EXPERIMENTAL_CRNN_WEIGHT", "EXPERIMENTAL_CRNN_REVIEW_REQUIRED"]
    except (OSError, RuntimeError, KeyError, ValueError):
        return None, 0.0, ["EXPERIMENTAL_CRNN_FAILED"]
