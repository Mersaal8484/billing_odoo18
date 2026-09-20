"""Train a compact digit classifier on weakly segmented roller-display cells.

This checkpoint is an experimental bootstrap aid.  It is intentionally not
loaded by production inference: promotion requires a double-reviewed dataset
and a documented held-out accuracy gate.
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from torch import nn
from torch.utils.data import DataLoader, Dataset


IMAGE_SIZE = (48, 72)


class DigitDataset(Dataset):
    def __init__(self, rows, root, augment=False, repeats=1):
        self.rows = rows
        self.root = root
        self.augment = augment
        self.repeats = repeats

    def __len__(self):
        return len(self.rows) * self.repeats

    def __getitem__(self, index):
        row = self.rows[index % len(self.rows)]
        with Image.open(self.root / Path(row["crop"])) as source:
            image = ImageOps.grayscale(source)
            if self.augment:
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.65, 1.55))
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.72, 1.28))
                if random.random() < 0.65:
                    image = image.rotate(random.uniform(-5.0, 5.0), Image.Resampling.BILINEAR, fillcolor=255)
                if random.random() < 0.35:
                    image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.0, 0.8)))
            image = ImageOps.autocontrast(image, cutoff=1).resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
            values = np.asarray(image, dtype="float32") / 255.0
        return torch.from_numpy(values).unsqueeze(0), int(row["digit"])


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


def evaluate(model, loader, device):
    model.eval()
    total = correct = 0
    with torch.no_grad():
        for images, targets in loader:
            predictions = model(images.to(device)).argmax(dim=1).cpu()
            correct += int((predictions == targets).sum())
            total += len(targets)
    return {"correct": correct, "total": total, "accuracy": correct / max(1, total)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--augment-repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    splits = {name: [row for row in rows if row["split"] == name] for name in ("train", "val", "test")}
    if not all(splits.values()):
        raise SystemExit("digit manifest needs non-empty train, val and test splits")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loaders = {
        "train": DataLoader(DigitDataset(splits["train"], args.manifest.parent, augment=True, repeats=args.augment_repeats), args.batch_size, shuffle=True),
        "val": DataLoader(DigitDataset(splits["val"], args.manifest.parent), args.batch_size),
        "test": DataLoader(DigitDataset(splits["test"], args.manifest.parent), args.batch_size),
    }
    model = DigitCNN().to(device)
    weights = Counter(int(row["digit"]) for row in splits["train"])
    class_weights = torch.tensor([1.0 / max(1, weights[digit]) for digit in range(10)], device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)
    best = {"val_accuracy": -1.0}
    for epoch in range(1, args.epochs + 1):
        model.train()
        for images, targets in loaders["train"]:
            loss = loss_fn(model(images.to(device)), targets.to(device))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        val = evaluate(model, loaders["val"], device)
        if val["accuracy"] >= best["val_accuracy"]:
            best = {"epoch": epoch, "val_accuracy": val["accuracy"], "val": val}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"state_dict": model.state_dict(), "image_size": IMAGE_SIZE, "metrics": best,
                        "warning": "weak_grid_from_single_review; not production approved"}, args.output)
        if epoch == 1 or epoch % 10 == 0 or epoch == args.epochs:
            print(json.dumps({"epoch": epoch, "val": val}, ensure_ascii=False))
    checkpoint = torch.load(args.output, map_location=device)
    model.load_state_dict(checkpoint["state_dict"])
    checkpoint["metrics"]["test"] = evaluate(model, loaders["test"], device)
    torch.save(checkpoint, args.output)
    print(json.dumps({"device": str(device), "metrics": checkpoint["metrics"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
