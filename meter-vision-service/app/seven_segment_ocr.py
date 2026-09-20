"""Small, deterministic OCR baseline for seven-segment electricity displays.

This is deliberately separate from generic document OCR.  It only returns a
reading when a display crop can be explained by seven-segment digit geometry;
otherwise the caller must send the image to manual review.
"""

from collections import Counter
from typing import Optional

from PIL import Image, ImageOps


SEGMENTS = {
    "0": "ab cdef".replace(" ", ""), "1": "bc", "2": "abdeg",
    "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
    "7": "abc", "8": "abcdefg", "9": "abcdfg",
}
ROIS = {
    "a": (0.20, 0.06, 0.80, 0.18), "b": (0.72, 0.14, 0.90, 0.50),
    "c": (0.72, 0.52, 0.90, 0.88), "d": (0.20, 0.82, 0.80, 0.95),
    "e": (0.10, 0.52, 0.28, 0.88), "f": (0.10, 0.14, 0.28, 0.50),
    "g": (0.20, 0.43, 0.80, 0.58),
}


def _otsu(gray: Image.Image) -> int:
    histogram = gray.histogram()[:256]
    total = sum(histogram)
    sum_total = sum(index * count for index, count in enumerate(histogram))
    weight_bg = sum_bg = best = 0
    threshold = 128
    for index, count in enumerate(histogram):
        weight_bg += count
        if not weight_bg or weight_bg == total:
            continue
        sum_bg += index * count
        weight_fg = total - weight_bg
        between = (sum_bg * weight_fg / weight_bg - (sum_total - sum_bg)) ** 2
        between *= weight_bg * weight_fg
        if between > best:
            best, threshold = between, index
    return threshold


def _active_pixels(image: Image.Image, invert: bool) -> Image.Image:
    gray = ImageOps.grayscale(image).resize((max(240, image.width * 2), max(100, image.height * 2)))
    threshold = _otsu(gray)
    if invert:
        return gray.point(lambda value: 255 if value > threshold else 0)
    return gray.point(lambda value: 255 if value <= threshold else 0)


def _trim(binary: Image.Image) -> Image.Image:
    bbox = binary.getbbox()
    if not bbox:
        return binary
    left, top, right, bottom = bbox
    return binary.crop((max(0, left - 3), max(0, top - 3), min(binary.width, right + 3), min(binary.height, bottom + 3)))


def _segment_pattern(cell: Image.Image) -> tuple[set[str], float]:
    cell = cell.resize((100, 180))
    pixels = cell.load()
    active = set()
    occupancies = {}
    for name, (x1, y1, x2, y2) in ROIS.items():
        left, top = int(x1 * cell.width), int(y1 * cell.height)
        right, bottom = int(x2 * cell.width), int(y2 * cell.height)
        values = [pixels[x, y] > 0 for y in range(top, bottom) for x in range(left, right)]
        occupancy = sum(values) / max(1, len(values))
        occupancies[name] = occupancy
        if occupancy >= 0.22:
            active.add(name)
    return active, sum(occupancies.values()) / 7.0


def _classify(active: set[str]) -> tuple[Optional[str], float]:
    scores = []
    for digit, segments in SEGMENTS.items():
        expected = set(segments)
        distance = len(active ^ expected)
        scores.append((distance, digit))
    distance, digit = min(scores)
    # A segment pattern with too many lit/unlit errors is not a reading.
    return (digit, round(1.0 - distance / 7.0, 4)) if distance <= 2 else (None, 0.0)


def recognize(image: Image.Image, expected_digits: Optional[int] = None) -> tuple[Optional[str], float, list[str]]:
    """Recognize a cropped seven-segment display, returning value/confidence/flags."""
    candidates = []
    for invert in (False, True):
        binary = _active_pixels(image, invert)
        foreground_ratio = sum(binary.getdata()) / (255 * binary.width * binary.height)
        # The background must not be treated as the seven-segment foreground.
        if foreground_ratio > 0.55 or foreground_ratio < 0.005:
            continue
        if expected_digits:
            bbox = binary.getbbox()
            if bbox:
                binary = binary.crop((0, max(0, bbox[1] - 3), binary.width,
                                      min(binary.height, bbox[3] + 3)))
        else:
            binary = _trim(binary)
        if binary.width < binary.height // 2:
            continue
        min_digits = expected_digits or 4
        max_digits = expected_digits or 12
        for count in range(min_digits, max_digits + 1):
            # Leave a small gutter around the crop; each cell is one display digit.
            gutter = max(2, int(binary.width * 0.02))
            usable = binary.crop((gutter, 0, max(gutter + 1, binary.width - gutter), binary.height))
            width = usable.width / count
            value, confidences = [], []
            for index in range(count):
                left = int(index * width + width * 0.06)
                right = int((index + 1) * width - width * 0.06)
                cell = usable.crop((left, 0, max(left + 1, right), usable.height))
                active, _occupancy = _segment_pattern(cell)
                digit, confidence = _classify(active)
                if digit is None:
                    break
                value.append(digit)
                confidences.append(confidence)
            if len(value) == count:
                candidates.append((sum(confidences) / count, "".join(value), invert, count))
    if not candidates:
        return None, 0.0, ["SEVEN_SEGMENT_PATTERN_NOT_FOUND"]
    candidates.sort(reverse=True)
    best = candidates[0]
    same_value = [item for item in candidates if item[1] == best[1]]
    confidence = min(0.96, best[0] * (1.0 if len(same_value) > 1 else 0.85))
    if confidence < 0.72:
        return None, round(confidence, 4), ["SEVEN_SEGMENT_LOW_CONFIDENCE"]
    return best[1], round(confidence, 4), []
