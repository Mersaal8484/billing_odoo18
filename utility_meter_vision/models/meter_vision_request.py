import base64
import json
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityMeterVisionRequest(models.Model):
    _name = 'utility.meter.vision.request'
    _description = 'طلب تحليل صورة عداد'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char('المرجع', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code(
                           'utility.meter.vision.request') or _('جديد'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'الشركة', required=True,
                                 default=lambda self: self.env.company, index=True)
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True,
                                 ondelete='set null', check_company=True)
    media_asset_id = fields.Many2one('utility.media.asset', 'أصل صورة العداد',
                                     index=True, ondelete='set null')
    attachment_id = fields.Many2one('ir.attachment', 'المرفق الأصلي',
                                    index=True, ondelete='set null')
    image_filename = fields.Char('اسم الصورة', compute='_compute_image_info')
    image_url = fields.Char('رابط الصورة', compute='_compute_image_info')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('queued', 'في الانتظار'),
        ('processing', 'قيد التحليل'),
        ('needs_review', 'تحتاج مراجعة'),
        ('approved', 'معتمدة'),
        ('rejected', 'مرفوضة'),
        ('failed', 'فشل التحليل'),
    ], string='الحالة', default='draft', required=True, tracking=True, index=True)
    provider_request_id = fields.Char('معرف الطلب لدى الخدمة', copy=False, index=True)
    model_name = fields.Char('النموذج المستخدم')
    model_version = fields.Char('إصدار النموذج')
    quality_state = fields.Selection([
        ('unknown', 'غير مقيمة'),
        ('good', 'جيدة'),
        ('review', 'تحتاج مراجعة'),
        ('poor', 'ضعيفة'),
    ], string='جودة الصورة', default='unknown')
    quality_score = fields.Float('درجة الجودة', digits=(5, 4))
    meter_number_candidate = fields.Char('رقم العداد المقترح')
    reading_candidate = fields.Float('القراءة المقترحة', digits=(16, 3))
    has_reading_candidate = fields.Boolean('توجد قراءة مقترحة', compute='_compute_has_candidate')
    confidence = fields.Float('الثقة', digits=(5, 4))
    raw_text = fields.Text('النص المستخرج')
    flags = fields.Text('تنبيهات التحليل')
    response_json = fields.Text('استجابة الخدمة الخام')
    error_message = fields.Text('رسالة الخطأ')
    reviewer_id = fields.Many2one('res.users', 'المراجع', readonly=True)
    reviewed_at = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    created_by = fields.Many2one('res.users', 'أنشأه', default=lambda self: self.env.user,
                                 readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        requests._check_image_source()
        return requests

    @api.depends('media_asset_id', 'attachment_id', 'reading_id')
    def _compute_image_info(self):
        for request in self:
            asset = request.media_asset_id
            attachment = (asset.original_attachment_id if asset else False) or request.attachment_id
            request.image_filename = (
                (asset.original_filename if asset else False)
                or (attachment.name if attachment else False)
                or 'meter-image'
            )
            request.image_url = (
                (asset.review_url if asset else False)
                or (asset.original_url if asset else False)
                or (f'/web/image/{attachment.id}' if attachment else False)
            ) or False

    @api.depends('reading_candidate', 'confidence')
    def _compute_has_candidate(self):
        for request in self:
            request.has_reading_candidate = bool(request.reading_candidate or request.confidence)

    @api.constrains('media_asset_id', 'attachment_id', 'reading_id')
    def _check_image_source(self):
        for request in self:
            has_asset_image = request.media_asset_id and request.media_asset_id.original_attachment_id
            has_attachment = request.attachment_id and request.attachment_id.datas
            has_reading_image = request.reading_id and (
                request.reading_id.image_asset_id or request.reading_id.attachment_id
            )
            if not (has_asset_image or has_attachment or has_reading_image):
                raise ValidationError(_('يجب ربط طلب التحليل بصورة عداد قابلة للقراءة.'))

    def _get_image_bytes(self):
        self.ensure_one()
        attachment = self.attachment_id
        if self.media_asset_id:
            attachment = self.media_asset_id.original_attachment_id or attachment
        if not attachment and self.reading_id:
            attachment = self.reading_id.attachment_id
            if not attachment and self.reading_id.image_asset_id:
                attachment = self.reading_id.image_asset_id.original_attachment_id
        if attachment and attachment.datas:
            return base64.b64decode(attachment.datas)
        if self.reading_id and self.reading_id.meter_image:
            return base64.b64decode(self.reading_id.meter_image)
        return b''

    @api.model
    def _service_config(self):
        params = self.env['ir.config_parameter'].sudo()
        return (
            (params.get_param('utility_meter_vision.service_url') or '').rstrip('/'),
            params.get_param('utility_meter_vision.service_token') or '',
            int(params.get_param('utility_meter_vision.timeout', '30') or 30),
        )

    def action_queue(self):
        for request in self:
            if request.state not in ('draft', 'failed', 'rejected'):
                continue
            if not request._get_image_bytes():
                raise UserError(_('تعذر قراءة صورة العداد قبل إرسال الطلب للتحليل.'))
            request.write({'state': 'queued', 'error_message': False, 'review_notes': False})
        return True

    def action_process(self):
        for request in self:
            request._process_one()
        return True

    def _process_one(self):
        self.ensure_one()
        if self.state not in ('queued', 'processing'):
            return False
        service_url, token, timeout = self._service_config()
        if not service_url:
            self.write({'state': 'failed', 'error_message': _(
                'لم يتم إعداد رابط meter-vision-service في إعدادات النظام.')})
            return False
        image_bytes = self._get_image_bytes()
        if not image_bytes:
            self.write({'state': 'failed', 'error_message': _('تعذر قراءة صورة العداد.')})
            return False
        self.write({'state': 'processing', 'error_message': False})
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        payload = {
            'request_id': self.name,
            'image_base64': base64.b64encode(image_bytes).decode('ascii'),
            'meter_id': self.reading_id.meter_id.display_name if self.reading_id and self.reading_id.meter_id else None,
            'language_hint': 'eng',
        }
        try:
            response = requests.post('%s/v1/inference' % service_url, json=payload,
                                     headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            _logger.warning('Meter vision request %s failed: %s', self.name, error)
            self.write({'state': 'failed', 'error_message': str(error)})
            return False
        self._apply_service_result(result)
        return True

    def _apply_service_result(self, result):
        self.ensure_one()
        reading = result.get('reading') or {}
        quality = result.get('quality') or {}
        candidate = reading.get('value')
        vals = {
            'state': 'needs_review',
            'provider_request_id': result.get('request_id') or self.name,
            'model_name': result.get('model') or 'meter-vision-service',
            'model_version': result.get('model_version'),
            'quality_state': quality.get('state') or 'unknown',
            'quality_score': quality.get('score') or 0.0,
            'confidence': reading.get('confidence') or 0.0,
            'meter_number_candidate': (result.get('meter_number') or {}).get('value'),
            'reading_candidate': float(candidate) if candidate not in (None, '') else 0.0,
            'raw_text': result.get('raw_text') or '',
            'flags': '\n'.join(str(flag) for flag in (result.get('flags') or [])),
            'response_json': json.dumps(result, ensure_ascii=False, indent=2),
            'error_message': False,
        }
        if result.get('state') == 'failed':
            vals['state'] = 'failed'
            vals['error_message'] = result.get('error_message') or _('فشلت الخدمة في تحليل الصورة.')
        self.write(vals)

    def action_approve(self):
        if not self.env.user.has_group('utility_meter_vision.group_meter_vision_reviewer'):
            raise AccessError(_('لا تملك صلاحية اعتماد نتيجة تحليل العداد.'))
        for request in self:
            if request.state != 'needs_review':
                raise UserError(_('لا يمكن اعتماد إلا الطلبات التي تحتاج مراجعة.'))
            if not request.has_reading_candidate:
                raise UserError(_('لا توجد قراءة مقترحة لاعتمادها.'))
            request.write({'state': 'approved', 'reviewer_id': self.env.user.id,
                           'reviewed_at': fields.Datetime.now()})
        return True

    def action_reject(self):
        for request in self:
            request.write({'state': 'rejected', 'reviewer_id': self.env.user.id,
                           'reviewed_at': fields.Datetime.now()})
        return True

    def action_retry(self):
        self.write({'state': 'queued', 'error_message': False})
        return True

    @api.model
    def _cron_process_queue(self):
        for request in self.search([('state', '=', 'queued')], limit=20):
            request._process_one()
        return True
