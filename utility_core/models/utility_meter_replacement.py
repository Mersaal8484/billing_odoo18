from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class UtilityMeterReplacement(models.Model):
    _name = 'utility.meter.replacement'
    _description = 'سجل استبدال العدادات (مشتركين / فيدرات / محولات)'
    _inherit = ['mail.thread']
    _order = 'replace_date desc'

    name = fields.Char(string="الاسم", compute="_compute_name", store=True)
    company_id = fields.Many2one('res.company', string='الشركة', required=True, index=True, default=lambda self: self.env.company)
    closing_reading_id = fields.Many2one('utility.reading', string='سجل القراءة الختامية', readonly=True, copy=False, ondelete='restrict')
    opening_reading_id = fields.Many2one('utility.reading', string='سجل القراءة الافتتاحية', readonly=True, copy=False, ondelete='restrict')

    target_type = fields.Selection([
        ('subscriber', 'عداد مشترك (حساب كهرباء)'),
        ('feeder', 'عداد فيدر / خلية'),
        ('transformer', 'عداد محول'),
    ], string="نوع العداد المستبدل", default='subscriber', required=True, tracking=True)

    # Target Entities
    utility_account_id = fields.Many2one('utility.customer', string="حساب الكهرباء / المشترك", tracking=True, check_company=True)
    partner_id = fields.Many2one('res.partner', related='utility_account_id.partner_id', string="العميل", store=True)
    feeder_id = fields.Many2one('utility.feeder', string="الفيدر / الخلية", tracking=True, check_company=True)
    transformer_id = fields.Many2one('utility.transformer', string="المحول", tracking=True, check_company=True)

    @api.depends('target_type', 'utility_account_id', 'feeder_id', 'transformer_id')
    def _compute_name(self):
        for rec in self:
            if rec.target_type == 'subscriber' and rec.utility_account_id:
                rec.name = f"استبدال عداد مشترك: {rec.utility_account_id.display_name}"
            elif rec.target_type == 'feeder' and rec.feeder_id:
                rec.name = f"استبدال عداد فيدر: {rec.feeder_id.name}"
            elif rec.target_type == 'transformer' and rec.transformer_id:
                rec.name = f"استبدال عداد محول: {rec.transformer_id.name}"
            else:
                rec.name = "استبدال عداد جديد"

    # Old meter
    old_meter_id = fields.Many2one(
        'utility.meter', string="العداد القديم",
        compute='_compute_old_meter_info', store=True, readonly=False, check_company=True)
    old_meter_number = fields.Char(
        string="رقم العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_meter_type_id = fields.Many2one(
        'utility.meter.type', string="نوع العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string="طور العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_last_invo_reading = fields.Float(
        string="آخر قراءة مفوترة", digits=(12, 3), compute='_compute_old_meter_info', store=True, readonly=False)

    old_closing_reading = fields.Float(string="آخر قراءة للعداد عند الاستبدال", digits=(12, 3), required=True, tracking=True)
    old_uninvoiced_consumption = fields.Float(string="الاستهلاك غير المفوتر", digits=(12, 3), compute="_compute_old_uninvoiced", store=True)

    old_meter_serial_scan = fields.Char(string="مسح العداد القديم (باركود)", store=False, help="استخدم الكاميرا لمسح العداد واستدعاء العنصر المربوط")
    replacement_image = fields.Binary(string="صورة العداد (اختياري)", attachment=True)

    # New meter
    new_meter_serial_scan = fields.Char(string="مسح العداد الجديد (باركود)", store=False, help="استخدم الكاميرا للبحث عن العداد الجديد")
    new_meter_id = fields.Many2one('utility.meter', string="العداد الجديد (موجود بالنظام)", domain="[('connection_type', '=', 'not_connected')]", tracking=True, check_company=True)
    new_meter_number = fields.Char(string="رقم العداد الجديد (لإنشاء جديد)", tracking=True)
    new_meter_model_id = fields.Many2one('utility.meter.model', string="موديل العداد الجديد")
    new_meter_type_id = fields.Many2one('utility.meter.type', string="نوع العداد الجديد")
    new_phase = fields.Selection(
        related='new_meter_model_id.phase', string="طور العداد الجديد", readonly=True)
    new_opening_reading = fields.Float(string="القراءة الافتتاحية", digits=(12, 3), required=True, tracking=True)
    new_meter_val = fields.Float(string="معامل الضرب", default=1.0, tracking=True)

    replace_date = fields.Datetime(string="تاريخ طلب الاستبدال", default=fields.Datetime.now, required=True, tracking=True)
    reason = fields.Selection([
        ('fault', 'عطل فني'),
        ('expired', 'انتهاء العمر الافتراضي'),
        ('upgrade', 'تطوير النظام'),
        ('tamper', 'تلاعب/سرقة'),
        ('other', 'أخرى'),
    ], string="سبب الاستبدال", required=True, tracking=True)
    notes = fields.Text(string="ملاحظات")
    user_id = fields.Many2one('res.users', string="المستخدم", default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم الاستبدال (Done)'),
    ], string="الحالة", default='draft', tracking=True)

    @api.depends('target_type', 'old_meter_id', 'utility_account_id', 'utility_account_id.meter_id', 'feeder_id', 'feeder_id.coupling_meter_id', 'transformer_id', 'transformer_id.coupling_meter_id')
    def _compute_old_meter_info(self):
        for rec in self:
            if rec.state == 'done':
                continue
            meter = False
            last_invo_reading = 0.0
            if rec.target_type == 'subscriber' and rec.utility_account_id:
                acc = rec.utility_account_id
                meter = rec.old_meter_id or acc.meter_id
                last_invo_reading = (
                    rec.old_last_invo_reading
                    or acc.last_invoice_reading
                    or acc.last_reading_value
                    or (meter.last_reading_value if meter else 0.0)
                    or 0.0
                )
            elif rec.target_type == 'feeder' and rec.feeder_id:
                feeder = rec.feeder_id
                meter = rec.old_meter_id or feeder.coupling_meter_id or self.env['utility.meter'].search([('linked_feeder_id', '=', feeder.id)], limit=1)
                last_invo_reading = rec.old_last_invo_reading or (meter.last_reading_value if meter else 0.0)
            elif rec.target_type == 'transformer' and rec.transformer_id:
                trans = rec.transformer_id
                meter = rec.old_meter_id or trans.coupling_meter_id or self.env['utility.meter'].search([('linked_transformer_id', '=', trans.id)], limit=1)
                last_invo_reading = rec.old_last_invo_reading or (meter.last_reading_value if meter else 0.0)

            if meter:
                rec.old_meter_id = meter
                rec.old_meter_number = meter.meter_number
                rec.old_meter_type_id = meter.meter_type_id
                rec.old_phase = meter.phase
                rec.old_last_invo_reading = last_invo_reading
            else:
                if not rec.old_meter_id: rec.old_meter_id = False
                if not rec.old_meter_number: rec.old_meter_number = False
                if not rec.old_meter_type_id: rec.old_meter_type_id = False
                if not rec.old_phase: rec.old_phase = False
                rec.old_last_invo_reading = last_invo_reading

    @api.depends('old_closing_reading', 'old_last_invo_reading', 'old_meter_id')
    def _compute_old_uninvoiced(self):
        for rec in self:
            val = rec.old_meter_id.multiplier if rec.old_meter_id else 1.0
            rec.old_uninvoiced_consumption = max((rec.old_closing_reading - rec.old_last_invo_reading) * val, 0.0)

    @api.onchange('old_closing_reading', 'old_last_invo_reading')
    def _onchange_old_closing_reading(self):
        val = self.old_meter_id.multiplier if self.old_meter_id else 1.0
        self.old_uninvoiced_consumption = max((self.old_closing_reading - self.old_last_invo_reading) * val, 0.0)

    @api.onchange('target_type', 'utility_account_id', 'feeder_id', 'transformer_id')
    def _onchange_target_entity(self):
        meter = False
        last_reading = 0.0
        if self.target_type == 'subscriber' and self.utility_account_id:
            acc = self.utility_account_id
            meter = acc.meter_id
            last_reading = acc.last_invoice_reading or acc.last_reading_value or 0.0
        elif self.target_type == 'feeder' and self.feeder_id:
            feeder = self.feeder_id
            meter = feeder.coupling_meter_id or self.env['utility.meter'].search([('linked_feeder_id', '=', feeder.id)], limit=1)
            last_reading = meter.last_reading_value if meter else 0.0
        elif self.target_type == 'transformer' and self.transformer_id:
            trans = self.transformer_id
            meter = trans.coupling_meter_id or self.env['utility.meter'].search([('linked_transformer_id', '=', trans.id)], limit=1)
            last_reading = meter.last_reading_value if meter else 0.0

        if meter:
            self.old_meter_id = meter
            self.old_meter_number = meter.meter_number
            self.old_meter_type_id = meter.meter_type_id
            self.old_phase = meter.phase
            self.old_last_invo_reading = last_reading
            self.old_closing_reading = last_reading
        
        val = meter.multiplier if meter else 1.0
        self.old_uninvoiced_consumption = max((self.old_closing_reading - self.old_last_invo_reading) * val, 0.0)

    def _get_target_phase(self):
        self.ensure_one()
        if self.target_type == 'feeder':
            return self.feeder_id.phase
        if self.target_type == 'transformer':
            return self.transformer_id.phase
        return self.old_meter_id.phase or self.utility_account_id.meter_id.phase

    @api.constrains('target_type', 'utility_account_id', 'feeder_id', 'transformer_id',
                    'old_meter_id', 'new_meter_id', 'new_meter_model_id', 'new_meter_type_id')
    def _check_target_and_meter_compatibility(self):
        for rec in self:
            target = {
                'subscriber': rec.utility_account_id,
                'feeder': rec.feeder_id,
                'transformer': rec.transformer_id,
            }.get(rec.target_type)
            if target and target.company_id != rec.company_id:
                raise ValidationError(_('العنصر المستهدف وعملية الاستبدال يجب أن ينتميا إلى الشركة نفسها.'))
            phase = rec._get_target_phase()
            if rec.old_meter_id and rec.new_meter_id and rec.old_meter_id == rec.new_meter_id:
                raise UserError(_('يجب اختيار عداد جديد مختلف عن العداد القديم.'))
            if rec.new_meter_id:
                if (not self.env.context.get('in_replacement_execution')
                        and rec.state == 'draft'
                        and rec.new_meter_id.connection_type != 'not_connected'):
                    raise ValidationError(_('العداد الجديد المختار يجب أن يكون غير مرتبط.'))
                if phase and not rec.new_meter_id.phase:
                    raise ValidationError(_('يجب أن يكون للعداد الجديد طور محدد من موديل العداد.'))
                if phase and rec.new_meter_id.phase and rec.new_meter_id.phase != phase:
                    raise ValidationError(_('طور العداد الجديد لا يطابق طور العنصر المستهدف.'))
            if rec.new_meter_model_id:
                if not rec.new_meter_model_id.phase:
                    raise ValidationError(_('موديل العداد الجديد يجب أن يحتوي طورًا فنيًا محددًا.'))
                if phase and rec.new_meter_model_id.phase and rec.new_meter_model_id.phase != phase:
                    raise ValidationError(_('موديل العداد الجديد لا يطابق طور العنصر المستهدف.'))
                if (rec.new_meter_type_id and rec.new_meter_type_id.phase
                        and rec.new_meter_model_id.phase
                        and rec.new_meter_type_id.phase != rec.new_meter_model_id.phase):
                    raise ValidationError(_('نوع العداد الجديد لا يطابق موديل العداد المختار.'))

    @api.onchange('old_meter_serial_scan')
    def _onchange_old_meter_serial_scan(self):
        if self.old_meter_serial_scan:
            meter = self.env['utility.meter'].search(
                self.env['utility.meter']._scan_domain(self.old_meter_serial_scan),
                limit=1)
            if meter:
                if meter.connection_type == 'feeder' and meter.linked_feeder_id:
                    self.target_type = 'feeder'
                    self.feeder_id = meter.linked_feeder_id.id
                    self.old_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم تحديد الفيدر (%s) بناءً على العداد الممسوح.') % meter.linked_feeder_id.name, 'type': 'notification'}}
                elif meter.connection_type == 'transformer' and meter.linked_transformer_id:
                    self.target_type = 'transformer'
                    self.transformer_id = meter.linked_transformer_id.id
                    self.old_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم تحديد المحول (%s) بناءً على العداد الممسوح.') % meter.linked_transformer_id.name, 'type': 'notification'}}
                elif meter.customer_id:
                    self.target_type = 'subscriber'
                    self.utility_account_id = meter.customer_id.id
                    self.old_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم تحديد حساب المشترك (%s) بناءً على العداد الممسوح.') % meter.customer_id.display_name, 'type': 'notification'}}
                else:
                    return {'warning': {'title': _('تنبيه'), 'message': _('العداد الممسوح غير مرتبط بأي حساب أو فيدر أو محول حالياً.')}}
            else:
                return {'warning': {'title': _('غير موجود'), 'message': _('لم يتم العثور على عداد يحمل الرقم: %s') % self.old_meter_serial_scan}}

    @api.onchange('new_meter_serial_scan')
    def _onchange_new_meter_serial_scan(self):
        if self.new_meter_serial_scan:
            meter = self.env['utility.meter'].search(
                self.env['utility.meter']._scan_domain(self.new_meter_serial_scan),
                limit=1)
            if meter:
                if meter.connection_type == 'not_connected' and not meter.customer_id:
                    self.new_meter_id = meter.id
                    self.new_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم اختيار العداد الجديد (%s).') % meter.display_name, 'type': 'notification'}}
                else:
                    return {'warning': {'title': _('مرفوض'), 'message': _('هذا العداد مرتبط بالفعل بعنصر آخر!')}}
            else:
                return {'warning': {'title': _('غير موجود'), 'message': _('العداد %s غير مسجل في المخازن/النظام.') % self.new_meter_serial_scan}}

    @api.constrains('old_closing_reading', 'old_last_invo_reading', 'new_opening_reading')
    def _check_readings_validity(self):
        for rec in self:
            if rec.old_closing_reading < rec.old_last_invo_reading:
                raise ValidationError(_('القراءة الختامية للعداد القديم (%.2f) لا يمكن أن تقل عن آخر قراءة مفوترة (%.2f).') % (rec.old_closing_reading, rec.old_last_invo_reading))
            if rec.new_opening_reading < 0:
                raise ValidationError(_('القراءة الافتتاحية للعداد الجديد لا يمكن أن تكون سالبة.'))

    def action_view_closing_reading(self):
        self.ensure_one()
        if not self.closing_reading_id:
            raise UserError(_('لا توجد قراءة ختامية مرتبطة بهذا الاستبدال.'))
        return {
            'name': _('القراءة الختامية للعداد القديم'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reading',
            'res_id': self.closing_reading_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_opening_reading(self):
        self.ensure_one()
        if not self.opening_reading_id:
            raise UserError(_('لا توجد قراءة افتتاحية مرتبطة بهذا الاستبدال.'))
        return {
            'name': _('القراءة الافتتاحية للعداد الجديد'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reading',
            'res_id': self.opening_reading_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _action_confirm_replacement_unified(self):
        """Complete replacement and create auditable closing/opening readings for Subscribers, Feeders, or Transformers."""
        self = self.with_context(in_replacement_execution=True)
        for rec in self:
            if rec.state == 'done':
                continue

            account = False
            feeder = False
            transformer = False
            old_meter = rec.old_meter_id

            if rec.target_type == 'subscriber':
                account = rec.utility_account_id
                if not account:
                    raise UserError(_('يجب تحديد حساب المشترك أولاً.'))
                old_meter = old_meter or account.meter_id
                if not old_meter:
                    raise UserError(_('حساب المشترك المختار [%s] لا يملك عداداً فعالاً في النظام.') % account.display_name)
            elif rec.target_type == 'feeder':
                feeder = rec.feeder_id
                if not feeder:
                    raise UserError(_('يجب تحديد الفيدر / الخلية أولاً.'))
                old_meter = old_meter or feeder.coupling_meter_id
                if not old_meter:
                    raise UserError(_('الفيدر المختار [%s] لا يملك عداد مقارنة ورصد فعال.') % feeder.name)
            elif rec.target_type == 'transformer':
                transformer = rec.transformer_id
                if not transformer:
                    raise UserError(_('يجب تحديد المحول أولاً.'))
                old_meter = old_meter or transformer.coupling_meter_id
                if not old_meter:
                    raise UserError(_('المحول المختار [%s] لا يملك عداد مقارنة ورصد فعال.') % transformer.name)

            new_meter = rec.new_meter_id
            if not new_meter and rec.new_meter_number:
                if not rec.new_meter_model_id:
                    raise UserError(_('يجب تحديد موديل العداد الجديد حتى يكون طوره مصدرًا فنيًا موثوقًا.'))
                meter_vals = {
                    'meter_number': rec.new_meter_number,
                    'model_id': rec.new_meter_model_id.id,
                    'meter_type_id': rec.new_meter_type_id.id if rec.new_meter_type_id else False,
                    'installation_date': rec.replace_date.date(),
                    'company_id': rec.company_id.id,
                    'multiplier': rec.new_meter_val or 1.0,
                }
                if rec.target_type == 'subscriber':
                    meter_vals['connection_type'] = 'subscriber'
                elif rec.target_type == 'feeder':
                    meter_vals['connection_type'] = 'feeder'
                    meter_vals['is_coupling_meter'] = True
                    meter_vals['linked_feeder_id'] = feeder.id
                elif rec.target_type == 'transformer':
                    meter_vals['connection_type'] = 'transformer'
                    meter_vals['is_coupling_meter'] = True
                    meter_vals['linked_transformer_id'] = transformer.id

                new_meter = self.env['utility.meter'].create(meter_vals)
                rec.new_meter_id = new_meter

            prev_reading = rec.old_last_invo_reading
            if not prev_reading and account:
                prev_reading = account.last_invoice_reading or account.last_reading_value or 0.0
            elif not prev_reading and old_meter:
                prev_reading = old_meter.last_reading_value or 0.0
            if not rec.old_last_invo_reading and prev_reading:
                rec.old_last_invo_reading = prev_reading

            if rec.old_closing_reading < prev_reading:
                raise UserError(_('القراءة الختامية لا يمكن أن تقل عن آخر قراءة مفوترة.'))

            Reading = self.env['utility.reading'].with_context(_bypass_reading_protection=True)

            # Build Closing Reading
            closing_vals = {
                'company_id': rec.company_id.id,
                'meter_id': old_meter.id,
                'reading_date': rec.replace_date,
                'reading_value': rec.old_closing_reading,
                'previous_reading': prev_reading,
                'previous_reading_date': (account.last_invoice_date if account else False) or rec.replace_date,
                'meter_multiplier': old_meter.multiplier or 1.0,
                'reading_type': 'manual',
                'reading_purpose': 'replacement_closing',
                'reading_event': 'replacement',
                'replacement_id': rec.id,
                'state': 'approved',
                'remarks': _('قراءة إغلاق بسبب استبدال العداد بالعملية %s') % rec.display_name,
            }

            if rec.target_type == 'subscriber':
                closing_vals['reading_category'] = 'customer'
                closing_vals['account_id'] = account.id
            elif rec.target_type == 'feeder':
                closing_vals['reading_category'] = 'feeder'
                closing_vals['feeder_id'] = feeder.id
            elif rec.target_type == 'transformer':
                closing_vals['reading_category'] = 'transformer'
                closing_vals['transformer_id'] = transformer.id
                if transformer.feeder_id:
                    closing_vals['feeder_id'] = transformer.feeder_id.id

            closing = Reading.create(closing_vals)

            if closing.consumption < 0:
                raise UserError(_('القراءة الختامية أقل من آخر قراءة صحيحة للعداد القديم.'))

            # Detach Old Meter & Attach New Meter
            if rec.target_type == 'subscriber':
                old_meter.write({'customer_id': False, 'active': False})
                new_meter.write({'customer_id': account.id, 'multiplier': rec.new_meter_val, 'active': True, 'connection_type': 'subscriber'})
                old_assignment = account.current_meter_assignment_id
                if old_assignment:
                    old_assignment.action_close(
                        final_reading=rec.old_closing_reading,
                        reason=rec.reason,
                        notes=rec.notes)
                account.with_context(lifecycle_operation=True).write({
                    'meter_id': new_meter.id,
                    'last_reading_value': rec.new_opening_reading,
                })
                self.env['utility.customer.meter.assignment'].create({
                    'customer_id': account.id,
                    'meter_id': new_meter.id,
                    'company_id': account.company_id.id,
                    'date_from': rec.replace_date,
                    'initial_reading': rec.new_opening_reading,
                    'assignment_type': 'replacement',
                    'reason': rec.reason,
                    'notes': rec.notes,
                })
                account._log_lifecycle_event(
                    'meter_replaced', reason=rec.reason, notes=rec.notes,
                    old_meter=old_meter, new_meter=new_meter)
            elif rec.target_type == 'feeder':
                old_meter.write({'linked_feeder_id': False, 'active': False})
                new_meter.write({'linked_feeder_id': feeder.id, 'multiplier': rec.new_meter_val, 'active': True, 'connection_type': 'feeder', 'is_coupling_meter': True})
                feeder.write({'coupling_meter_id': new_meter.id})
            elif rec.target_type == 'transformer':
                old_meter.write({'linked_transformer_id': False, 'active': False})
                new_meter.write({'linked_transformer_id': transformer.id, 'multiplier': rec.new_meter_val, 'active': True, 'connection_type': 'transformer', 'is_coupling_meter': True})
                transformer.write({'coupling_meter_id': new_meter.id})

            # Build Opening Reading
            opening_vals = {
                'company_id': rec.company_id.id,
                'meter_id': new_meter.id,
                'reading_date': rec.replace_date,
                'reading_value': rec.new_opening_reading,
                'previous_reading': rec.new_opening_reading,
                'previous_reading_date': rec.replace_date,
                'meter_multiplier': rec.new_meter_val or 1.0,
                'reading_type': 'manual',
                'reading_purpose': 'opening',
                'reading_event': 'replacement',
                'replacement_id': rec.id,
                'state': 'approved',
                'is_initial_reading': True,
                'remarks': _('قراءة افتتاحية بسبب استبدال العداد بالعملية %s') % rec.display_name,
            }

            if rec.target_type == 'subscriber':
                opening_vals['reading_category'] = 'customer'
                opening_vals['account_id'] = account.id
            elif rec.target_type == 'feeder':
                opening_vals['reading_category'] = 'feeder'
                opening_vals['feeder_id'] = feeder.id
            elif rec.target_type == 'transformer':
                opening_vals['reading_category'] = 'transformer'
                opening_vals['transformer_id'] = transformer.id
                if transformer.feeder_id:
                    opening_vals['feeder_id'] = transformer.feeder_id.id

            opening = Reading.create(opening_vals)

            self.env['utility.meter.log']._create_log(old_meter, 'removal', _('رفع العداد %s واستبداله بـ %s') % (old_meter.meter_number, new_meter.meter_number), ref_record=rec)
            self.env['utility.meter.log']._create_log(new_meter, 'replacement', _('تركيب العداد %s') % new_meter.meter_number, ref_record=rec)

            rec.write({'closing_reading_id': closing.id, 'opening_reading_id': opening.id, 'old_meter_id': old_meter.id, 'state': 'done'})
        return True

    def action_confirm_replacement(self):
        """Run the unified replacement workflow from the core form."""
        return self._action_confirm_replacement_unified()
