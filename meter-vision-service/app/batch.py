import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .inference import analyze
from .schemas import InferenceRequest


def run_directory(input_dir: Path, output_file: Path,
                  meter_type_hint: str = "digital_lcd",
                  sample: int = 0,
                  include_thumbnails: bool = False) -> dict:
    """Analyze all images in input_dir and write a JSON report.

    Parameters
    ----------
    input_dir : Path
        Directory containing meter images (searched recursively).
    output_file : Path
        Destination for the JSON report.
    meter_type_hint : str
        Passed to every inference request.  Use "mechanical_roller" for
        analogue dial meters; default "digital_lcd" for LCD displays.
    sample : int
        If > 0, process only the first *sample* images (useful for quick tests).
    """
    all_files = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    )
    files = []
    skipped_thumbnails = 0
    for path in all_files:
        try:
            with Image.open(path) as image:
                is_thumbnail = min(image.size) < 600
        except (OSError, ValueError):
            # Let inference record the error consistently for a corrupt image.
            is_thumbnail = False
        if is_thumbnail and not include_thumbnails:
            skipped_thumbnails += 1
            continue
        files.append(path)
    if sample > 0:
        files = files[:sample]

    rows = []
    for path in files:
        try:
            result = analyze(InferenceRequest(
                request_id=path.name,
                image_base64=base64.b64encode(path.read_bytes()).decode("ascii"),
                meter_type_hint=meter_type_hint,
            ))
            reading_dict = result.reading.model_dump() if hasattr(result.reading, "model_dump") else result.reading.dict()
            quality_dict = result.quality.model_dump() if hasattr(result.quality, "model_dump") else result.quality.dict()
            # Extract detected bbox from preprocessing flags if auto-detection fired
            auto_detected = "AUTO_DISPLAY_DETECTED" in result.flags
            rows.append({
                "image": path.name,
                "state": result.state,
                "quality": quality_dict,
                "reading": reading_dict,
                "flags": result.flags,
                "auto_display_detected": auto_detected,
                "auto_approval_eligible": result.auto_approval_eligible,
            })
        except (OSError, ValueError) as error:
            rows.append({"image": path.name, "state": "failed", "error": str(error)})

    # Summary statistics
    total = len(rows)
    detected = sum(1 for r in rows if r.get("auto_display_detected"))
    reading_found = sum(1 for r in rows if r.get("reading", {}).get("value") is not None)
    confidences = [r["reading"]["confidence"] for r in rows
                   if r.get("reading", {}).get("value") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "meter_type_hint": meter_type_hint,
        "image_count": total,
        "source_image_count": len(all_files),
        "skipped_thumbnail_count": skipped_thumbnails,
        "include_thumbnails": include_thumbnails,
        "auto_detect_success": detected,
        "auto_detect_rate": round(detected / max(1, total), 4),
        "reading_found": reading_found,
        "reading_found_rate": round(reading_found / max(1, total), 4),
        "avg_reading_confidence": avg_confidence,
        "results": rows,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run meter vision baseline over a directory")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_file", type=Path)
    parser.add_argument("--meter-type", default="digital_lcd",
                        help="digital_lcd (default) | mechanical_roller | mechanical_round")
    parser.add_argument("--sample", type=int, default=0,
                        help="Process only the first N images (0 = all)")
    parser.add_argument("--include-thumbnails", action="store_true",
                        help="Also process source images smaller than 600px (review-only)")
    args = parser.parse_args()
    report = run_directory(args.input_dir, args.output_file,
                           meter_type_hint=args.meter_type,
                           sample=args.sample,
                           include_thumbnails=args.include_thumbnails)
    summary = {
        "image_count": report["image_count"],
        "auto_detect_rate": report["auto_detect_rate"],
        "reading_found_rate": report["reading_found_rate"],
        "avg_reading_confidence": report["avg_reading_confidence"],
        "output": str(args.output_file),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
