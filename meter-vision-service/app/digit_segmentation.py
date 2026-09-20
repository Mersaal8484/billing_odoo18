"""Contour-based digit ROI extraction for a confirmed meter display crop."""

from dataclasses import dataclass
from typing import Optional

from PIL import Image


@dataclass(frozen=True)
class DigitROI:
    x: int
    y: int
    w: int
    h: int


def segment_digits(image: Image.Image, expected_digits: Optional[int] = None) -> tuple[list[DigitROI], list[str]]:
    """Find, filter, and order digit contours from left to right.

    The display is already cropped and deskewed.  We deliberately reject a
    contour set with an unexpected count instead of inventing digit positions.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return [], ["OPENCV_SEGMENTATION_UNAVAILABLE"]

    gray = np.asarray(image.convert("L"))
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    result = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = result[0] if len(result) == 2 else result[1]

    height, width = gray.shape
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        ratio = w / max(1, h)
        if h < height * 0.30 or h > height * 0.96:
            continue
        if w < width * 0.018 or w > width * 0.24:
            continue
        if ratio < 0.07 or ratio > 1.15:
            continue
        candidates.append(DigitROI(int(x), int(y), int(w), int(h)))

    if not candidates:
        return [], ["DIGIT_CONTOURS_NOT_FOUND"]
    # Digit windows share a common baseline.  Remove isolated labels/units.
    median_y = sorted(roi.y + roi.h / 2 for roi in candidates)[len(candidates) // 2]
    candidates = [roi for roi in candidates if abs((roi.y + roi.h / 2) - median_y) <= height * 0.22]
    candidates.sort(key=lambda roi: roi.x)
    if expected_digits and len(candidates) != expected_digits:
        return candidates, ["DIGIT_CONTOUR_COUNT_MISMATCH"]
    if len(candidates) < 3:
        return candidates, ["DIGIT_CONTOUR_COUNT_TOO_LOW"]
    return candidates, ["DIGIT_CONTOURS_SEGMENTED"]


def crop_roi(image: Image.Image, roi: DigitROI, padding: int = 3) -> Image.Image:
    return image.crop((max(0, roi.x - padding), max(0, roi.y - padding),
                       min(image.width, roi.x + roi.w + padding), min(image.height, roi.y + roi.h + padding)))
