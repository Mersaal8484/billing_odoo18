"""Convenience wrapper: run the meter-vision batch over D:/datameter.

Usage
-----
    python run_datameter.py
    python run_datameter.py --output ../meter-vision-data/reports/datameter-auto.json
    python run_datameter.py --sample 20 --output quick_test.json
    python run_datameter.py --meter-type mechanical_roller --output roller_test.json

The script prints a one-line summary to stdout after completion.
"""
import argparse
import json
from pathlib import Path

from app.batch import run_directory


DEFAULT_INPUT = Path(r"D:/datameter")
DEFAULT_OUTPUT = Path(r"..\meter-vision-data\reports\datameter-auto.json")


def main():
    parser = argparse.ArgumentParser(
        description="Run meter-vision OCR over D:/datameter and write a JSON report."
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Source image directory (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output JSON report path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--meter-type", default="digital_lcd",
        help="digital_lcd (default) | mechanical_roller | mechanical_round"
    )
    parser.add_argument(
        "--sample", type=int, default=0,
        help="Process only the first N images — 0 means all (default: 0)"
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"ERROR: input directory not found: {args.input}")

    print(f"Processing: {args.input}")
    print(f"Meter type: {args.meter_type}")
    print(f"Sample:     {'all' if args.sample == 0 else args.sample}")
    print(f"Output:     {args.output}\n")

    report = run_directory(
        args.input,
        args.output,
        meter_type_hint=args.meter_type,
        sample=args.sample,
    )

    summary = {
        "image_count":            report["image_count"],
        "auto_detect_success":    report["auto_detect_success"],
        "auto_detect_rate_%":     f"{report['auto_detect_rate'] * 100:.1f}%",
        "reading_found":          report["reading_found"],
        "reading_found_rate_%":   f"{report['reading_found_rate'] * 100:.1f}%",
        "avg_reading_confidence": report["avg_reading_confidence"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nFull report saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()

