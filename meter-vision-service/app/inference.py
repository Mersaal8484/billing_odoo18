import base64
import binascii
import io
import os
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageEnhance, ImageOps

from .schemas import ConfidenceValue, DisplayBBox, InferenceRequest, InferenceResponse, QualityResult
from .model_registry import model_status
from .pipeline import run_validation_gates
from .image_enhancement import correct_display_perspective, prepare_for_vision, professional_display_preprocess
from .roller_ocr import recognize as recognize_roller
from .seven_segment_ocr import recognize as recognize_seven_segment

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


def _load_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (OSError, ValueError) as error:
        raise ValueError("invalid image payload") from error
    return image


def _prepare_image(raw: bytes, display_bbox: Optional[DisplayBBox], display_quad: Optional[list[int]]) -> tuple[Image.Image, tuple[int, int], bool, bool, list[str]]:
    if display_bbox and display_quad:
        raise ValueError("send either display_bbox or display_quad, not both")
    image = _load_image(raw)
    source_size = image.size
    crop_applied = False
    preprocessing = ["EXIF_ORIENTATION_NORMALIZED"]
    if display_quad:
        if any(value < 0 for value in display_quad):
            raise ValueError("display_quad coordinates must be non-negative")
        image = correct_display_perspective(image, display_quad)
        crop_applied = True
        preprocessing.append("PERSPECTIVE_CORRECTED")
    if display_bbox:
        left = display_bbox.x
        top = display_bbox.y
        right = min(image.width, left + display_bbox.w)
        bottom = min(image.height, top + display_bbox.h)
        if left >= image.width or top >= image.height or right <= left or bottom <= top:
            raise ValueError("display_bbox is outside the source image")
        image = image.crop((left, top, right, bottom))
        crop_applied = True
        preprocessing.append("DISPLAY_CROPPED")
    image, display_steps = professional_display_preprocess(image)
    prepared, _, low_resolution = prepare_for_vision(image)
    preprocessing.extend(display_steps)
    preprocessing.append("CONTRAST_SHARPEN_DENOISE")
    return prepared, source_size, low_resolution, crop_applied, preprocessing


def _quality(image: Image.Image, source_size: tuple[int, int], low_resolution: bool) -> QualityResult:
    gray = ImageOps.grayscale(image)
    sample = gray.resize((1, 1)).getpixel((0, 0))
    score = 1.0
    if min(image.width, image.height) < 300:
        score -= 0.35
    if low_resolution:
        score -= 0.20
    if sample < 35 or sample > 235:
        score -= 0.25
    score = max(0.0, min(1.0, score))
    state = "good" if score >= 0.75 else "review" if score >= 0.45 else "poor"
    return QualityResult(state=state, score=round(score, 4), width=image.width, height=image.height,
                         source_width=source_size[0], source_height=source_size[1],
                         low_resolution=low_resolution)


