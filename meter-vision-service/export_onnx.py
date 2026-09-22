"""Export PyTorch checkpoints to ONNX for production inference.

Usage
-----
    python export_onnx.py                        # export all available checkpoints
    python export_onnx.py --checkpoint reading_ocr.pt --type crnn
    python export_onnx.py --checkpoint mechanical_roller_digit_cnn.pt --type digit_cnn

Output goes to models/ directory alongside existing weights.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


VOCAB = "0123456789."


class CRNN(nn.Module):
    """Small CRNN (16→32→64→64 channels, 1-layer LSTM)."""
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


class CRNNWide(nn.Module):
    """Wide CRNN (32→64→128→128 channels, 2-layer LSTM) — reading_ocr.pt."""
    def __init__(self, num_classes: int = len(VOCAB) + 1):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d((2, 1)),
        )
        # Compute LSTM input size from a dummy forward pass
        with torch.no_grad():
            dummy_feat = self.features(torch.randn(1, 1, 64, 256))
            feat_size = dummy_feat.shape[1] * dummy_feat.shape[2]  # channels * height
        self.rnn = nn.LSTM(feat_size, 128, bidirectional=True, num_layers=2)
        self.classifier = nn.Linear(256, num_classes)

    def forward(self, images):
        features = self.features(images)
        batch, channels, height, width = features.shape
        sequence = features.permute(3, 0, 1, 2).contiguous().view(width, batch, channels * height)
        return self.classifier(self.rnn(sequence)[0])


class DigitCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 24, 3, padding=1), nn.BatchNorm2d(24), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(24, 48, 3, padding=1), nn.BatchNorm2d(48), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(48, 96, 3, padding=1), nn.BatchNorm2d(96), nn.ReLU(),
            nn.AdaptiveAvgPool2d((3, 2)),
        )
        self.classifier = nn.Sequential(nn.Flatten(), nn.Dropout(0.2), nn.Linear(96 * 3 * 2, 10))

    def forward(self, images):
        return self.classifier(self.features(images))


EXPORT_DIR = Path(__file__).resolve().parent / "models"


def export_crnn(checkpoint_path: Path, output_path: Path) -> dict:
    """Export CRNN checkpoint to ONNX — auto-detects small vs wide architecture."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    sd = checkpoint["state_dict"]
    image_size = checkpoint.get("image_size", (192, 48))
    input_h, input_w = image_size[1], image_size[0]

    # Auto-detect architecture from state_dict keys
    if "rnn.weight_ih_l1" in sd:
        num_classes = sd["classifier.weight"].shape[0]
        model = CRNNWide(num_classes=num_classes)
    else:
        model = CRNN()
    model.load_state_dict(sd)
    model.eval()

    dummy = torch.randn(1, 1, input_h, input_w)
    torch.onnx.export(
        model, dummy, str(output_path),
        input_names=["image"], output_names=["logits"],
        opset_version=18,
    )
    return {
        "type": "crnn-ctc",
        "input_shape": [1, 1, input_h, input_w],
        "vocab": VOCAB,
        "blank_index": len(VOCAB),
        "source_checkpoint": str(checkpoint_path.name),
    }


def export_digit_cnn(checkpoint_path: Path, output_path: Path) -> dict:
    """Export DigitCNN checkpoint to ONNX."""
    model = DigitCNN()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    dummy = torch.randn(1, 1, 72, 48)
    torch.onnx.export(
        model, dummy, str(output_path),
        input_names=["image"], output_names=["digit_logits"],
        opset_version=18,
    )
    return {
        "type": "digit-cnn",
        "input_shape": [1, 1, 72, 48],
        "num_classes": 10,
        "source_checkpoint": str(checkpoint_path.name),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, help="Specific .pt file to export")
    parser.add_argument("--type", choices=["crnn", "digit_cnn"], help="Model type (auto-detected if omitted)")
    args = parser.parse_args()

    results = []

    if args.checkpoint:
        checkpoints = [(args.checkpoint, args.type)]
    else:
        # Auto-discover available checkpoints from both models/ and processed/
        models_dir = Path(__file__).resolve().parent / "models"
        processed_dir = Path(__file__).resolve().parents[1] / "meter-vision-data" / "processed"
        checkpoints = []
        for search_dir in (models_dir, processed_dir):
            for pt in search_dir.rglob("*.pt"):
                if "digit_cnn" in pt.name:
                    checkpoints.append((pt, "digit_cnn"))
                elif "reading_ocr" in pt.name:
                    checkpoints.append((pt, "crnn"))

    for ckpt_path, model_type in checkpoints:
        if not ckpt_path.exists():
            print(f"SKIP: {ckpt_path} not found")
            continue

        if model_type == "crnn":
            onnx_name = ckpt_path.stem + ".onnx"
            out_path = EXPORT_DIR / onnx_name
            print(f"Exporting CRNN: {ckpt_path.name} -> {out_path.name}")
            meta = export_crnn(ckpt_path, out_path)
        elif model_type == "digit_cnn":
            onnx_name = ckpt_path.stem + ".onnx"
            out_path = EXPORT_DIR / onnx_name
            print(f"Exporting DigitCNN: {ckpt_path.name} -> {out_path.name}")
            meta = export_digit_cnn(ckpt_path, out_path)
        else:
            print(f"SKIP: unknown type for {ckpt_path}")
            continue

        meta["output_path"] = str(out_path)
        results.append(meta)
        print(f"  OK: {out_path} ({out_path.stat().st_size // 1024} KB)")

    # Write export manifest
    manifest_path = EXPORT_DIR / "onnx_export_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")
    print(f"Exported: {len(results)} model(s)")


if __name__ == "__main__":
    main()
