from dataclasses import dataclass

from PIL import Image

from .model_registry import model_status


@dataclass
class PipelineDecision:
    state: str
    flags: list[str]
    auto_approval_eligible: bool


def run_validation_gates(image: Image.Image, quality_score: float,
                         ocr_confidence: float, ocr_flags: list[str]) -> PipelineDecision:
    flags = list(ocr_flags)
    models = {item["key"]: item for item in model_status()}
    if quality_score < 0.75:
        flags.append("QUALITY_BELOW_AUTO_THRESHOLD")
    if not models["meter_detector"]["weights_available"]:
        flags.append("METER_DETECTOR_WEIGHTS_NOT_READY")
    if not models["meter_type_classifier"]["weights_available"]:
        flags.append("METER_TYPE_WEIGHTS_NOT_READY")
    if not models["reading_ocr"]["weights_available"]:
        flags.append("CUSTOM_OCR_WEIGHTS_NOT_READY")
    if ocr_confidence < 0.95:
        flags.append("OCR_BELOW_AUTO_THRESHOLD")
    # Baseline OCR is deliberately never auto-approved until trained weights,
    # detector and consistency rules are available.
    eligible = not flags and all(
        models[key]["weights_available"]
        for key in ("meter_detector", "meter_type_classifier", "reading_ocr")
    )
    return PipelineDecision(
        state="completed" if eligible else "needs_review",
        flags=list(dict.fromkeys(flags)),
        auto_approval_eligible=eligible,
    )
