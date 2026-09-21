from PIL import Image, ImageEnhance, ImageFilter, ImageOps


MIN_SOURCE_SIDE = 600
TARGET_SIDE = 900


def professional_display_preprocess(image: Image.Image) -> tuple[Image.Image, list[str]]:
    """Deskew a confirmed display crop before OCR using OpenCV when available.

    Canny + Hough lines estimate the horizontal register angle.  A conservative
    rotation is applied only for a credible small angle, preventing labels,
    barcode lines, or vertical meter edges from flipping the crop.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        fallback = ImageOps.grayscale(image).filter(ImageFilter.MedianFilter(size=3))
        return fallback.convert("RGB"), ["PIL_GRAYSCALE_DENOISE_FALLBACK"]

    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    denoised = cv2.bilateralFilter(gray, 7, 45, 45)
    edges = cv2.Canny(denoised, 50, 150, apertureSize=3)
    min_length = max(20, int(image.width * 0.22))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=24, minLineLength=min_length, maxLineGap=12)
    angles = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle) <= 18:
                angles.append(angle)
    flags = ["OPENCV_GRAYSCALE", "BILATERAL_DENOISE", "CANNY_EDGES"]
    if angles:
        angle = float(np.median(angles))
        flags.append("HOUGH_SKEW_ESTIMATED")
        if abs(angle) >= 0.45:
            matrix = cv2.getRotationMatrix2D((image.width / 2, image.height / 2), angle, 1.0)
            denoised = cv2.warpAffine(denoised, matrix, (image.width, image.height), flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_REPLICATE)
            flags.append("SKEW_ROTATION_APPLIED")
    else:
        flags.append("SKEW_NOT_DETECTED")
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
    return Image.fromarray(clahe).convert("RGB"), flags + ["CLAHE_LOCAL_CONTRAST"]


def prepare_for_vision(image: Image.Image) -> tuple[Image.Image, tuple[int, int], bool]:
    """Normalize field captures while retaining the original dimensions for gating."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    original_size = image.size
    low_resolution = min(original_size) < MIN_SOURCE_SIDE
    if low_resolution:
        scale = min(4.0, TARGET_SIDE / max(1, min(original_size)))
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.15)
    image = ImageEnhance.Sharpness(image).enhance(1.35)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
    return image, original_size, low_resolution


def correct_display_perspective(image: Image.Image, quad: list[int]) -> Image.Image:
    """Rectify a display from four source points: TL, TR, BR, BL.

    The annotation tool stores points in original-image pixel coordinates. PIL's
    QUAD transform maps that quadrilateral onto a clean rectangular crop, which
    makes slanted field captures usable without introducing a heavy CV runtime.
    """
    if len(quad) != 8:
        raise ValueError("display_quad must contain 8 coordinates")
    points = [(quad[index], quad[index + 1]) for index in range(0, 8, 2)]
    top_left, top_right, bottom_right, bottom_left = points
    width = max(
        1,
        int(max(
            ((bottom_right[0] - bottom_left[0]) ** 2 + (bottom_right[1] - bottom_left[1]) ** 2) ** 0.5,
            ((top_right[0] - top_left[0]) ** 2 + (top_right[1] - top_left[1]) ** 2) ** 0.5,
        )),
    )
    height = max(
        1,
        int(max(
            ((bottom_left[0] - top_left[0]) ** 2 + (bottom_left[1] - top_left[1]) ** 2) ** 0.5,
            ((bottom_right[0] - top_right[0]) ** 2 + (bottom_right[1] - top_right[1]) ** 2) ** 0.5,
        )),
    )
    return image.transform(
        (width, height),
        Image.Transform.QUAD,
        tuple(value for point in points for value in point),
        resample=Image.Resampling.BICUBIC,
    )


def build_ocr_variants(image: Image.Image) -> list[Image.Image]:
    """Create conservative variants for glare, low contrast, and dirty glass."""
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    scale = max(2, min(5, 1600 // max(1, gray.width)))
    enlarged = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
    denoised = enlarged.filter(ImageFilter.MedianFilter(size=3))
    sharp = denoised.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))
    contrast = ImageEnhance.Contrast(sharp).enhance(1.7)
    variants = [
        contrast,
        ImageOps.autocontrast(denoised, cutoff=2),
        contrast.point(lambda value: 255 if value > 145 else 0),
        contrast.point(lambda value: 255 if value > 185 else 0),
    ]
    try:
        import cv2
        import numpy as np
        matrix = np.asarray(contrast)
        _, otsu = cv2.threshold(matrix, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(matrix, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 5)
        variants.extend([Image.fromarray(otsu), Image.fromarray(adaptive)])
    except ImportError:
        pass
    return variants


def roller_register_variants(image: Image.Image) -> tuple[list[Image.Image], list[str]]:
    """Return the original display and a tightly localized roller register.

    The annotated display may contain units, separators, or a wide bright
    margin.  Mechanical wheels typically form one dark, horizontally elongated
    band.  Localizing that band gives OCR a second, independent image without
    destroying the original crop when the detector is uncertain.
    """
    variants = [image]
    try:
        import cv2
        import numpy as np
    except ImportError:
        return variants, ["ROLLER_WINDOW_LOCALIZATION_UNAVAILABLE"]

    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    if width < 40 or height < 24:
        return variants, ["ROLLER_WINDOW_TOO_SMALL"]
    smooth = cv2.bilateralFilter(gray, 5, 35, 35)
    _, dark = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(5, width // 18), max(2, height // 18)))
    joined = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, kernel)
    result = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = result[0] if len(result) == 2 else result[1]
    candidates = []
    for contour in contours:
        x, y, candidate_width, candidate_height = cv2.boundingRect(contour)
        if candidate_width < width * 0.38 or candidate_height < height * 0.20:
            continue
        if candidate_height > height * 0.92:
            continue
        density = float(dark[y:y + candidate_height, x:x + candidate_width].mean()) / 255.0
        score = candidate_width * candidate_height * (0.6 + density)
        candidates.append((score, x, y, candidate_width, candidate_height))
    if not candidates:
        return variants, ["ROLLER_WINDOW_NOT_LOCALIZED"]
    _, x, y, candidate_width, candidate_height = max(candidates)
    pad_x, pad_y = max(2, width // 80), max(2, height // 12)
    left, top = max(0, x - pad_x), max(0, y - pad_y)
    right, bottom = min(width, x + candidate_width + pad_x), min(height, y + candidate_height + pad_y)
    if right - left < width * 0.35:
        return variants, ["ROLLER_WINDOW_NOT_LOCALIZED"]
    variants.append(image.crop((left, top, right, bottom)))
    return variants, ["ROLLER_WINDOW_LOCALIZED"]
