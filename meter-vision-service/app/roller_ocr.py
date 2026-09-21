"""OCR ensemble for mechanical roller displays."""

import os
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from PIL import Image

from .digit_segmentation import crop_roi, segment_digits
from .image_enhancement import build_ocr_variants, roller_register_variants


_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIGITS = re.compile(r"\d{3,12}")


def _direct_display_candidates(image: Image.Image, expected_digits: Optional[int]) -> tuple[Counter, dict[str, set[int]], list[str]]:
    """Read an unmodified display crop before aggressive image processing.

    Mechanical rollers have strong physical borders and high-contrast glyphs.
    On such images, thresholding or skew correction can join neighbouring
    rollers, while the original crop is often immediately readable.
    """
    try:
        import pytesseract
    except ImportError:
        return Counter(), {}, ["OCR_ENGINE_UNAVAILABLE"]
    variants, flags = roller_register_variants(image)
    candidates = []
    sources: dict[str, set[int]] = {}
    for index, variant in enumerate(variants):
        scaled = variant.resize((variant.width * 4, variant.height * 4), Image.Resampling.LANCZOS)
        for psm in (8, 13):
            text = pytesseract.image_to_string(
                scaled, lang="eng", config=f"--psm {psm} -c tessedit_char_whitelist=0123456789"
            ).translate(_DIGIT_TRANSLATION)
            for candidate in _DIGITS.findall(text):
                if not expected_digits or len(candidate) == expected_digits:
                    candidates.append(candidate)
                    sources.setdefault(candidate, set()).add(index)
    return Counter(candidates), sources, flags


def recognize(image: Image.Image, expected_digits: Optional[int] = None,
              original_display: Optional[Image.Image] = None) -> tuple[Optional[str], float, list[str]]:
    rois, segmentation_flags = segment_digits(image, expected_digits)
    try:
        import pytesseract
    except ImportError:
        return None, 0.0, segmentation_flags + ["OCR_ENGINE_UNAVAILABLE"]

    if os.name == "nt" and not os.environ.get("TESSERACT_CMD"):
        default_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if default_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(default_path)
    elif os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

    candidates: list[str] = []
    try:
        # Prefer a stable agreement on the original confirmed display crop.
        # It avoids a false result caused by preprocessing on roller borders.
        if original_display is not None:
            direct, sources, direct_flags = _direct_display_candidates(original_display, expected_digits)
            if direct:
                candidate, votes = direct.most_common(1)[0]
                # Matching a whole display and its localized register is a
                # stronger signal than PSM variants of the same pixels.
                if votes >= 2 and (len(sources.get(candidate, set())) >= 2 or len(sources) == 1):
                    confidence = min(0.92, 0.60 + votes / max(1, sum(direct.values())) * 0.32)
                    return candidate, round(confidence, 4), segmentation_flags + direct_flags + ["RAW_DISPLAY_OCR_ENSEMBLE"]
        for variant in build_ocr_variants(image):
            for psm in (7, 8, 13):
                text = pytesseract.image_to_string(
                    variant,
                    lang="eng",
                    config=f"--psm {psm} -c tessedit_char_whitelist=0123456789",
                ).translate(_DIGIT_TRANSLATION)
                for candidate in _DIGITS.findall(text):
                    if expected_digits and len(candidate) != expected_digits:
                        continue
                    candidates.append(candidate)
        # OCR on individual, contour-derived digit ROIs is used only when the
        # segmentation count agrees with the expected meter register width.
        if rois and (not expected_digits or len(rois) == expected_digits):
            segmented = []
            for roi in rois:
                votes = []
                for variant in build_ocr_variants(crop_roi(image, roi))[:3]:
                    text = pytesseract.image_to_string(
                        variant, lang="eng", config="--psm 10 -c tessedit_char_whitelist=0123456789"
                    ).translate(_DIGIT_TRANSLATION)
                    votes.extend(_DIGITS.findall(text))
                if not votes:
                    segmented = []
                    break
                digit, count = Counter(votes).most_common(1)[0]
                if len(digit) != 1 or count < 2:
                    segmented = []
                    break
                segmented.append(digit)
            if segmented:
                candidates.extend(["".join(segmented)] * 2)
    except (OSError, RuntimeError):
        return None, 0.0, segmentation_flags + ["OCR_ENGINE_UNAVAILABLE"]

    if not candidates:
        return None, 0.0, segmentation_flags + ["NO_READING_DETECTED"]
    counts = Counter(candidates)
    candidate, votes = counts.most_common(1)[0]
    agreement = votes / len(candidates)
    confidence = min(0.94, 0.42 + agreement * 0.48)
    if votes < 2 or confidence < 0.68:
        return None, round(confidence, 4), segmentation_flags + ["OCR_CANDIDATES_DISAGREE", "ROLLER_REVIEW_REQUIRED"]
    return candidate, round(confidence, 4), segmentation_flags + ["ROLLER_OCR_ENSEMBLE"]
