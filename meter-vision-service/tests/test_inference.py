import base64
import unittest
from io import BytesIO

from PIL import Image

from app.inference import _apply_decimal_places, analyze
from app.schemas import DisplayBBox, InferenceRequest
from app.seven_segment_ocr import _classify
from app.digit_segmentation import segment_digits


class TestInference(unittest.TestCase):
    def test_decimal_places_formats_a_known_register_scale(self):
        self.assertEqual(_apply_decimal_places("281839", 1), "28183.9")
        self.assertEqual(_apply_decimal_places("25509", 0), "25509")
        self.assertIsNone(_apply_decimal_places(None, 1))

    def test_specialized_ocr_digit_patterns_are_explicit(self):
        for expected, pattern in (("5", "acdfg"), ("9", "abcdfg"), ("0", "abcdef")):
            value, confidence = _classify(set(pattern))
            self.assertEqual(value, expected)
            self.assertEqual(confidence, 1.0)

    def test_contour_segmentation_orders_digit_rois(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV optional dependency is unavailable")
        canvas = np.full((90, 330), 255, dtype=np.uint8)
        cv2.putText(canvas, "123456", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 3, cv2.LINE_AA)
        rois, flags = segment_digits(Image.fromarray(canvas), expected_digits=6)
        self.assertIn("DIGIT_CONTOURS_SEGMENTED", flags)
        self.assertEqual(len(rois), 6)
        self.assertEqual([roi.x for roi in rois], sorted(roi.x for roi in rois))
    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze(InferenceRequest(request_id="MVR/1", image_base64="not-base64"))

    def test_image_returns_reviewable_contract_without_auto_acceptance(self):
        output = BytesIO()
        Image.new("RGB", (320, 240), (100, 100, 100)).save(output, format="PNG")
        request = InferenceRequest(
            request_id="MVR/2",
            image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
        )
        result = analyze(request)
        self.assertEqual(result.request_id, "MVR/2")
        self.assertIn(result.state, ("completed", "needs_review"))
        self.assertGreaterEqual(result.quality.score, 0.0)
        self.assertFalse(result.auto_approval_eligible)
        self.assertTrue(result.stages)

    def test_thumbnail_is_upscaled_but_marked_low_resolution(self):
        output = BytesIO()
        Image.new("RGB", (250, 250), (100, 100, 100)).save(output, format="PNG")
        result = analyze(InferenceRequest(
            request_id="MVR/thumbnail",
            image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
        ))
        self.assertTrue(result.quality.low_resolution)
        self.assertEqual(result.quality.source_width, 250)
        self.assertIn("LOW_SOURCE_RESOLUTION_UPSCALED", result.flags)

    def test_full_photo_requires_a_confirmed_display_crop(self):
        output = BytesIO()
        Image.new("RGB", (900, 700), (100, 100, 100)).save(output, format="PNG")
        result = analyze(InferenceRequest(
            request_id="MVR/no-crop",
            image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
        ))
        self.assertIn("DISPLAY_CROP_REQUIRED", result.flags)
        self.assertFalse(result.auto_approval_eligible)

    def test_display_crop_is_accepted_in_original_image_coordinates(self):
        output = BytesIO()
        Image.new("RGB", (900, 700), (100, 100, 100)).save(output, format="PNG")
        result = analyze(InferenceRequest(
            request_id="MVR/crop",
            image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
            display_bbox=DisplayBBox(x=100, y=120, w=500, h=160),
        ))
        self.assertNotIn("DISPLAY_CROP_REQUIRED", result.flags)
        self.assertFalse(result.auto_approval_eligible)

    def test_perspective_quad_is_supported_and_reported(self):
        output = BytesIO()
        Image.new("RGB", (900, 700), (100, 100, 100)).save(output, format="PNG")
        result = analyze(InferenceRequest(
            request_id="MVR/quad",
            image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
            display_quad=[100, 120, 600, 130, 590, 280, 110, 270],
            meter_type_hint="mechanical_roller",
        ))
        self.assertIn("PERSPECTIVE_CORRECTED", result.preprocessing)
        self.assertNotIn("DISPLAY_CROP_REQUIRED", result.flags)

    def test_bbox_and_quad_cannot_be_combined(self):
        output = BytesIO()
        Image.new("RGB", (900, 700), (100, 100, 100)).save(output, format="PNG")
        with self.assertRaises(ValueError):
            analyze(InferenceRequest(
                request_id="MVR/conflicting-crops",
                image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
                display_bbox=DisplayBBox(x=100, y=120, w=500, h=160),
                display_quad=[100, 120, 600, 130, 590, 280, 110, 270],
            ))


if __name__ == "__main__":
    unittest.main()
