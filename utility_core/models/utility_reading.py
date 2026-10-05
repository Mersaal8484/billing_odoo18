import base64
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


# Object identity cannot be reproduced by a JSON/RPC context value. Only the
# server-side approval action may authorize its audited transition.
_APPROVAL_ACTION_TOKEN = object()


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'قراءة عداد'
    _rec_name = 'reading_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utility.dropdown.mixin']
    _order = 'reading_date desc'


    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    reading_id = fields.Char('رقم القراءة', default=lambda self: _('جديد'), readonly=True)
    meter_serial_scan = fields.Char('مسح العداد (باركود)', store=False, help="استخدم الكاميرا لمسح رقم العداد وجلبه تلقائياً")
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    account_id = fields.Many2one(
        'utility.customer', 'الحساب', index=True,
        check_company=True, ondelete='restrict',
        help='حساب المشترك المثبت تاريخياً وقت إنشاء القراءة.')
    customer_id = fields.Many2one(
        'utility.customer', 'العميل/العقد', related='account_id',
        store=True, index=True, readonly=True)
    reading_date = fields.Datetime('تاريخ القراءة', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('قيمة القراءة', required=True)
    raw_consumption = fields.Float('الاستهلاك الخام', compute='_compute_consumption', store=True)
    consumption = fields.Float('الاستهلاك', compute='_compute_consumption', store=True)
    meter_multiplier = fields.Float('معامل الضرب وقت القراءة', default=1.0, required=True)
    is_rollover = fields.Boolean('تدوير العداد (Rollover)', default=False, tracking=True,
                                 help='يُحدد إذا تجاوز العداد الحد الأقصى وبدأ الدورة من الصفر مجدداً')
    max_reading_value = fields.Float('الحد الأقصى للعداد وقت التدوير', default=99999.0)
    reading_purpose = fields.Selection([
        ('opening', 'افتتاحية'),
        ('periodic', 'دورية'),
        ('closing', 'ختامية'),
        ('replacement_closing', 'ختامية استبدال (توافقي)'),
    ], string='غرض القراءة', default='periodic', required=True, index=True, tracking=True)
    reading_event = fields.Selection([
        ('normal', 'عادية / دورية'),
        ('installation', 'تركيب عداد جديد'),
        ('replacement', 'استبدال عداد'),
        ('disconnection', 'فصل الخدمة'),
        ('removal', 'إزالة عداد'),
        ('contract_closure', 'إنهاء عقد / اشتراك'),
    ], string='حدث القراءة', default='normal', required=True, index=True, tracking=True)
    reading_category = fields.Selection([
        ('customer', 'مشترك'),
        ('transformer', 'محول / خلية'),
        ('feeder', 'فيدر'),
    ], string='تصنيف القراءة', default='customer', required=True)
    transformer_id = fields.Many2one('utility.transformer', 'المحول', related='meter_id.transformer_id', store=True)
    transformer_snapshot_id = fields.Many2one('utility.transformer', 'المحول الفعلي (بصمة)', copy=False, index=True,
                                              help="بصمة تاريخية ثابتة للمحول وقت أخذ القراءة. لا تتغير إذا نقل المشترك لمحول آخر لاحقاً.")
    is_private_transformer = fields.Boolean('محول خاص', related='transformer_id.is_private', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر', related='meter_id.feeder_id', store=True)

    reading_type = fields.Selection([
        ('manual', 'يدوي'),
        ('estimated', 'تقديري'),
        ('ami', 'قراءة تلقائية (AMI)'),
    ], string='طريقة أخذ القراءة', default='manual')
    is_estimated = fields.Boolean('تقديرية', default=False)
    is_initial_reading = fields.Boolean('قراءة افتتاحية', default=False)
    replacement_id = fields.Many2one('utility.meter.replacement', 'عملية الاستبدال', index=True, check_company=True, ondelete='restrict')
    image_asset_id = fields.Many2one('utility.media.asset', string='Meter Image Asset', ondelete='set null', index=True)
    meter_image = fields.Binary('صورة العداد (توافقي)', compute='_compute_meter_image', inverse='_inverse_meter_image', store=False,
                                help='حقل توافقي غير مخزن — التخزين الأصيل ممركز في image_asset_id')
    meter_image_url = fields.Char('رابط صورة العداد', compute='_compute_meter_image_url', store=False, compute_sudo=True)
    meter_image_upload = fields.Binary('رفع صورة العداد', attachment=True)
    meter_image_filename = fields.Char('اسم ملف الصورة', compute='_compute_meter_image_filename', store=False)
    meter_image_secondary = fields.Binary('صورة إضافية', attachment=True)
    image_state = fields.Selection([
        ('clear', 'واضحة'),
        ('not_clear', 'غير واضحة'),
        ('not_same', 'لا تطابق العداد'),
        ('none', 'بدون صورة'),
        ('pending', 'بانتظار مراجعة الصورة'),
        ('replace', 'عداد مركب حديثاً'),
        ('loss_read', 'قراءة مفقودة'),
    ], string='حالة الصورة', default='none',
        help='حالة فحص الصورة من قبل المراجع')
    attachment_id = fields.Many2one('ir.attachment', string='ملف المرفق الرسمي')
    reviewer_id = fields.Many2one('res.users', 'المراجع',
        readonly=True, tracking=True)
    review_date = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    rejection_reason = fields.Text('سبب الرفض', tracking=True, copy=False)
    rejected_by = fields.Many2one('res.users', 'المستخدم الرافض', readonly=True, copy=False)
    rejected_at = fields.Datetime('تاريخ الرفض', readonly=True, copy=False)
    is_validated = fields.Boolean('تم التحقق', default=False)
    validator_id = fields.Many2one('res.users', 'المُتحقّق')
    previous_reading = fields.Float('القراءة السابقة', compute='_compute_previous_reading', store=True, readonly=False)
    previous_reading_date = fields.Datetime('تاريخ القراءة السابقة', compute='_compute_previous_reading', store=True, readonly=False)
    consumption_difference = fields.Float('فرق الاستهلاك',
        compute='_compute_consumption_analysis', store=True)
    consumption_diff_percentage = fields.Float('نسبة الفرق %',
        compute='_compute_consumption_analysis', store=True)
    consumption_alert = fields.Selection([
        ('normal', 'طبيعي'),
        ('high', 'مرتفع'),
        ('negative', 'سلبي'),
        ('zero', 'صفر'),
    ], compute='_compute_consumption_analysis', store=True, string='حالة الاستهلاك')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('under_review', 'قيد المراجعة'),
        ('approved', 'معتمدة'),
        ('queued', 'في طابور الفوترة'),
        ('billed', 'مفوترة'),
        ('error', 'خطأ'),
    ], string='الحالة', default='draft', tracking=True, index=True)
    available_open_reading_period_ids = fields.Many2many('date.range', compute='_compute_available_open_reading_period_ids')
    available_meter_ids = fields.Many2many(
        'utility.meter', compute='_compute_available_meter_ids',
        string='العدادات المتوافقة')
    date_range_id = fields.Many2one('date.range', string="الفترة", index=True)
    remarks = fields.Text('ملاحظات')
    reading_source = fields.Char('مصدر القراءة')

    @api.onchange('reading_type')
    def _onchange_reading_type(self):
        if self.reading_type == 'estimated':
            self.is_estimated = True
        elif self.reading_type in ('manual', 'ami'):
            self.is_estimated = False

    @api.onchange('is_estimated')
    def _onchange_is_estimated(self):
        if self.is_estimated and self.reading_type != 'estimated':
            self.reading_type = 'estimated'
        elif not self.is_estimated and self.reading_type == 'estimated':
            self.reading_type = 'manual'

    @api.model
    def _decode_image_payload(self, raw):
        """Safely decode image payload from base64 string, data-uri, or bytes."""
        if not raw:
            return b''
        if isinstance(raw, str):
            if ',' in raw and raw.startswith('data:'):
                raw = raw.split(',', 1)[1]
            try:
                return base64.b64decode(raw, validate=False)
            except Exception:
                return b''
        if isinstance(raw, (bytes, bytearray)):
            raw_bytes = bytes(raw)
            if (raw_bytes.startswith(b'\xff\xd8') or
                raw_bytes.startswith(b'\x89PNG') or
                raw_bytes.startswith(b'GIF') or
                raw_bytes.startswith(b'RIFF') or
                raw_bytes.startswith(b'BM')):
                return raw_bytes
            try:
                decoded = base64.b64decode(raw_bytes, validate=False)
                return decoded
            except Exception:
                return raw_bytes
        return b''

    def _store_reading_image(self, raw_data, filename=None):
        """Helper to store image data into canonical utility.media.asset and link it."""
        raw_bytes = self._decode_image_payload(raw_data)
        if not raw_bytes:
            return False
        old_asset = self.image_asset_id if len(self) == 1 else False
        real_id = False
        if len(self) == 1:
            if isinstance(self.id, int):
                real_id = self.id
            elif hasattr(self, '_origin') and self._origin and isinstance(self._origin.id, int):
                real_id = self._origin.id
        target_filename = filename or (f"reading_{real_id or 'new'}.jpg")
        new_asset = self.env['utility.media.service'].sudo().store_media(
            file_data=raw_bytes,
            filename=target_filename,
            mimetype='image/jpeg',
            reading_id=real_id,
            asset_type='meter_reading'
        )
        if old_asset and old_asset != new_asset:
            new_asset.sudo().write({'revision': (old_asset.revision or 1) + 1})
        if new_asset and new_asset.original_attachment_id and len(self) == 1 and real_id:
            self.sudo().with_context(_bypass_reading_protection=True).write({
                'attachment_id': new_asset.original_attachment_id.id,
            })
        return new_asset

    @api.onchange('meter_image_upload')
    def _onchange_meter_image_upload(self):
        if not self.meter_image_upload:
            return
        reading_origin = self._origin if getattr(self, '_origin', False) else self
        target_id = reading_origin.id if (reading_origin and isinstance(reading_origin.id, int)) else (self.id if isinstance(self.id, int) else False)
        new_asset = reading_origin._store_reading_image(
            self.meter_image_upload,
            filename=self.meter_image_filename or (f"reading_{target_id}.jpg" if target_id else "reading_new.jpg")
        )
        if new_asset:
            self.image_asset_id = new_asset.id
            if new_asset.original_attachment_id:
                self.attachment_id = new_asset.original_attachment_id.id
            self.meter_image_upload = False
            self.meter_image_url = (
                (f"/web/image/{new_asset.original_attachment_id.id}" if new_asset.original_attachment_id else False)
                or new_asset.review_url
                or new_asset.original_url
                or (f"/utility/media/{new_asset.asset_uuid}/original" if new_asset.asset_uuid else '')
            )
            if self.image_state == 'none':
                self.image_state = 'pending'
            if target_id:
                reading_origin.sudo().with_context(_bypass_reading_protection=True).write({
                    'image_asset_id': new_asset.id,
                    'attachment_id': new_asset.original_attachment_id.id if new_asset.original_attachment_id else False,
                    'meter_image_upload': False,
                    'image_state': self.image_state,
                })

    @api.depends('image_asset_id', 'image_asset_id.state', 'attachment_id')
    def _compute_meter_image(self):
        MediaService = self.env['utility.media.service']
        for r in self:
            r.meter_image = False
            if r.image_asset_id and r.image_asset_id.state == 'ready':
                raw = MediaService.sudo().retrieve_media(r.image_asset_id.sudo(), variant='review')
                if raw:
                    r.meter_image = base64.b64encode(raw)
                    continue
            if r.attachment_id and r.attachment_id.datas:
                r.meter_image = r.attachment_id.datas

    @api.depends('image_asset_id', 'image_asset_id.state', 'image_asset_id.review_url', 'attachment_id', 'meter_image_upload')
    def _compute_meter_image_url(self):
        for r in self:
            attachment = r.attachment_id.sudo() if r.attachment_id else (
                r.image_asset_id.original_attachment_id.sudo() if r.image_asset_id and r.image_asset_id.original_attachment_id else False
            )
            if attachment:
                r.meter_image_url = f"/web/image/{attachment.id}"
            elif r.image_asset_id and r.image_asset_id.sudo().asset_uuid:
                r.meter_image_url = f"/utility/media/{r.image_asset_id.sudo().asset_uuid}/original"
            elif r.meter_image_upload and isinstance(r.id, int):
                r.meter_image_url = f"/web/image?model=utility.reading&id={r.id}&field=meter_image_upload"
            else:
                r.meter_image_url = ''

    def _compute_meter_image_filename(self):
        for r in self:
            r.meter_image_filename = f"reading_{r.id or 'new'}.jpg"

    def _inverse_meter_image(self):
        for r in self:
            if not r.meter_image:
                continue
            new_asset = r._store_reading_image(
                r.meter_image,
                filename=f"reading_{r.id or 'legacy'}.jpg"
            )
            if new_asset:
                write_vals = {
                    'image_asset_id': new_asset.id,
                    'image_state': 'pending' if r.image_state == 'none' else r.image_state,
                }
                if new_asset.original_attachment_id:
                    write_vals['attachment_id'] = new_asset.original_attachment_id.id
                r.with_context(_bypass_reading_protection=True).write(write_vals)

    def action_save_image(self):
        """حفظ الصورة وإغلاق النافذة المنبثقة."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    def _requires_billing_review(self):
        """Return whether commercial validation rules apply to the reading.

        Core deliberately returns ``False``.  The billing module overrides this
        hook after it installs its commercial fields and rules.
        """
        self.ensure_one()
        return False

    def init(self):
        """Backfill stable accounts and legacy opening-reading purposes on upgrade."""
        self.env.flush_all()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_meter_date_idx
            ON utility_reading (meter_id, reading_date DESC)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_review_state_image_date_idx
            ON utility_reading (state, image_state, reading_date DESC, id DESC)
        """)
        self.env.cr.execute("""
            UPDATE utility_reading AS reading
               SET image_state = CASE
                   WHEN reading.state IN ('approved', 'queued', 'billed')
                   THEN 'clear'
                   ELSE 'pending'
               END
              FROM utility_media_asset AS asset
             WHERE reading.image_asset_id = asset.id
               AND reading.image_state = 'none'
               AND asset.state NOT IN ('deleted', 'failed')
        """)
        self.env.cr.execute("""
            UPDATE utility_reading reading
               SET account_id = meter.customer_id
              FROM utility_meter meter
             WHERE reading.meter_id = meter.id
               AND reading.account_id IS NULL
               AND meter.customer_id IS NOT NULL
        """)
        self.env.cr.execute("""
            UPDATE utility_reading
               SET reading_purpose = 'opening'
              WHERE is_initial_reading = TRUE
                AND reading_purpose != 'opening'
        """)

    @api.onchange('meter_serial_scan')
    def _onchange_meter_serial_scan(self):
        if self.meter_serial_scan:
            meter = self.env['utility.meter'].search([
                ('meter_number', '=', self.meter_serial_scan)
            ], limit=1)
            
            if not meter:
                meter = self.env['utility.meter'].search(
                    self.env['utility.meter']._scan_domain(self.meter_serial_scan),
                    limit=1)

            if meter:
                self.meter_id = meter.id
                self.meter_serial_scan = False
                return {
                    'warning': {
                        'title': _('نجاح'),
                        'message': _('تم العثور على العداد (%s) بنجاح.') % meter.display_name,
                        'type': 'notification',
                    }
                }
            else:
                return {
                    'warning': {
                        'title': _('غير موجود'),
                        'message': _('لم يتم العثور على عداد يحمل الرقم: %s') % self.meter_serial_scan,
                    }
                }

    @api.onchange('meter_id')
    def _onchange_meter_account(self):
        """Snapshot the account and multiplier selected with the meter."""
        if self.meter_id:
            self.account_id = (
                self.meter_id.customer_id
                or self.meter_id.linked_private_transformer_id.private_customer_id
            )
            self.meter_multiplier = self.meter_id.multiplier or 1.0

    @api.onchange('reading_purpose')
    def _onchange_reading_purpose(self):
        if self.reading_purpose != 'periodic':
            self.date_range_id = False
        else:
            if not self.date_range_id and self.available_open_reading_period_ids:
                self.date_range_id = self.available_open_reading_period_ids[0].id
        self.is_initial_reading = self.reading_purpose == 'opening'

    @api.onchange('reading_category')
    def _onchange_reading_category(self):
        if self.reading_category == 'customer':
            self.transformer_id = False
            self.feeder_id = False
        elif self.reading_category == 'transformer':
            self.feeder_id = False
        elif self.reading_category == 'feeder':
            self.transformer_id = False
        self.meter_id = False
        return self._get_meter_domain()

    def _get_meter_domain(self):
        category_to_connection = {
            'customer': ['subscriber', 'private_transformer'],
            'transformer': ['transformer'],
            'feeder': ['feeder'],
        }
        connection_types = category_to_connection.get(self.reading_category, [])
        if connection_types:
            return {'domain': {'meter_id': [('connection_type', 'in', connection_types)]}}
        return {'domain': {'meter_id': []}}

    @api.depends('reading_category', 'account_id')
    def _compute_available_meter_ids(self):
        Meter = self.env['utility.meter']
        meters_by_category = {
            'customer': Meter.search([('connection_type', 'in', ['subscriber', 'private_transformer'])]),
            'transformer': Meter.search([('connection_type', '=', 'transformer')]),
            'feeder': Meter.search([('connection_type', '=', 'feeder')]),
        }
        for reading in self:
            meters = meters_by_category.get(reading.reading_category, Meter.browse())
            if reading.reading_category == 'customer' and reading.account_id:
                meters = meters.filtered(
                    lambda meter: meter.customer_id == reading.account_id
                    or meter.linked_private_transformer_id.private_customer_id == reading.account_id)
            reading.available_meter_ids = meters

    @api.constrains('meter_id', 'account_id', 'reading_category')
    def _check_meter_subject_consistency(self):
        """A reading subject is derived from its meter, never entered independently."""
        expected_connections = {
            'customer': ('subscriber', 'private_transformer'),
            'transformer': ('transformer',),
            'feeder': ('feeder',),
        }
        for reading in self:
            meter = reading.meter_id
            if not meter:
                continue
            if meter.connection_type not in expected_connections.get(
                    reading.reading_category, ()):
                raise ValidationError(_(
                    'تصنيف القراءة لا يطابق نوع ربط العداد المختار.'
                ))
            if meter.connection_type == 'subscriber':
                if meter.customer_id and reading.account_id != meter.customer_id:
                    raise ValidationError(_(
                        'حساب القراءة يجب أن يطابق المشترك المرتبط بالعداد.'
                    ))
            elif meter.connection_type == 'private_transformer':
                owner = meter.linked_private_transformer_id.private_customer_id
                if owner and reading.account_id != owner:
                    raise ValidationError(_(
                        'حساب قراءة المحول الخاص يجب أن يطابق مالك المحول.'
                    ))
            elif reading.account_id:
                raise ValidationError(_(
                    'قراءات المحولات والفيدرات العامة لا ترتبط بحساب مشترك.'
                ))

    reading_history_count = fields.Integer('عدد القراءات السابقة', compute='_compute_reading_history_count')

    @api.depends('meter_id')
    def _compute_reading_history_count(self):
        for r in self:
            if r.meter_id:
                domain = [('meter_id', '=', r.meter_id.id)]
                if r.id and isinstance(r.id, int):
                    domain.append(('id', '!=', r.id))
                r.reading_history_count = self.search_count(domain)
            else:
                r.reading_history_count = 0

    def action_view_reading_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجل القراءات - %s') % self.meter_id.meter_number,
            'res_model': 'utility.reading',
            'view_mode': 'list,form',
            'domain': [('meter_id', '=', self.meter_id.id), ('id', '!=', self.id)],
            'context': {'create': False},
        }

    def action_open_meter_images(self):
        """Open the current reading in a modal image form bound to this record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('صورة العداد'),
            'res_model': 'utility.reading',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('utility_billing.view_utility_reading_images').id, 'form')],
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit', 'create': False, 'edit': True},
        }

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    STATE_EDITABLE = {
        'draft': {'meter_id', 'reading_date', 'reading_value', 'reading_category',
                  'reading_type', 'reading_purpose', 'reading_event', 'account_id', 'meter_multiplier',
                  'is_estimated', 'is_initial_reading', 'is_rollover', 'max_reading_value',
                  'replacement_id', 'meter_image', 'image_asset_id', 'meter_image_secondary',
                  'meter_image_upload', 'meter_image_filename',
                  'image_state', 'rejection_reason', 'remarks', 'date_range_id',
                  'reading_source', 'active', 'is_validated', 'validator_id',
                  'reviewer_id', 'review_date', 'rejected_by', 'rejected_at'},
        'under_review': {'meter_image', 'image_asset_id', 'meter_image_secondary', 'image_state',
                          'meter_image_upload', 'meter_image_filename',
                          'review_notes', 'rejection_reason', 'rejected_by', 'rejected_at',
                          'is_validated', 'validator_id', 'reviewer_id', 'review_date', 'remarks', 'active'},
        'approved': {'rejection_reason', 'rejected_by', 'rejected_at', 'active', 'attachment_id',
                     'billing_error', 'remarks'},
        'queued': {'attachment_id', 'billing_error', 'remarks', 'active'},
        'billed': {'active', 'remarks', 'billing_error'},
        'error': {'reading_date', 'reading_value', 'meter_image', 'image_asset_id', 'meter_image_secondary',
                  'meter_image_upload', 'meter_image_filename',
                  'is_rollover', 'max_reading_value',
                  'image_state', 'remarks', 'date_range_id', 'billing_error', 'active'},
    }

    @api.constrains('reading_purpose', 'date_range_id', 'replacement_id', 'account_id', 'reading_date')
    def _check_reading_purpose_rules(self):
        """Enforce period, replacement, and billing-anchor invariants."""
        for reading in self:
            if reading.reading_purpose != 'periodic' and reading.date_range_id:
                raise ValidationError(_('الفترة مسموحة للقراءة الدورية فقط.'))
            if reading.reading_purpose == 'replacement_closing' and not reading.replacement_id:
                raise ValidationError(_('القراءة الختامية تتطلب عملية استبدال مرتبطة.'))

    @api.constrains('is_rollover', 'max_reading_value', 'reading_value', 'previous_reading')
    def _check_rollover_integrity(self):
        for r in self:
            if r.is_rollover:
                if r.max_reading_value <= 0:
                    raise ValidationError(_('الحد الأقصى للعداد وقت التدوير يجب أن يكون قيمة موجبة أكبر من الصفر.'))
                if r.reading_value > r.max_reading_value:
                    raise ValidationError(_(
                        'قيمة القراءة الحالية (%.2f) لا يمكن أن تتجاوز الحد الأقصى للعداد (%.2f).'
                    ) % (r.reading_value, r.max_reading_value))
                if (r.previous_reading or 0.0) > r.max_reading_value:
                    raise ValidationError(_(
                        'قيمة القراءة السابقة (%.2f) تتجاوز الحد الأقصى للعداد (%.2f).'
                    ) % (r.previous_reading or 0.0, r.max_reading_value))
                if r.reading_value >= (r.previous_reading or 0.0):
                    raise ValidationError(_(
                        'لا يمكن تفعيل خيار تدوير العداد إذا كانت القراءة الحالية (%.2f) أكبر من أو تساوي القراءة السابقة (%.2f).'
                    ) % (r.reading_value, r.previous_reading or 0.0))
                if r.consumption <= 0:
                    raise ValidationError(_('الاستهلاك المحسوب من تدوير العداد يجب أن يكون أكبر من الصفر.'))

    @api.depends('account_id.contract_template_id.recurring_rule_type', 'account_id.area_id.recurring_rule_type', 'account_id.region_id.recurring_rule_type')
    def _compute_available_open_reading_period_ids(self):
        for reading in self:
            account = reading.account_id
            billing_period = account._get_effective_billing_period() if account else False
            domain = self._get_open_period_domain(
                work_type='readings', billing_period=billing_period)
            reading.available_open_reading_period_ids = self.env['date.range'].search(domain)

    @api.onchange('account_id', 'meter_id', 'reading_purpose')
    def _onchange_account_id_date_range(self):
        available_periods = self.available_open_reading_period_ids
        if self.date_range_id and self.date_range_id not in available_periods:
            self.date_range_id = False
        if self.reading_purpose == 'periodic' and not self.date_range_id and available_periods:
            self.date_range_id = available_periods[0].id
        return {'domain': {'date_range_id': [('id', 'in', available_periods.ids)]}}

    @api.depends('reading_value', 'previous_reading', 'is_initial_reading', 'reading_purpose', 'meter_multiplier', 'is_rollover', 'max_reading_value')
    def _compute_consumption(self):
        for r in self:
            if r.is_initial_reading or r.reading_purpose == 'opening':
                r.raw_consumption = 0.0
                r.consumption = 0.0
            else:
                prev = r.previous_reading or 0.0
                curr = r.reading_value or 0.0
                if r.is_rollover and curr < prev:
                    max_val = r.max_reading_value if r.max_reading_value > 0 else 99999.0
                    raw = (max_val - prev + 1.0) + curr
                else:
                    raw = curr - prev
                r.raw_consumption = raw
                r.consumption = raw * (r.meter_multiplier or 1.0)

    @api.depends('consumption', 'meter_id', 'reading_purpose')
    def _compute_consumption_analysis(self):
        meters = self.mapped('meter_id')
        approved_map = {}
        if meters:
            approved_readings = self.search([
                ('meter_id', 'in', meters.ids),
                ('state', '=', 'approved'),
                ('id', 'not in', self.ids),
            ], order='reading_date desc')
            for a in approved_readings:
                approved_map.setdefault(a.meter_id.id, []).append(a)

        for r in self:
            # Opening readings: zero consumption is EXPECTED, never flag
            if r.reading_purpose == 'opening':
                r.consumption_alert = 'normal'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue

            if r.consumption <= 0:
                r.consumption_alert = 'zero' if r.consumption == 0 else 'negative'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue
            candidates = approved_map.get(r.meter_id.id, [])
            last_approved = candidates[0] if candidates else False
            if last_approved and last_approved.consumption > 0:
                diff = r.consumption - last_approved.consumption
                r.consumption_difference = diff
                r.consumption_diff_percentage = (diff / last_approved.consumption) * 100
                r.consumption_alert = 'high' if abs(r.consumption_diff_percentage) > 50 else 'normal'
            else:
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                r.consumption_alert = 'normal'

    @api.depends('meter_id', 'reading_date', 'reading_purpose', 'replacement_id', 'account_id')
    def _compute_previous_reading(self):
        meters = self.mapped('meter_id')
        prev_map = {}
        if meters:
            all_prev = self.search([
                ('meter_id', 'in', meters.ids),
                ('state', 'in', ['approved', 'billed']),
            ], order='meter_id, reading_date desc')
            for p in all_prev:
                prev_map.setdefault(p.meter_id.id, []).append(p)

        for r in self:
            candidates = prev_map.get(r.meter_id.id, [])
            found = False
            for p in candidates:
                if p.reading_date < r.reading_date and p.id != r.id:
                    r.previous_reading = p._get_effective_previous_reading()
                    r.previous_reading_date = p.reading_date
                    found = True
                    break
            if not found:
                if r.reading_purpose == 'replacement_closing' and r.replacement_id and r.replacement_id.old_last_invo_reading:
                    r.previous_reading = r.replacement_id.old_last_invo_reading
                elif r.account_id and (r.account_id.last_invoice_reading or r.account_id.last_reading_value):
                    r.previous_reading = r.account_id.last_invoice_reading or r.account_id.last_reading_value or 0.0
                elif not r.previous_reading:
                    r.previous_reading = 0.0
                if not r.previous_reading_date:
                    r.previous_reading_date = False

    def _get_effective_previous_reading(self):
        """Return the effective previous reading value for the NEXT reading's consumption calculation.

        The historical ``reading_value`` is preserved immutably forever.
        If a technically-approved (or processed) correction exists for this
        reading, the ``corrected_reading_value`` is used as the operational
        baseline for the subsequent reading — without mutating any stored data.

        This is the canonical resolver used by downstream consumption
        calculations. Never use ``reading_value`` directly when computing
        consumption for the reading that *follows* this one.

        Returns:
            float: The corrected reading value if an approved settlement exists,
                   otherwise the immutable historical reading_value.
        """
        self.ensure_one()
        # Avoid circular import: use model name string, not import
        Settlement = self.env.get('utility.reading.settlement')
        if Settlement is not None:
            approved = Settlement.search([
                ('reading_id', '=', self.id),
                ('state', 'in', ('technically_approved', 'processed')),
            ], limit=1, order='approved_date desc')
            if approved:
                return approved.corrected_reading_value
        return self.reading_value


    def action_submit_review(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError('يمكن إرسال القراءات المسودة فقط للمراجعة!')

            if not r.meter_image and r._requires_billing_review():
                raise ValidationError('يجب رفع صورة العداد قبل إرسال القراءة للمراجعة!')

            r.with_context(_reading_state_transition=True).write({
                'reading_source': r.reading_source or f'manual_{fields.Datetime.now()}',
                'state': 'under_review',
            })

    def _check_approval_access(self):
        if not (self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية اعتماد قراءات العدادات. يتطلب صلاحية مشرف أو مدير فوترة أو مدير إيرادات.'))

    def action_approve(self):
        self._check_approval_access()

        for r in self:
            if r.state not in ('under_review', 'approved', 'queued'):
                raise ValidationError('يمكن الموافقة على القراءات قيد المراجعة فقط!')

            if r._requires_billing_review() and r.image_state != 'clear':
                raise ValidationError(
                    'لا يمكن اعتماد القراءة قبل اعتماد الصورة كصورة واضحة (clear).'
                )

            # FIX-4: منع اعتماد قراءة باستهلاك سالب للقراءات القابلة للفوترة
            if r._requires_billing_review() and r.consumption < 0:
                raise ValidationError(
                    'لا يمكن اعتماد قراءة باستهلاك سالب (%.2f). '
                    'تحقق من صحة القراءة أو أنشئ تسوية.'
                    % r.consumption
                )

            r.with_context(
                _reading_state_transition=True,
                _internal_approval_action=_APPROVAL_ACTION_TOKEN,
            ).write({
                'state': 'approved',
                'is_validated': True,
                'validator_id': self.env.user.id,
                'reviewer_id': self.env.user.id,
                'review_date': fields.Datetime.now(),
            })

            # FIX-3: تحديث آخر قراءة على الحساب عند الاعتماد
            if r.account_id:
                current_last = r.account_id.last_reading_date
                if not current_last or r.reading_date > current_last:
                    r.account_id.sudo().write({
                        'last_reading_date': r.reading_date,
                        'last_reading_value': r.reading_value,
                    })
            # تحديث آخر قراءة في العداد
            if r.meter_id:
                r.meter_id._update_last_reading()

    def action_reject(self):
        if not (self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية رفض قراءات العدادات. يتطلب صلاحية مشرف أو مدير فوترة أو مدير إيرادات.'))

        for r in self:
            # FIX-1: منع رفض قراءة مفوترة — يجب إلغاء الفاتورة أولاً أو استخدام تسوية
            if r.state == 'billed':
                raise ValidationError(_(
                    'لا يمكن رفض قراءة مفوترة مباشرةً.\n'
                    'قم بإلغاء الفاتورة المرتبطة أولاً، '
                    'أو استخدم نموذج تسوية القراءات لتعديل القيمة.'
                ))
            if r.state not in ('under_review', 'approved'):
                raise ValidationError(_('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!'))

            reason = r.rejection_reason or self.env.context.get('default_rejection_reason')
            if not reason or not reason.strip():
                raise ValidationError(_('يجب تحديد سبب رفض القراءة لتوجيه القارئ الميداني للتصحيح.'))

            r.with_context(_reading_state_transition=True).write({
                'state': 'draft',
                'rejection_reason': reason.strip(),
                'rejected_by': self.env.user.id,
                'rejected_at': fields.Datetime.now(),
                'is_validated': False,
                'validator_id': False,
                'reviewer_id': False,
                'review_date': False,
            })

    def _check_review_access(self):
        if not (self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.user.has_group('utility_core.group_utility_auditor')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية مراجعة صور وقراءات العدادات.'))

    def action_mark_image_clear(self):
        self._check_review_access()
        for r in self:
            r.with_context(_bypass_reading_protection=True).write({'image_state': 'clear'})

    def action_mark_image_not_clear(self):
        self._check_review_access()
        for r in self:
            r.with_context(_bypass_reading_protection=True).write({'image_state': 'not_clear'})

    def action_mark_image_not_same(self):
        self._check_review_access()
        for r in self:
            r.with_context(_bypass_reading_protection=True).write({'image_state': 'not_same'})

    def action_mark_image_loss_read(self):
        self._check_review_access()
        for r in self:
            r.with_context(_bypass_reading_protection=True).write({'image_state': 'loss_read'})

    def action_approve_batch(self):
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    def write(self, vals):
        # Sync reading_type and is_estimated
        if vals.get('reading_type') == 'estimated':
            vals['is_estimated'] = True
        elif vals.get('is_estimated'):
            vals['reading_type'] = 'estimated'
        elif vals.get('reading_type') in ('manual', 'ami') and 'is_estimated' not in vals:
            vals['is_estimated'] = False

        # Process uploaded meter image into canonical media asset
        if vals.get('meter_image_upload'):
            first_rec = self[:1]
            new_asset = first_rec._store_reading_image(
                vals['meter_image_upload'],
                filename=vals.get('meter_image_filename')
            )
            if new_asset:
                vals['image_asset_id'] = new_asset.id
                vals['meter_image_upload'] = False
                if vals.get('image_state', 'none') == 'none':
                    vals['image_state'] = 'pending'
                if first_rec.id and not new_asset.reading_id:
                    new_asset.sudo().write({'reading_id': first_rec.id})

        if vals.get('image_asset_id'):
            for r in self:
                asset = self.env['utility.media.asset'].sudo().browse(vals['image_asset_id'])
                if asset.exists() and not asset.reading_id and r.id:
                    asset.write({'reading_id': r.id})

        # P0 Guard: state cannot be directly mutated outside controlled transitions
        is_su_or_admin = bool(self.env.su or self.env.user.has_group('utility_core.group_utility_admin'))
        is_billing_mgr = bool(is_su_or_admin or self.env.user.has_group('utility_core.group_utility_billing_manager'))
        is_supervisor = bool(is_su_or_admin or self.env.user.has_group('utility_core.group_utility_supervisor'))
        is_revenue_mgr = bool(is_su_or_admin or self.env.user.has_group('utility_core.group_utility_revenue_manager'))
        is_reader = bool(self.env.user.has_group('utility_core.group_utility_meter_reader'))

        # Only superuser and system administrators can bypass reading protection
        # Billing managers may bypass only during explicit billing adjustments (allow_billing_adjustment)
        has_bypass = bool(
            (self.env.context.get('_bypass_reading_protection') and is_su_or_admin)
            or (self.env.context.get('allow_billing_adjustment') and is_billing_mgr)
        )

        if 'transformer_snapshot_id' in vals and not has_bypass:
            for reading in self:
                if reading.transformer_snapshot_id and vals['transformer_snapshot_id'] != reading.transformer_snapshot_id.id:
                    raise ValidationError(_("لا يمكن تعديل بصمة المحول التاريخية (transformer_snapshot_id) بعد تعبئتها."))

        # Guard direct state mutations
        if 'state' in vals:
            target_state = vals['state']
            has_transition_flag = bool(self.env.context.get('_reading_state_transition'))

            # If all records already have the target state, allow idempotent write
            if not any(r.state != target_state for r in self):
                pass
            # Transition to 'approved' can ONLY occur through action_approve()
            elif target_state == 'approved':
                if not has_bypass and self.env.context.get('_internal_approval_action') is not _APPROVAL_ACTION_TOKEN:
                    raise ValidationError(_('لا يمكن اعتماد القراءة مباشرةً عبر تعديل الحالة. يجب استخدام زر وإجراء الاعتماد الرسمي (action_approve).'))
                if not has_bypass:
                    self._check_approval_access()

                # Enforce business approval invariants on every transition to approved
                for r in self:
                    if r.state not in ('under_review', 'approved', 'queued') and not is_su_or_admin:
                        raise ValidationError(_('يمكن اعتماد القراءات قيد المراجعة فقط!'))
                    if r._requires_billing_review():
                        target_img = vals.get('image_state', r.image_state)
                        if target_img != 'clear':
                            raise ValidationError(_('لا يمكن اعتماد القراءة قبل اعتماد الصورة كصورة واضحة (clear).'))
                        target_consumption = vals.get('consumption', r.consumption)
                        if target_consumption < 0:
                            raise ValidationError(_('لا يمكن اعتماد قراءة باستهلاك سالب (%.2f). تحقق من صحة القراءة أو أنشئ تسوية.') % target_consumption)
            else:
                transition_authorized = False
                if has_transition_flag or has_bypass:
                    if is_su_or_admin or is_billing_mgr:
                        transition_authorized = True
                    elif is_supervisor or is_revenue_mgr:
                        transition_authorized = target_state in ('under_review', 'queued', 'draft')
                    elif is_reader:
                        transition_authorized = target_state == 'under_review'

                if not transition_authorized:
                    raise ValidationError(_('لا يمكن تغيير حالة القراءة مباشرةً. يجب استخدام أزرار وسير العمل المعتمد.'))

        # Enforce review access for image_state evaluations (clear, not_clear, not_same, loss_read)
        # Note: 'pending' is the initial state set upon image capture/upload by readers.
        if 'image_state' in vals and vals.get('image_state') != 'pending' and not self.env.su:
            self._check_review_access()

        if not has_bypass:
            # 'state' is included in bypass_fields because its direct mutation is already guarded by the first block above.
            bypass_fields = {'state', 'active', 'remarks', 'rejection_reason', 'rejected_by', 'rejected_at'}
            for reading in self:
                editable = set(self.STATE_EDITABLE.get(reading.state, set()))
                if 'image_state' in vals:
                    editable.add('image_state')
                changed = set(vals) - bypass_fields
                if changed and not changed.issubset(editable):
                    forbidden = changed - editable
                    raise ValidationError(_(
                        'لا يمكن تعديل الحقول التالية في حالة %(state)s: %(fields)s') % {
                            'state': reading.state,
                            'fields': ', '.join(sorted(forbidden)),
                        })
        meters = self.mapped('meter_id')
        res = super().write(vals)
        if meters:
            meters._update_last_reading()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        Meter = self.env['utility.meter']
        Sequence = self.env['ir.sequence']
        sequence_codes = {
            'opening': 'utility.reading.opening',
            'periodic': 'utility.reading.periodic',
            'replacement_closing': 'utility.reading.replacement_closing',
        }
        for vals in vals_list:
            if vals.get('reading_type') == 'estimated':
                vals['is_estimated'] = True
            elif vals.get('is_estimated'):
                vals['reading_type'] = 'estimated'

            # Process meter image upload into canonical media asset
            if vals.get('meter_image_upload') and not vals.get('image_asset_id'):
                raw_bytes = self._decode_image_payload(vals['meter_image_upload'])
                if raw_bytes:
                    target_filename = vals.get('meter_image_filename') or 'reading_new.jpg'
                    new_asset = self.env['utility.media.service'].sudo().store_media(
                        file_data=raw_bytes,
                        filename=target_filename,
                        mimetype='image/jpeg',
                        asset_type='meter_reading'
                    )
                    vals['image_asset_id'] = new_asset.id
                    if vals.get('image_state', 'none') == 'none':
                        vals['image_state'] = 'pending'

            purpose = vals.get('reading_purpose')
            if vals.get('is_initial_reading'):
                purpose = 'opening'
            purpose = purpose or 'periodic'
            vals['reading_purpose'] = purpose
            if vals.get('reading_id', _('جديد')) == _('جديد'):
                sequence_code = sequence_codes.get(purpose, 'utility.reading.periodic')
                vals['reading_id'] = (
                    Sequence.next_by_code(sequence_code)
                    or Sequence.next_by_code('utility.reading')
                    or _('جديد')
                )
            meter = Meter.browse(vals.get('meter_id')).exists() if vals.get('meter_id') else Meter
            if meter:
                vals.setdefault('account_id', meter.customer_id.id)
                vals.setdefault('meter_multiplier', meter.multiplier or 1.0)
                if not vals.get('transformer_snapshot_id'):
                    vals['transformer_snapshot_id'] = meter.transformer_id.id
            else:
                if not vals.get('transformer_snapshot_id') and vals.get('transformer_id'):
                    vals['transformer_snapshot_id'] = vals.get('transformer_id')
            if purpose == 'periodic' and not vals.get('date_range_id'):
                account = self.env['utility.customer'].browse(vals.get('account_id')).exists() if vals.get('account_id') else (meter.customer_id if meter else False)
                billing_period = account._get_effective_billing_period() if account else False
                period_domain = self._get_open_period_domain(
                    work_type='readings', billing_period=billing_period)
                raw_rdate = vals.get('reading_date')
                if raw_rdate:
                    rdate = fields.Date.to_date(raw_rdate)
                    period_domain += [('date_start', '<=', rdate), ('date_end', '>=', rdate)]
                open_period = self.env['date.range'].search(period_domain, limit=1)
                if not open_period:
                    raise ValidationError(_(
                        'لا توجد فترة قراءة مفعلة ومطابقة لتاريخ ودورية المشترك.'))
                vals['date_range_id'] = open_period.id
        records = super().create(vals_list)
        for r in records:
            if r.image_asset_id and r.image_state == 'none':
                r.with_context(_bypass_reading_protection=True).write({
                    'image_state': (
                        'clear' if r.state in ('approved', 'queued', 'billed')
                        else 'pending'
                    ),
                })
            if r.meter_id:
                r.meter_id._update_last_reading()
            if r.image_asset_id and not r.image_asset_id.reading_id:
                r.image_asset_id.sudo().write({'reading_id': r.id})
        return records
