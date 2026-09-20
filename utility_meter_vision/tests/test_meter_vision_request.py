import base64

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestMeterVisionRequest(TransactionCase):
    def test_request_lifecycle_stays_separate_from_reading(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'meter.png',
            'mimetype': 'image/png',
            'datas': base64.b64encode(b'not-a-real-image'),
        })
        request = self.env['utility.meter.vision.request'].create({
            'attachment_id': attachment.id,
        })
        request.action_queue()
        self.assertEqual(request.state, 'queued')
        request._apply_service_result({
            'request_id': request.name,
            'state': 'needs_review',
            'model': 'test-model',
            'model_version': 'test',
            'quality': {'state': 'review', 'score': 0.7},
            'reading': {'value': '12345.6', 'confidence': 0.8},
            'flags': ['MANUAL_REVIEW'],
        })
        self.assertEqual(request.state, 'needs_review')
        self.assertEqual(request.reading_candidate, 12345.6)
        request.action_approve()
        self.assertEqual(request.state, 'approved')

    def test_image_source_is_required(self):
        with self.assertRaises(ValidationError):
            self.env['utility.meter.vision.request'].create({'company_id': self.env.company.id})
