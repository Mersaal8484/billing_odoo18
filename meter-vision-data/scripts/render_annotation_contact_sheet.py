"""Render labelled source thumbnails for manual meter-family classification."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=5)
    args = parser.parse_args()
    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = payload.get("images", [])
    cell_w, cell_h, caption_h = 220, 180, 38
    sheet = Image.new("RGB", (args.columns * cell_w, ((len(rows) + args.columns - 1) // args.columns) * (cell_h + caption_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(rows):
        source = args.root / Path(item["source_path"])
        if not source.exists():
            continue
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            thumb = ImageOps.contain(image, (cell_w - 8, cell_h - 8), Image.Resampling.LANCZOS)
        col, row = index % args.columns, index // args.columns
        left, top = col * cell_w, row * (cell_h + caption_h)
        sheet.paste(thumb, (left + (cell_w - thumb.width) // 2, top + (cell_h - thumb.height) // 2))
        label = f"{Path(item['image_id']).name} | {item.get('reading', '')}"
        draw.text((left + 4, top + cell_h + 3), label, fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=90)
    print(args.output)


if __name__ == "__main__":
    main()
