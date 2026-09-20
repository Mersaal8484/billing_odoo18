import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from .inference import analyze
from .schemas import InferenceRequest


def run_directory(input_dir: Path, output_file: Path) -> dict:
    files = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
    )
    rows = []
    for path in files:
        try:
            result = analyze(InferenceRequest(
                request_id=path.name,
                image_base64=base64.b64encode(path.read_bytes()).decode("ascii"),
            ))
            rows.append({
                "image": path.name,
                "state": result.state,
                "quality": result.quality.model_dump() if hasattr(result.quality, "model_dump") else result.quality.dict(),
                "reading": result.reading.model_dump() if hasattr(result.reading, "model_dump") else result.reading.dict(),
                "flags": result.flags,
                "auto_approval_eligible": result.auto_approval_eligible,
                "stages": [stage.model_dump() if hasattr(stage, "model_dump") else stage.dict() for stage in result.stages],
            })
        except (OSError, ValueError) as error:
            rows.append({"image": path.name, "state": "failed", "error": str(error)})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "image_count": len(files),
        "results": rows,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run meter vision baseline over a directory")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_file", type=Path)
    args = parser.parse_args()
    report = run_directory(args.input_dir, args.output_file)
    print(json.dumps({"image_count": report["image_count"], "output": str(args.output_file)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
