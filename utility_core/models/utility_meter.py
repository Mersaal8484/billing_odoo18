from urllib.parse import quote

import re

from odoo import api, fields, models, _
import base64
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression


PHONE_9_RE = re.compile(r'^\d{9}$')


def validate_phone_9(value, field_label='رقم الهاتف'):
    if not value:
        return
    if not PHONE_9_RE.match(value):
        raise ValidationError(
            '%s يجب أن يتكون من 9 أرقام فقط، بدون مفتاح دولة (+967/00) أو شرطات.'
            % field_label
        )


class UtilityMeter(models.Model):
    _name = 'utility.meter'
    _description = 'عداد كهرباء'
    _inherit = ['mail.thread']
    _order = 'meter_number'
    _rec_name = 'meter_number'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    meter_number = fields.Char('رقم العداد', required=True, index=True, default=lambda self: _('جديد'))
    operational_number = fields.Char('الرقم التشغيلي', index=True, tracking=True)
    # المواصفات الفنية مصدر حقيقتها عداد الموديل (utility.meter.model)؛
    # الحقول هنا مجرد إسقاطات للقراءة فقط للتوافق مع الشاشات القديمة.
    manufacturer = fields.Char(
        'الشركة المصنّعة', related='model_id.manufacturer', store=True, readonly=True)
    model_id = fields.Many2one('utility.meter.model', 'الموديل')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع'),
        ('prepaid', 'دفع مسبق'),
        ('manual', 'يدوي')
    ], string='نظام العداد', default='manual', required=True)
    meter_type_id = fields.Many2one('utility.meter.type', 'نوع العداد')
    status_id = fields.Many2one('utility.meter.status', 'الحالة')
    phase = fields.Selection(
        related='model_id.phase', string='الطور', store=True, readonly=True,
        index=True,
        help='مواصفة الطور الفنية؛ تُجلب من موديل العداد'
    )
    voltage = fields.Float(
        'الجهد (فولت)', related='model_id.voltage', store=True, readonly=True)
    current_rating = fields.Float(
        'شدة التيار (أمبير)', related='model_id.current_rating', store=True, readonly=True)
    power_rating = fields.Float(
        'القدرة (كيلوواط)', related='model_id.power_rating', store=True, readonly=True)
    customer_id = fields.Many2one('utility.customer', 'العميل/العقد', index=True)
    account_id = fields.Many2one('utility.customer', string='الحساب', related='customer_id', store=True)

    idle_months = fields.Integer('الأشهر الخاملة', default=0, help='عدد الأشهر المتتالية بدون استهلاك')
    last_calibration_date = fields.Date('تاريخ آخر فحص/معايرة')
    next_calibration_date = fields.Date('تاريخ الفحص القادم')

    region_id = fields.Many2one('utility.region', 'المنطقة', compute='_compute_location_fields', store=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', compute='_compute_location_fields', store=True)
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', compute='_compute_location_fields', store=True)
    route_id = fields.Many2one('utility.route', 'خط السير', compute='_compute_location_fields', store=True)
    transformer_id = fields.Many2one('utility.transformer', 'المحول', compute='_compute_location_fields', store=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة', compute='_compute_location_fields', store=True)
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر', compute='_compute_location_fields', store=True)
    installation_date = fields.Date('تاريخ التركيب')
    address = fields.Text('العنوان')
    reading_ids = fields.One2many('utility.reading', 'meter_id', string='سجل القراءات')
    log_ids = fields.One2many('utility.meter.log', 'meter_id', string='سجل تاريخ العداد')
    reading_count = fields.Integer('عدد القراءات', compute='_compute_reading_count', store=True)
    last_read_date = fields.Datetime('تاريخ آخر قراءة')
    last_reading_value = fields.Float('قيمة آخر قراءة', digits=(12, 3))
    multiplier = fields.Float('معامل الضرب', default=1.0)
    qr_code_value = fields.Char('بيانات QR', compute='_compute_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_qr_code', readonly=True)
    qr_code_image = fields.Binary('صورة QR', compute='_compute_qr_code', readonly=True, attachment=False)

    # خصائص الربط
    is_coupling_meter = fields.Boolean('عداد ربط رئيسي', default=False, help='يُشير إذا كان هذا العداد هو عداد ربط يقرأ إجمالي طاقة الفيدر أو المحطة')

    # نوع الربط
    connection_type = fields.Selection([
        ('not_connected', 'غير مربوط'),
        ('subscriber', 'مربوط بمشترك'),
        ('private_transformer', 'محول خاص'),
        ('transformer', 'محول'),
        ('feeder', 'فيدر'),
    ], string='نوع الربط', default='not_connected', required=True, tracking=True)

    linked_transformer_id = fields.Many2one(
        'utility.transformer', 'المحول المرتبط', index=True,
        domain="[('is_private', '=', False)]")
    linked_private_transformer_id = fields.Many2one(
        'utility.transformer', 'المحول الخاص', index=True,
        domain="[('is_private', '=', True)]")
    linked_feeder_id = fields.Many2one(
        'utility.feeder', 'Linked Feeder', index=True)
    available_meter_model_ids = fields.Many2many(
        'utility.meter.model', compute='_compute_available_meter_catalogs',
        string='موديلات العدادات المتوافقة')
    available_meter_type_ids = fields.Many2many(
        'utility.meter.type', compute='_compute_available_meter_catalogs',
        string='أنواع العدادات المتوافقة')

    def _get_required_network_phase(self):
        """Return the phase imposed by the connected network asset, if any."""
        self.ensure_one()
        if self.connection_type == 'transformer':
            return self.linked_transformer_id.phase
        if self.connection_type == 'private_transformer':
            return self.linked_private_transformer_id.phase
        if self.connection_type == 'feeder':
            return self.linked_feeder_id.phase
        return False

    @api.depends(
        'connection_type', 'model_id.phase',
        'linked_transformer_id.phase', 'linked_private_transformer_id.phase',
        'linked_feeder_id.phase',
    )
    def _compute_available_meter_catalogs(self):
        MeterModel = self.env['utility.meter.model']
        MeterType = self.env['utility.meter.type']
        all_models = MeterModel.search([])
        all_types = MeterType.search([])
        models_by_phase = {
            'single': all_models.filtered(lambda model: model.phase == 'single'),
            'three': all_models.filtered(lambda model: model.phase == 'three'),
        }
        types_by_phase = {
            'single': all_types.filtered(lambda meter_type: meter_type.phase == 'single'),
            'three': all_types.filtered(lambda meter_type: meter_type.phase == 'three'),
        }
        for meter in self:
            phase = meter._get_required_network_phase() or meter.phase
            meter.available_meter_model_ids = models_by_phase.get(phase, all_models)
            meter.available_meter_type_ids = types_by_phase.get(phase, all_types)

    def _clear_incompatible_catalog_values(self):
        """Keep the form coherent when its connected asset changes phase."""
        self.ensure_one()
        required_phase = self._get_required_network_phase()
        if required_phase and self.model_id and self.phase and self.phase != required_phase:
            self.model_id = False
        effective_phase = self._get_required_network_phase() or self.phase
        if (effective_phase and self.meter_type_id.phase
                and self.meter_type_id.phase != effective_phase):
            self.meter_type_id = False

    @api.depends('reading_ids')
    def _compute_reading_count(self):
        for m in self:
            m.reading_count = len(m.reading_ids)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if not self.model_id:
            return
        model = self.model_id
        if not self.phase:
            self.phase = model.phase
        if not self.meter_type_id:
            self.meter_type_id = model.meter_type_id
        self._clear_incompatible_catalog_values()

    @api.onchange('connection_type')
    def _onchange_connection_type(self):
        if self.connection_type == 'not_connected':
            self.customer_id = False
            self.linked_transformer_id = False
            self.linked_private_transformer_id = False
            self.linked_feeder_id = False
        elif self.connection_type == 'subscriber':
            self.linked_transformer_id = False
            self.linked_private_transformer_id = False
            self.linked_feeder_id = False
        elif self.connection_type == 'transformer':
            self.customer_id = False
            self.linked_private_transformer_id = False
            self.linked_feeder_id = False
        elif self.connection_type == 'private_transformer':
            self.customer_id = False
            self.linked_transformer_id = False
            self.linked_feeder_id = False
        elif self.connection_type == 'feeder':
            self.customer_id = False
            self.linked_transformer_id = False
            self.linked_private_transformer_id = False

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id and self.connection_type != 'subscriber':
            self.connection_type = 'subscriber'

    @api.onchange('linked_transformer_id')
    def _onchange_linked_transformer_id(self):
        if self.linked_transformer_id and self.connection_type != 'transformer':
            self.connection_type = 'transformer'
        self._clear_incompatible_catalog_values()

    @api.onchange('linked_private_transformer_id')
    def _onchange_linked_private_transformer_id(self):
        if self.linked_private_transformer_id and self.connection_type != 'private_transformer':
            self.connection_type = 'private_transformer'
        self._clear_incompatible_catalog_values()

    @api.onchange('linked_feeder_id')
    def _onchange_linked_feeder_id(self):
        if self.linked_feeder_id and self.connection_type != 'feeder':
            self.connection_type = 'feeder'
        self._clear_incompatible_catalog_values()

    @api.constrains(
        'connection_type', 'linked_transformer_id',
        'linked_private_transformer_id', 'linked_feeder_id', 'model_id',
        'meter_type_id', 'phase',
    )
    def _check_phase_matches_connected_asset(self):
        """Protect phase compatibility for UI, imports, and RPC writes."""
        for meter in self:
            required_phase = meter._get_required_network_phase()
            if required_phase and meter.phase and meter.phase != required_phase:
                raise ValidationError(_(
                    'طور العداد يجب أن يطابق طور العنصر المرتبط (%s).'
                ) % dict(meter._fields['phase'].selection).get(required_phase))
            effective_phase = required_phase or meter.phase
            if (effective_phase and meter.meter_type_id.phase
                    and meter.meter_type_id.phase != effective_phase):
                raise ValidationError(_(
                    'نوع العداد المختار لا يطابق طور العداد أو العنصر المرتبط.'
                ))

    def _update_last_reading(self):
        for m in self:
            last = self.env['utility.reading'].search(
                [('meter_id', '=', m.id)], order='reading_date desc, id desc', limit=1)
            if last:
                m.sudo().write({
                    'last_reading_value': last.reading_value,
                    'last_read_date': last.reading_date,
                })

    def _lock_meter(self):
        """Serialize concurrent decisions that involve this meter (e.g. meter
        assignment/installation) by locking its row with SELECT ... FOR UPDATE.
        Must be called inside the same transaction as the decision that reads
        the current assignments and then inserts the new one."""
        self.env.flush_all()
        if self.ids:
            self.env.cr.execute(
                'SELECT id FROM utility_meter WHERE id IN %s ORDER BY id FOR UPDATE',
                [tuple(self.ids)])
        self.invalidate_cache()

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجل القراءات - %s') % self.meter_number,
            'res_model': 'utility.reading',
            'view_mode': 'list,form',
            'domain': [('meter_id', '=', self.id)],
            'context': {'default_meter_id': self.id},
        }

    @api.depends('connection_type',
                 'customer_id', 'customer_id.region_id', 'customer_id.area_id', 'customer_id.zone_id',
                 'customer_id.route_id', 'customer_id.transformer_id', 'customer_id.transformer_id.substation_id',
                 'customer_id.cell_id',
                 'linked_transformer_id', 'linked_transformer_id.substation_id', 'linked_transformer_id.feeder_id',
                 'linked_transformer_id.zone_region_id',
                 'linked_private_transformer_id', 'linked_private_transformer_id.substation_id',
                 'linked_private_transformer_id.feeder_id', 'linked_private_transformer_id.zone_region_id',
                 'linked_feeder_id', 'linked_feeder_id.substation_id')
    def _compute_location_fields(self):
        for m in self:
            ct = m.connection_type
            if ct == 'subscriber' and m.customer_id:
                m.region_id = m.customer_id.region_id
                m.area_id = m.customer_id.area_id
                m.zone_id = m.customer_id.zone_id
                m.route_id = m.customer_id.route_id
                m.transformer_id = m.customer_id.transformer_id
                m.substation_id = m.transformer_id.substation_id if m.transformer_id else False
                m.feeder_id = m.customer_id.cell_id
            elif ct == 'private_transformer' and m.linked_private_transformer_id:
                t = m.linked_private_transformer_id
                m.region_id = t.region_id
                m.area_id = t.area_id
                m.zone_id = t.zone_region_id
                m.route_id = False
                m.transformer_id = t
                m.substation_id = t.substation_id
                m.feeder_id = t.feeder_id
            elif ct == 'transformer' and m.linked_transformer_id:
                t = m.linked_transformer_id
                m.region_id = t.region_id
                m.area_id = t.area_id
                m.zone_id = t.zone_region_id
                m.route_id = False
                m.transformer_id = t
                m.substation_id = t.substation_id
                m.feeder_id = t.feeder_id
            elif ct == 'feeder' and m.linked_feeder_id:
                f = m.linked_feeder_id
                m.region_id = f.region_id
                m.area_id = f.area_id
                m.zone_id = False
                m.route_id = False
                m.transformer_id = False
                m.substation_id = f.substation_id
                m.feeder_id = f
            else:
                m.region_id = False
                m.area_id = False
                m.zone_id = False
                m.route_id = False
                m.transformer_id = False
                m.substation_id = False
                m.feeder_id = False

    @api.depends('meter_number', 'operational_number', 'connection_type',
                 'customer_id.customer_number', 'customer_id.partner_id.name',
                 'linked_transformer_id.code', 'linked_private_transformer_id.code',
                 'linked_feeder_id.code',
                 'transformer_id.code', 'feeder_id.code')
    def _compute_qr_code(self):
        for meter in self:
            customer_name = ''
            customer_number = ''
            if meter.customer_id:
                customer_number = meter.customer_id.customer_number or ''
                customer_name = meter.customer_id.partner_id.name or ''
            company_name = (meter.company_id.name if meter.company_id else self.env.company.name) or ''
            payload = '|'.join([
                'UTILITY-METER',
                company_name,
                meter.meter_number or '',
                meter._get_physical_serial(),
                customer_number,
                customer_name,
                meter.transformer_id.code or '',
                meter.feeder_id.code or '',
                meter.operational_number or '',
            ])
            meter.qr_code_value = payload
            encoded = quote(payload)
            base_url = self.env['ir.config_parameter'].sudo().get_param(
                'report.url') or self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url', 'http://localhost:8069')
            meter.qr_code_url = '%s/report/barcode?barcode_type=QR&value=%s&width=%s&height=%s' % (
                base_url.rstrip('/'), encoded, 200, 200)
            try:
                barcode = self.env['ir.actions.report'].barcode('QR', payload, width=200, height=200)
                meter.qr_code_image = base64.b64encode(barcode)
            except Exception:
                meter.qr_code_image = False
    _sql_constraints = [
        ('unique_meter_number_company', 'unique(meter_number, company_id)',
         'رقم العداد يجب أن يكون فريداً لكل شركة!'),
        ('unique_operational_number_company', 'unique(operational_number, company_id)',
         'الرقم التشغيلي للعداد يجب أن يكون فريداً لكل شركة!'),
    ]

    def action_add_subscriber(self):
        self.ensure_one()
        if self.connection_type != 'not_connected' or self.customer_id:
            raise UserError(_('هذا العداد مرتبط بالفعل بمشترك (%s) أو بعنصر آخر.') % (self.customer_id.display_name if self.customer_id else self.connection_type))
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة مشترك جديد'),
            'res_model': 'utility.meter.subscriber.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_private_transformer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة محول خاص'),
            'res_model': 'utility.meter.private.transformer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_transformer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة محول'),
            'res_model': 'utility.meter.transformer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def action_add_feeder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إضافة فيدر / خلية'),
            'res_model': 'utility.meter.feeder.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meter_id': self.id},
        }

    def _check_mutation_scope(self, vals):
        """Validate canonical ownership of a meter mutation against the acting user's scope.

        utility.meter.region_id/area_id are computed-stored from _compute_location_fields
        and will not appear in vals directly. The real attack vector is changing the
        canonical owner (customer_id, linked_transformer_id, etc.) to an out-of-scope record.

        SECURITY (P0): utility_scope_bypass is ONLY honored when env.su=True (superuser/migration)
        or the acting user is a Utility Admin. It CANNOT be exploited via crafted RPC context.

        SECURITY (P1): Fail-closed — if connection_type is subscriber/transformer/feeder/etc.
        and the canonical owner exists but has no resolvable geography, REJECT.
        Only 'not_connected' meters are exempt (no canonical owner by design).
        """
        _bypass_allowed = (
            self.env.su
            or self.env.user.has_group('utility_core.group_utility_admin')
        )
        if (
            (self.env.context.get('utility_scope_bypass') and _bypass_allowed)
            or self.env.user._is_global_utility_scope()
        ):
            return
        effective_branches = self.env.user._get_effective_branch_ids()
        effective_regions = self.env.user._get_effective_region_ids()

        def _in_scope(region, area):
            return (
                (area and area.id in effective_branches)
                or (region and region.id in effective_regions)
            )

        ownership_keys = {
            'customer_id', 'linked_transformer_id',
            'linked_private_transformer_id', 'linked_feeder_id', 'connection_type',
        }
        if not ownership_keys.intersection(vals.keys()):
            return  # No ownership-changing field — skip

        for meter in self:
            ct = vals.get('connection_type', meter.connection_type)

            if ct == 'not_connected':
                continue  # No canonical owner — allowed explicitly

            region = False
            area = False
            owner_found = False

            if ct == 'subscriber':
                cust_id = vals.get('customer_id', meter.customer_id.id if meter.customer_id else False)
                if cust_id:
                    cust = self.env['utility.customer'].sudo().browse(cust_id).exists()
                    if cust:
                        owner_found = True
                        region = cust.partner_id.region_id
                        area = cust.partner_id.area_id
            elif ct in ('transformer', 'private_transformer'):
                key = 'linked_transformer_id' if ct == 'transformer' else 'linked_private_transformer_id'
                t_id = vals.get(key, getattr(meter, key).id if getattr(meter, key, False) else False)
                if t_id:
                    transformer = self.env['utility.transformer'].sudo().browse(t_id).exists()
                    if transformer:
                        owner_found = True
                        region = transformer.region_id
                        area = transformer.area_id
            elif ct == 'feeder':
                f_id = vals.get('linked_feeder_id', meter.linked_feeder_id.id if meter.linked_feeder_id else False)
                if f_id:
                    feeder = self.env['utility.feeder'].sudo().browse(f_id).exists()
                    if feeder:
                        owner_found = True
                        region = feeder.region_id
                        area = feeder.area_id

            # FAIL-CLOSED: if connected meter has no canonical owner, or owner geography is unresolvable or out of scope = reject
            if not owner_found:
                raise ValidationError(_(
                    'يجب تحديد العنصر المرتبط (مشترك، محول، فيدر) المطابق لنوع الاتصال المحدد للعداد.'
                ))
            if not _in_scope(region, area):
                raise AccessError(_(
                    'لا يمكنك ربط عداد بعنصر (عميل أو محول أو فيدر) خارج نطاقك التنظيمي المخصص، '
                    'أو بدون منطقة/فرع محددة على العنصر المستهدف.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'operational_number' in vals:
                vals['operational_number'] = (vals['operational_number'] or '').strip() or False
            if vals.get('meter_number', _('جديد')) == _('جديد'):
                vals['meter_number'] = self.env['ir.sequence'].next_by_code('utility.meter') or _('جديد')
            if vals.get('connection_type', 'not_connected') == 'not_connected':
                if vals.get('customer_id'):
                    vals['connection_type'] = 'subscriber'
                elif vals.get('linked_private_transformer_id'):
                    vals['connection_type'] = 'private_transformer'
                elif vals.get('linked_transformer_id'):
                    vals['connection_type'] = 'transformer'
                elif vals.get('linked_feeder_id'):
                    vals['connection_type'] = 'feeder'
        # Validate canonical ownership scope before creating meters.
        # SECURITY: bypass gated to superuser / Utility Admin only.
        _bypass_allowed = (
            self.env.su
            or self.env.user.has_group('utility_core.group_utility_admin')
        )
        if not (
            (self.env.context.get('utility_scope_bypass') and _bypass_allowed)
            or self.env.user._is_global_utility_scope()
        ):
            for vals in vals_list:
                self._check_create_scope_vals(vals)
        return super().create(vals_list)

    @api.model
    def _check_create_scope_vals(self, vals):
        """Scope check for meter creation (no existing record yet).
        Resolves canonical geography from vals and validates against user scope.

        SECURITY (P0): bypass gated to env.su or Utility Admin.
        SECURITY (P1): Fail-closed — if canonical owner is missing or has no geography, reject.
        Only 'not_connected' meters are exempt.
        """
        _bypass_allowed = (
            self.env.su
            or self.env.user.has_group('utility_core.group_utility_admin')
        )
        if (
            (self.env.context.get('utility_scope_bypass') and _bypass_allowed)
            or self.env.user._is_global_utility_scope()
        ):
            return
        effective_branches = self.env.user._get_effective_branch_ids()
        effective_regions = self.env.user._get_effective_region_ids()

        def _in_scope(region, area):
            return (
                (area and area.id in effective_branches)
                or (region and region.id in effective_regions)
            )

        ct = vals.get('connection_type', 'not_connected')

        if ct == 'not_connected':
            return  # No canonical owner — allowed explicitly

        region = False
        area = False
        owner_found = False

        if ct == 'subscriber':
            cust_id = vals.get('customer_id')
            if cust_id:
                cust = self.env['utility.customer'].sudo().browse(cust_id).exists()
                if cust:
                    owner_found = True
                    region = cust.partner_id.region_id
                    area = cust.partner_id.area_id
        elif ct in ('transformer', 'private_transformer'):
            key = 'linked_transformer_id' if ct == 'transformer' else 'linked_private_transformer_id'
            t_id = vals.get(key)
            if t_id:
                transformer = self.env['utility.transformer'].sudo().browse(t_id).exists()
                if transformer:
                    owner_found = True
                    region = transformer.region_id
                    area = transformer.area_id
        elif ct == 'feeder':
            f_id = vals.get('linked_feeder_id')
            if f_id:
                feeder = self.env['utility.feeder'].sudo().browse(f_id).exists()
                if feeder:
                    owner_found = True
                    region = feeder.region_id
                    area = feeder.area_id

        # FAIL-CLOSED: if connected meter has no canonical owner, or owner geography is unresolvable or out of scope = reject
        if not owner_found:
            raise ValidationError(_(
                'يجب تحديد العنصر المرتبط (مشترك، محول، فيدر) عند إنشاء عداد متصل.'
            ))
        if not _in_scope(region, area):
            raise AccessError(_(
                'لا يمكنك إنشاء عداد مرتبط بعنصر (عميل أو محول أو فيدر) '
                'خارج نطاقك التنظيمي المخصص، أو بدون منطقة/فرع محددة على العنصر المستهدف.'
            ))

    @api.model
    def _search_display_name(self, operator, value):
        return self._name_search_domain(value, operator)

    def _get_physical_serial(self):
        """Return the physical serial when an inventory bridge provides it."""
        self.ensure_one()
        return ''

    @api.model
    def _name_search_domain(self, name, operator='ilike'):
        """Build the logical meter lookup domain without inventory fields."""
        if not name:
            return []
        domains = [[(field, operator, name)] for field in (
            'meter_number',
            'operational_number',
            'customer_id.partner_id.name',
            'meter_type_id.name',
        )]
        if 'lot_id' in self._fields:
            domains.append([('lot_id.name', operator, name)])
        aggregator = expression.AND if operator in expression.NEGATIVE_TERM_OPERATORS else expression.OR
        return aggregator(domains)

    @api.model
    def _scan_domain(self, value):
        """Build the barcode lookup domain; inventory may add Lot/Serial."""
        return [('meter_number', '=', value)]

    @api.depends('connection_type', 'meter_number', 'operational_number', 'customer_id', 'customer_id.partner_id', 'linked_private_transformer_id', 'linked_transformer_id', 'transformer_id', 'linked_feeder_id', 'feeder_id', 'meter_type_id', 'payment_type')
    def _compute_display_name(self):
        for meter in self:
            parts = [
                f"[{meter.operational_number}] {meter.meter_number}"
                if meter.operational_number else f"[{meter.meter_number}]"
            ]

            # 1. اسم العنصر المرتبط حسب نوع الربط (مشترك / محول خاص / محول / فيدر)
            target_name = False
            ct = getattr(meter, 'connection_type', False)
            if ct == 'subscriber' and meter.customer_id and meter.customer_id.partner_id:
                target_name = meter.customer_id.partner_id.name
            elif ct == 'private_transformer' and meter.linked_private_transformer_id:
                target_name = meter.linked_private_transformer_id.name
            elif ct == 'transformer' and (meter.linked_transformer_id or meter.transformer_id):
                target_name = (meter.linked_transformer_id or meter.transformer_id).name
            elif ct == 'feeder' and (meter.linked_feeder_id or meter.feeder_id):
                target_name = (meter.linked_feeder_id or meter.feeder_id).name
            elif not ct and meter.customer_id and meter.customer_id.partner_id:
                target_name = meter.customer_id.partner_id.name

            if target_name:
                parts.append(target_name)

            # 2. نوع العداد
            type_name = False
            if meter.meter_type_id and meter.meter_type_id.name:
                type_name = meter.meter_type_id.name
            elif meter.payment_type:
                type_name = dict(meter._fields['payment_type'].selection).get(meter.payment_type)

            if type_name:
                parts.append(type_name)

            meter.display_name = " - ".join(parts)

    def write(self, vals):
        vals = dict(vals)
        if 'operational_number' in vals:
            vals['operational_number'] = (vals['operational_number'] or '').strip() or False
        # Auto-infer connection_type when linking an entity without explicit connection_type
        if vals.get('connection_type') == 'not_connected':
            vals['customer_id'] = False
            vals['linked_transformer_id'] = False
            vals['linked_private_transformer_id'] = False
            vals['linked_feeder_id'] = False
        elif 'connection_type' not in vals:
            if vals.get('customer_id'):
                vals['connection_type'] = 'subscriber'
            elif vals.get('linked_private_transformer_id'):
                vals['connection_type'] = 'private_transformer'
            elif vals.get('linked_transformer_id'):
                vals['connection_type'] = 'transformer'
            elif vals.get('linked_feeder_id'):
                vals['connection_type'] = 'feeder'

        if 'customer_id' in vals and not vals['customer_id'] and 'connection_type' not in vals:
            for meter in self:
                if meter.connection_type == 'subscriber':
                    vals['connection_type'] = 'not_connected'

        # Canonical mutation integrity: validate ownership before any DB write.
        self._check_mutation_scope(vals)
        for meter in self:
            if not self.env.context.get('skip_implicit_log'):
                if 'status_id' in vals and vals.get('status_id') != meter.status_id.id:
                    new_status = self.env['utility.meter.status'].browse(vals['status_id']) if vals.get('status_id') else None
                    desc = f"تغيرت حالة العداد من {meter.status_id.name if meter.status_id else 'غير محدد'} إلى {new_status.name if new_status else 'غير محدد'}"
                    if 'utility.meter.log' in self.env:
                        self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                            meter.id, 'status_change', desc, customer_id=meter.customer_id
                        )
                if 'customer_id' in vals and vals.get('customer_id') != meter.customer_id.id:
                    old_cust = meter.customer_id.display_name if meter.customer_id else 'Undefined'
                    new_cust = self.env['utility.customer'].browse(vals['customer_id']).display_name if vals.get('customer_id') else 'Undefined'
                    desc = f"تم نقل العداد من العميل {old_cust} إلى العميل {new_cust}"
                    if 'utility.meter.log' in self.env:
                        self.env['utility.meter.log'].with_context(allow_log_update=True)._create_log(
                            meter.id, 'transfer', desc, customer_id=vals.get('customer_id')
                        )
        return super().write(vals)

    @api.model
    def cron_check_idle_meters(self, batch_limit=500):
        """تحديث عدد الأشهر الخاملة لكل عداد ثم إنشاء أوامر الفحص للعدادات الخاملة 3 أشهر فما فوق."""
        self.env.cr.execute("""
            UPDATE utility_meter
            SET idle_months = sub.cnt
            FROM (
                SELECT meter_id, COUNT(id) AS cnt
                FROM utility_reading
                WHERE reading_date >= current_date - interval '3 months'
                  AND consumption = 0
                  AND state IN ('approved', 'billed')
                GROUP BY meter_id
            ) sub
            WHERE utility_meter.id = sub.meter_id
              AND utility_meter.active = true;
        """)
        self.env.cr.execute("""
            UPDATE utility_meter
            SET idle_months = 0
            WHERE active = true
              AND id NOT IN (
                  SELECT meter_id
                  FROM utility_reading
                  WHERE reading_date >= current_date - interval '3 months'
                    AND consumption = 0
                    AND state IN ('approved', 'billed')
              );
        """)
        created_orders = 0
        if 'utility.service.order' in self.env:
            meters = self.search([
                ('active', '=', True),
                ('idle_months', '>=', 3),
                ('customer_id', '!=', False),
                ('customer_id.state', '=', 'active'),
            ], limit=batch_limit)
            for meter in meters:
                existing = self.env['utility.service.order'].search([
                    ('meter_id', '=', meter.id),
                    ('service_type', 'in', ('inspection', 'meter_test')),
                    ('state', 'in', ('draft', 'approved', 'scheduled', 'in_progress')),
                ], limit=1)
                if not existing:
                    self.env['utility.service.order'].create({
                        'service_type': 'inspection',
                        'priority': 'high',
                        'customer_id': meter.customer_id.id,
                        'meter_id': meter.id,
                        'description': _('تفتيش آلي: العداد خامل منذ %d أشهر. يرجى الفحص الميداني.') % meter.idle_months,
                        'state': 'draft',
                    })
                    created_orders += 1
        return {'processed': batch_limit, 'success': created_orders, 'failed': 0, 'skipped': 0}


class UtilityMeterType(models.Model):
    _name = 'utility.meter.type'
    _description = 'نوع العداد'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    description = fields.Text('الوصف')


class UtilityMeterModel(models.Model):
    _name = 'utility.meter.model'
    _description = 'موديل العداد (الكتالوج الفني)'
    _order = 'name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('كود الموديل/الرمز الفني')
    manufacturer = fields.Char('الشركة المصنّعة')
    default_meter_type_id = fields.Many2one('utility.meter.type', 'النوع الافتراضي بالموديل')
    meter_type_id = fields.Many2one('utility.meter.type', 'نوع العداد الافتراضي', related='default_meter_type_id', readonly=False, store=True)
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور المصنعي', help='الخصائص الطورية المصنعية للموديل')
    voltage = fields.Float('الجهد (فولت)')
    current_rating = fields.Float('شدة التيار (أمبير)')
    power_rating = fields.Float('القدرة (كيلوواط)')
    voltage_range = fields.Char('نطاق الجهد')
    current_range = fields.Char('نطاق التيار')
    sts_supported = fields.Boolean('يدعم STS')
    communication_types = fields.Char('أنواع الاتصال')
    description = fields.Text('الوصف الفني')


class UtilityMeterStatus(models.Model):
    _name = 'utility.meter.status'
    _description = 'حالة العداد'
    _order = 'sequence, name'

    name = fields.Char('الاسم', required=True)
    code = fields.Char('الرمز', required=True)
    sequence = fields.Integer('التسلسل')
    description = fields.Text('الوصف')