def _ocr(image: Image.Image, language: str) -> tuple[str, Optional[str], float, list[str]]:
    try:
        import pytesseract
    except ImportError:
        return "", None, 0.0, ["OCR_ENGINE_UNAVAILABLE"]

    if os.name == "nt" and not os.environ.get("TESSERACT_CMD"):
        default_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if default_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(default_path)
    elif os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

    # A confirmed display crop is enlarged and evaluated through several
    # seven-segment-friendly variants. Full-photo OCR is intentionally not
    # treated as trustworthy because it tends to read barcodes and overlays.
    gray = ImageOps.grayscale(image)
    scale = max(2, min(5, 1400 // max(1, gray.width)))
    gray = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
    prepared = ImageEnhance.Contrast(gray).enhance(1.8)
    variants = [
        prepared,
        prepared.point(lambda value: 255 if value > 145 else 0),
        prepared.point(lambda value: 255 if value > 185 else 0),
    ]
    configs = ("--psm 7", "--psm 8", "--psm 13")
    texts: list[str] = []
    found: list[str] = []
    try:
        for variant in variants:
            for config in configs:
                text = pytesseract.image_to_string(
                    variant, lang=language or "eng", config=f"{config} -c tessedit_char_whitelist=0123456789.,"
                )
                texts.append(text)
                normalized = text.translate(_DIGIT_TRANSLATION)
                found.extend(match.replace(",", ".") for match in _NUMBER_RE.findall(normalized)
                             if len(match.replace(".", "")) >= 3)
    except (OSError, RuntimeError):
        return "", None, 0.0, ["OCR_ENGINE_UNAVAILABLE"]
    if not found:
        return "\n".join(texts), None, 0.0, ["NO_READING_DETECTED"]
    counts = {}
    for value in found:
        counts[value] = counts.get(value, 0) + 1
    candidate, votes = max(counts.items(), key=lambda item: item[1])
    agreement = votes / max(1, len(found))
    if agreement >= 0.5:
        return "\n".join(texts), candidate, round(min(0.92, 0.45 + agreement * 0.45), 4), []
    return "\n".join(texts), None, 0.2, ["OCR_CANDIDATES_DISAGREE"]


def analyze(request: InferenceRequest) -> InferenceResponse:
    try:
        image, source_size, low_resolution, crop_applied, preprocessing = _prepare_image(
            _decode_image(request.image_base64), request.display_bbox, request.display_quad
        )
    except ValueError as error:
        raise ValueError(str(error)) from error
    quality = _quality(image, source_size, low_resolution)
    if crop_applied:
        experimental_crnn = bool(os.getenv("METER_VISION_EXPERIMENTAL_CRNN", "").strip())
        experimental_digit_cnn = bool(os.getenv("METER_VISION_EXPERIMENTAL_DIGIT_CNN", "").strip())
        if experimental_crnn:
            from .experimental_crnn import recognize as recognize_experimental_crnn
            candidate, confidence, flags = recognize_experimental_crnn(image)
            preprocessing.append("EXPERIMENTAL_CRNN_INPUT")
        elif experimental_digit_cnn and request.meter_type_hint in {"mechanical_roller", "mechanical_round"}:
            from .experimental_digit_cnn import recognize as recognize_experimental_digit_cnn
            candidate, confidence, flags = recognize_experimental_digit_cnn(image, request.expected_digits)
            preprocessing.append("EXPERIMENTAL_DIGIT_CNN_GRID_INPUT")
        elif request.meter_type_hint in {"mechanical_roller", "mechanical_round"}:
            candidate, confidence, flags = recognize_roller(image, request.expected_digits)
        else:
            candidate, confidence, flags = recognize_seven_segment(image, request.expected_digits)
        raw_text = candidate or ""
        if candidate:
            if not experimental_crnn and not experimental_digit_cnn:
                flags.append(
                    "SPECIALIZED_ROLLER_OCR" if request.meter_type_hint in {"mechanical_roller", "mechanical_round"}
                    else "SPECIALIZED_SEVEN_SEGMENT_OCR"
                )
    else:
        raw_text, candidate, confidence, flags = "", None, 0.0, ["DISPLAY_CROP_REQUIRED"]
    if not crop_applied:
        flags.append("DISPLAY_CROP_REQUIRED")
    if quality.state == "poor":
        flags.append("LOW_IMAGE_QUALITY")
    decision = run_validation_gates(image, quality.score, confidence, flags)
    if low_resolution:
        decision.flags.append("LOW_SOURCE_RESOLUTION_UPSCALED")
    statuses = {item["key"]: item for item in model_status()}
    stages = [
        {"name": "quality", "state": quality.state, "confidence": quality.score,
         "weights_status": statuses["image_quality"]["status"]},
        {"name": "meter_detection", "state": "not_ready", "confidence": 0.0,
         "weights_status": statuses["meter_detector"]["status"]},
        {"name": "meter_type", "state": "not_ready", "confidence": 0.0,
         "weights_status": statuses["meter_type_classifier"]["status"]},
        {"name": "digit_segmentation", "state": "completed" if "DIGIT_CONTOURS_SEGMENTED" in flags else "needs_review",
         "confidence": 1.0 if "DIGIT_CONTOURS_SEGMENTED" in flags else 0.0, "weights_status": "rules"},
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
        preprocessing=preprocessing,
        stages=stages,
        auto_approval_eligible=decision.auto_approval_eligible,
    )
