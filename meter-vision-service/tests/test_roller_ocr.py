"""Regression coverage for mechanical register OCR agreement."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.digit_segmentation import DigitROI
from app.roller_ocr import recognize


class TestRollerOCR(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGB", (120, 40), "white")

    def test_repeated_psm_votes_on_one_crop_do_not_count_as_independent(self):
        fake_tesseract = SimpleNamespace(image_to_string=lambda *args, **kwargs: "1234")
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}), \
                patch("app.roller_ocr.segment_digits", return_value=([], [])), \
                patch("app.roller_ocr.roller_register_variants", return_value=([self.image], [])), \
                patch("app.roller_ocr.build_ocr_variants", return_value=[self.image]):
            reading, _, flags = recognize(self.image, 4, self.image)
        self.assertIsNone(reading)
        self.assertIn("ROLLER_REVIEW_REQUIRED", flags)

    def test_distinct_display_crops_can_agree(self):
        fake_tesseract = SimpleNamespace(image_to_string=lambda *args, **kwargs: "1234")
        other_crop = Image.new("RGB", (100, 35), "white")
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}), \
                patch("app.roller_ocr.segment_digits", return_value=([], [])), \
                patch("app.roller_ocr.roller_register_variants", return_value=([self.image, other_crop], [])):
            reading, confidence, flags = recognize(self.image, 4, self.image)
        self.assertEqual(reading, "1234")
        self.assertGreater(confidence, 0)
        self.assertIn("RAW_DISPLAY_OCR_ENSEMBLE", flags)

    def test_single_digit_roi_votes_support_matching_whole_register(self):
        rois = [DigitROI(x * 20, 0, 12, 35) for x in range(4)]
        digits = iter(digit for digit in "1234" for _ in range(3))

        def read(image, **kwargs):
            return next(digits) if image.width == 10 else "1234"

        fake_tesseract = SimpleNamespace(image_to_string=read)
        small = Image.new("RGB", (10, 20), "white")
        with patch.dict(sys.modules, {"pytesseract": fake_tesseract}), \
                patch("app.roller_ocr.segment_digits", return_value=(rois, ["DIGIT_CONTOURS_SEGMENTED"])), \
                patch("app.roller_ocr.build_ocr_variants", side_effect=lambda image: [image] * 3), \
                patch("app.roller_ocr.crop_roi", return_value=small):
            reading, _, flags = recognize(self.image, 4)
        self.assertEqual(reading, "1234")
        self.assertIn("ROLLER_OCR_ENSEMBLE", flags)


if __name__ == "__main__":
    unittest.main()
