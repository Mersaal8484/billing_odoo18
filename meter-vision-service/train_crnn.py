"""Train a small character-level CRNN/CTC OCR baseline on approved crops.

This is a reproducible bootstrap trainer, not a production checkpoint. It is
deliberately separated from inference until the held-out exact-match gate is
met and the labels have a second review.
"""

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from torch import nn
from torch.utils.data import DataLoader, Dataset


VOCAB = "0123456789."
BLANK = len(VOCAB)
IMAGE_SIZE = (192, 48)


class OCRDataset(Dataset):
    def __init__(self, rows, root, augment=False, repeats=1):
        self.rows = rows
        self.root = root
        self.augment = augment
        self.repeats = repeats

    def __len__(self):
        return len(self.rows) * self.repeats

    def __getitem__(self, index):
        row = self.rows[index % len(self.rows)]
        path = self.root / Path(row["normalized_crop"])
        with Image.open(path) as image:
            image = ImageOps.grayscale(image)
            if self.augment:
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.78, 1.22))
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.75, 1.35))
                if random.random() < 0.45:
                    image = image.rotate(random.uniform(-3.0, 3.0), resample=Image.Resampling.BILINEAR, expand=False, fillcolor=255)
                if random.random() < 0.25:
                    image = image.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.8)))
                image = ImageOps.autocontrast(image, cutoff=random.choice((0, 1, 2)))
            image = image.resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
            tensor = torch.from_numpy(np.asarray(image, dtype="float32") / 255.0)
        target = torch.tensor([VOCAB.index(char) for char in row["reading"]], dtype=torch.long)
        return tensor.unsqueeze(0), target, row["reading"]


def collate(batch):
    images, targets, texts = zip(*batch)
    return torch.stack(images), torch.cat(targets), torch.tensor([len(target) for target in targets]), texts


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
        # CTC otherwise starts by predicting only the blank symbol on this
        # small dataset and struggles to recover.
        with torch.no_grad():
            self.classifier.bias[BLANK] = -2.0

    def forward(self, images):
        features = self.features(images)
        batch, channels, height, width = features.shape
        sequence = features.permute(3, 0, 1, 2).contiguous().view(width, batch, channels * height)
        return self.classifier(self.rnn(sequence)[0])


def decode(logits):
    values = logits.argmax(2).transpose(0, 1).tolist()
    texts = []
    for row in values:
        result, previous = [], None
        for value in row:
            if value != BLANK and value != previous:
                result.append(VOCAB[value])
            previous = value
        texts.append("".join(result))
    return texts


def evaluate(model, loader, device):
    model.eval()
    total = exact = char_total = char_correct = 0
    with torch.no_grad():
        for images, _targets, _lengths, texts in loader:
            predictions = decode(model(images.to(device)))
            total += len(texts)
            exact += sum(prediction == target for prediction, target in zip(predictions, texts))
            char_total += sum(max(len(prediction), len(target)) for prediction, target in zip(predictions, texts))
            char_correct += sum(sum(a == b for a, b in zip(prediction, target)) for prediction, target in zip(predictions, texts))
    return {"exact": exact, "total": total, "exact_accuracy": exact / max(1, total),
            "char_accuracy": char_correct / max(1, char_total)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--augment-repeats", type=int, default=1)
    parser.add_argument("--reading-format", help="Train one register layout, e.g. integer_6 or decimal_6")
    parser.add_argument("--meter-family", help="Restrict a checkpoint to one reviewed meter family")
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    formats = sorted({row.get("reading_format", "unknown") for row in rows})
    if not args.reading_format and not args.meter_family:
        raise SystemExit(f"choose --reading-format or --meter-family; formats: {', '.join(formats)}")
    if args.reading_format:
        rows = [row for row in rows if row.get("reading_format") == args.reading_format]
    if args.meter_family:
        rows = [row for row in rows if row.get("meter_family") == args.meter_family]
    root = args.manifest.parent
    splits = {name: [row for row in rows if row["split"] == name] for name in ("train", "val", "test")}
    if not all(splits.values()):
        raise SystemExit("manifest must contain non-empty train, val, and test splits")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CRNN().to(device)
    loaders = {
        "train": DataLoader(OCRDataset(splits["train"], root, augment=True, repeats=args.augment_repeats), batch_size=args.batch_size, shuffle=True, collate_fn=collate),
        "val": DataLoader(OCRDataset(splits["val"], root), batch_size=args.batch_size, shuffle=False, collate_fn=collate),
        "test": DataLoader(OCRDataset(splits["test"], root), batch_size=args.batch_size, shuffle=False, collate_fn=collate),
    }
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CTCLoss(blank=BLANK, zero_infinity=True)
    best = {"val": 0.0}
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for images, targets, target_lengths, _texts in loaders["train"]:
            logits = model(images.to(device))
            input_lengths = torch.full((images.size(0),), logits.size(0), dtype=torch.long)
            loss = criterion(logits.log_softmax(2), targets, input_lengths, target_lengths)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        val = evaluate(model, loaders["val"], device)
        if val["exact_accuracy"] >= best["val"]:
            best = {"val": val["exact_accuracy"], "epoch": epoch, "val_metrics": val}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"state_dict": model.state_dict(), "vocab": VOCAB, "image_size": IMAGE_SIZE,
                        "reading_format": args.reading_format, "meter_family": args.meter_family,
                        "metrics": best}, args.output)
        if epoch == 1 or epoch == args.epochs or epoch % 10 == 0:
            print(json.dumps({"epoch": epoch, "loss": sum(losses) / max(1, len(losses)), "val": val}, ensure_ascii=False))
    checkpoint = torch.load(args.output, map_location=device)
    model.load_state_dict(checkpoint["state_dict"])
    checkpoint["metrics"]["test_metrics"] = evaluate(model, loaders["test"], device)
    torch.save(checkpoint, args.output)
    print(json.dumps({"device": str(device), "metrics": checkpoint["metrics"], "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
