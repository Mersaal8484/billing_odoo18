import base64
import binascii
import io
import os
import re
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps

from .schemas import ConfidenceValue, InferenceRequest, InferenceResponse, QualityResult
from .model_registry import model_status
from .pipeline import run_validation_gates

MODEL_NAME = os.getenv("METER_VISION_MODEL", "baseline-ocr")
MODEL_VERSION = os.getenv("METER_VISION_MODEL_VERSION", "0.1.0")
MAX_IMAGE_BYTES = int(os.getenv("METER_VISION_MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))

_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)
_NUMBER_RE = re.compile(r"(?<!\d)(\d{2,}(?:[.,]\d{1,3})?)(?!\d)")


def _decode_image(encoded: str) -> bytes:
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("invalid base64 image") from error
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("image is empty or exceeds the configured size limit")
    return raw


def _prepare_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (OSError, ValueError) as error:
        raise ValueError("invalid image payload") from error
    image = ImageOps.exif_transpose(image).convert("RGB")
    if image.width < 240 or image.height < 160:
        return image
    scale = min(1600 / image.width, 1600 / image.height, 2.0)
    if scale > 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    return image


def _quality(image: Image.Image) -> QualityResult:
    gray = ImageOps.grayscale(image)
    sample = gray.resize((1, 1)).getpixel((0, 0))
    score = 1.0
    if min(image.width, image.height) < 300:
        score -= 0.35
    if sample < 35 or sample > 235:
        score -= 0.25
    score = max(0.0, min(1.0, score))
    state = "good" if score >= 0.75 else "review" if score >= 0.45 else "poor"
    return QualityResult(state=state, score=round(score, 4), width=image.width, height=image.height)


def _ocr(image: Image.Image, language: str) -> tuple[str, Optional[str], float, list[str]]:
    try:
        import pytesseract
    except ImportError:
        return "", None, 0.0, ["OCR_ENGINE_UNAVAILABLE"]

    prepared = ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(1.5)
    try:
        text = pytesseract.image_to_string(prepared, lang=language or "eng", config="--psm 6")
    except (OSError, RuntimeError):
        return "", None, 0.0, ["OCR_ENGINE_UNAVAILABLE"]
    normalized = text.translate(_DIGIT_TRANSLATION)
    candidates = [match.replace(",", ".") for match in _NUMBER_RE.findall(normalized)]
    candidates = [candidate for candidate in candidates if len(candidate.replace(".", "")) >= 3]
    if len(candidates) == 1:
        return text, candidates[0], 0.65, []
    if not candidates:
        return text, None, 0.0, ["NO_READING_DETECTED"]
    return text, None, 0.25, ["MULTIPLE_NUMERIC_CANDIDATES"]


def analyze(request: InferenceRequest) -> InferenceResponse:
    try:
        image = _prepare_image(_decode_image(request.image_base64))
    except ValueError as error:
        raise ValueError(str(error)) from error
    quality = _quality(image)
    raw_text, candidate, confidence, flags = _ocr(image, request.language_hint)
    if quality.state == "poor":
        flags.append("LOW_IMAGE_QUALITY")
    decision = run_validation_gates(image, quality.score, confidence, flags)
    statuses = {item["key"]: item for item in model_status()}
    stages = [
        {"name": "quality", "state": quality.state, "confidence": quality.score,
         "weights_status": statuses["image_quality"]["status"]},
        {"name": "meter_detection", "state": "not_ready", "confidence": 0.0,
         "weights_status": statuses["meter_detector"]["status"]},
        {"name": "meter_type", "state": "not_ready", "confidence": 0.0,
         "weights_status": statuses["meter_type_classifier"]["status"]},
        {"name": "reading_ocr", "state": "completed" if candidate else "needs_review",
         "confidence": confidence, "weights_status": statuses["reading_ocr"]["status"]},
    ]
    return InferenceResponse(
        request_id=request.request_id,
        state=decision.state,
        model=MODEL_NAME,
        model_version=MODEL_VERSION,
        quality=quality,
        reading=ConfidenceValue(value=candidate, confidence=confidence),
        raw_text=raw_text,
        flags=decision.flags,
        stages=stages,
        auto_approval_eligible=decision.auto_approval_eligible,
    )
