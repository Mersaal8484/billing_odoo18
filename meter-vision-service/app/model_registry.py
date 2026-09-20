import json
from pathlib import Path


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "models" / "model_manifest.json"


def load_manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def model_status() -> list[dict]:
    manifest = load_manifest()
    result = []
    for model in manifest["models"]:
        weights = Path(__file__).resolve().parent.parent / model["weights"]
        item = dict(model)
        item["weights_available"] = weights.exists()
        item["status"] = "ready" if weights.exists() else "not_ready"
        result.append(item)
    return result
