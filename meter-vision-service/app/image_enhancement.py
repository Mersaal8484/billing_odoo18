from PIL import Image, ImageEnhance, ImageFilter, ImageOps


MIN_SOURCE_SIDE = 600
TARGET_SIDE = 900


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
