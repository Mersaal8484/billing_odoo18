import base64
import unittest
from io import BytesIO

from PIL import Image

from app.inference import analyze
from app.schemas import InferenceRequest


class TestInference(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
