"""Automatic LCD/digital display detection for electricity meter images.

Attempts to locate the meter display bounding box without manual annotation.
Returns None when no credible display region is found so the caller can fall
back to manual crop or flag the image for review.

Detection strategy (in order):
1. Upscale small images (<= 400px on short side) to improve mask quality.
2. HSV colour mask: green-yellow LCD glass + bright white/gray backlit panel.
3. Morphological join + contour scoring (aspect-ratio and area filters).
4. Brightness percentile fallback (night shots, dirty glass, gray LCD).
5. Adaptive CLAHE + Otsu fallback for remaining edge cases.
"""
from __future__ import annotations

from typing import Optional

# Minimum short-side pixel count before upscaling for detection
_MIN_DETECT_SIDE = 400


def auto_detect_display(
    image,
    min_area_ratio: float = 0.005,
    max_area_ratio: float = 0.70,
    min_aspect: float = 1.0,
    max_aspect: float = 16.0,
) -> Optional[dict]:
    """Return {x, y, w, h} of the best display candidate or None.

    Parameters
    ----------
    image:
        A PIL Image (RGB) or a numpy BGR array (as returned by cv2.imread).
    min_area_ratio / max_area_ratio:
        Fraction of total image area that the detected region must occupy.
    min_aspect / max_aspect:
        Width-to-height ratio constraints for the display window.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    # Accept both PIL and numpy/cv2 inputs
    if hasattr(image, "convert"):
        rgb = np.asarray(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        bgr = image

    orig_h, orig_w = bgr.shape[:2]

    # ------------------------------------------------------------------
    # Stage 0: Upscale very small images for better feature detection
    # ------------------------------------------------------------------
    scale = 1.0
    if min(orig_h, orig_w) < _MIN_DETECT_SIDE:
        scale = _MIN_DETECT_SIDE / min(orig_h, orig_w)
        bgr = cv2.resize(bgr, (int(orig_w * scale), int(orig_h * scale)),
                         interpolation=cv2.INTER_LANCZOS4)

    h, w = bgr.shape[:2]
    total_area = h * w

    # ------------------------------------------------------------------
    # Stage 1: HSV colour mask — green-yellow LCD + white/gray panel
    # ------------------------------------------------------------------
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Green-yellow LCD backlight (Holley, ISKRA, etc.)
    lcd_mask = cv2.inRange(hsv, np.array([18, 8, 60]), np.array([115, 255, 255]))

    # Bright white / light-gray panel face (covers inactive LCD state)
    white_mask = cv2.inRange(hsv, np.array([0, 0, 145]), np.array([180, 70, 255]))

    combined = cv2.bitwise_or(lcd_mask, white_mask)

    close_size = max(10, min(h, w) // 35)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_size, close_size))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
    combined = cv2.morphologyEx(
        combined, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )

    best = _score_contours(combined, h, w, total_area,
                           min_area_ratio, max_area_ratio, min_aspect, max_aspect)
    if best:
        return _scale_back(best, scale)

    # ------------------------------------------------------------------
    # Stage 2: Gray-range mask (gray LCD, dim backlight)
    # ------------------------------------------------------------------
    gray_mask = cv2.inRange(hsv, np.array([0, 0, 100]), np.array([180, 100, 255]))
    kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (close_size, close_size))
    gray_closed = cv2.morphologyEx(gray_mask, cv2.MORPH_CLOSE, kernel2)

    best = _score_contours(gray_closed, h, w, total_area,
                           min_area_ratio, max_area_ratio, min_aspect, max_aspect)
    if best:
        return _scale_back(best, scale)

    # ------------------------------------------------------------------
    # Stage 3: Brightness percentile fallback
    # ------------------------------------------------------------------
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    thresh_val = int(np.percentile(enhanced, 70))
    _, bright = cv2.threshold(enhanced, max(thresh_val, 110), 255, cv2.THRESH_BINARY)
    kernel3 = cv2.getStructuringElement(cv2.MORPH_RECT, (close_size, close_size))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel3)

    best = _score_contours(bright, h, w, total_area,
                           min_area_ratio, max_area_ratio, min_aspect, max_aspect)
    if best:
        return _scale_back(best, scale)

    # ------------------------------------------------------------------
    # Stage 4: Canny edges (last resort, no fill requirement)
    # ------------------------------------------------------------------
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    edges = cv2.Canny(blurred, 25, 90)
    dil_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (4, 4))
    edges = cv2.dilate(edges, dil_kernel, iterations=2)

    best = _score_contours(edges, h, w, total_area,
                           min_area_ratio * 0.4, max_area_ratio,
                           min_aspect, max_aspect, require_fill=False)
    if best:
        return _scale_back(best, scale)

    return None


def _scale_back(bbox: dict, scale: float) -> dict:
    """Convert coordinates from upscaled space back to original image space."""
    if scale == 1.0:
        return bbox
    return {
        "x": int(bbox["x"] / scale),
        "y": int(bbox["y"] / scale),
        "w": max(1, int(bbox["w"] / scale)),
        "h": max(1, int(bbox["h"] / scale)),
    }


def _score_contours(
    mask,
    h: int,
    w: int,
    total_area: int,
    min_area_ratio: float,
    max_area_ratio: float,
    min_aspect: float,
    max_aspect: float,
    require_fill: bool = True,
) -> Optional[dict]:
    """Find the best bounding box among contours in mask."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = result[0] if len(result) == 2 else result[1]

    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < total_area * min_area_ratio:
            continue
        if area > total_area * max_area_ratio:
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        asp = bw / max(1, bh)
        if asp < min_aspect or asp > max_aspect:
            continue
        # Prefer displays in the upper 88% of the frame (meter body)
        if by > h * 0.88:
            continue
        # Reject extremely thin strips (likely a label, not a display)
        if bh < h * 0.035:
            continue
        if require_fill:
            roi_mask = mask[by: by + bh, bx: bx + bw]
            fill = float(roi_mask.sum()) / max(1, bh * bw * 255)
            if fill < 0.18:
                continue
        else:
            fill = 0.5
        # Score: area * fill * aspect-ratio proximity to 4:1 (typical LCD)
        score = area * (0.4 + fill) * (1.0 - abs(asp - 4.0) / 20.0)
        candidates.append((score, bx, by, bw, bh))

    if not candidates:
        return None
    _, bx, by, bw, bh = max(candidates)
    return {"x": int(bx), "y": int(by), "w": int(bw), "h": int(bh)}
