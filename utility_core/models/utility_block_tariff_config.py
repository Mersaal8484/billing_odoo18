from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare


class UtilityBlockTariffConfig(models.Model):
    """Reusable tariff settings; applying one creates customer-local copies."""

    _name = 'utility.block.tariff.config'
    _description = 'إعداد شرائح التعرفة'
    _order = 'company_id, billing_cycle, state, name, id'

    name = fields.Char(string='الاسم', required=True)
    company_id = fields.Many2one('res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='العملة', readonly=True)
    billing_cycle = fields.Selection(
        [('semi_monthly', 'نصف شهري'), ('monthly', 'شهري')],
        string='دورية الفوترة', required=True, index=True)
    state = fields.Selection([('draft', 'مسودة'), ('active', 'نشط')],
        string='الحالة', required=True, default='draft', index=True)
    notes = fields.Text(string='ملاحظات')
    line_ids = fields.One2many('utility.block.tariff.config.line', 'config_id',
        string='الشرائح', copy=True)

    def _validate_block_layout(self, require_complete=False):
        for config in self:
            lines = config.line_ids.sorted(key=lambda line: (line.from_kwh, line.sequence, line.id))
            if not lines:
                if require_complete:
                    raise ValidationError(_('يجب إضافة شريحة واحدة على الأقل.'))
                continue
            expected_from = 0.0
            for index, line in enumerate(lines):
                if float_compare(line.from_kwh, expected_from, precision_digits=6):
                    raise ValidationError(_(
                        'الشرائح في الإعداد "%(config)s" يجب أن تبدأ من %(expected)s kWh بدون فجوات أو تداخل.'
                    ) % {'config': config.display_name, 'expected': expected_from})
                if not line.to_kwh:
                    if index != len(lines) - 1:
                        raise ValidationError(_('الشريحة المفتوحة يجب أن تكون آخر شريحة في إعداد التعرفة.'))
                    continue
                if float_compare(line.to_kwh, line.from_kwh, precision_digits=6) <= 0:
                    raise ValidationError(_('يجب أن يكون حد نهاية الشريحة أكبر من حد بدايتها.'))
                expected_from = line.to_kwh
            if require_complete and lines[-1].to_kwh:
                raise ValidationError(_('يجب أن تنتهي التعرفة بشريحة مفتوحة (ضع حد النهاية 0).'))

    @api.constrains('state')
    def _check_active_layout(self):
        self.filtered(lambda config: config.state == 'active')._validate_block_layout(require_complete=True)

    def write(self, vals):
        protected = {'name', 'company_id', 'billing_cycle', 'notes', 'line_ids'}
        if protected.intersection(vals) and self.filtered(lambda config: config.state == 'active'):
            raise UserError(_('لا يمكن تعديل إعداد تعرفة نشط. أعده إلى المسودة أولاً ثم عدّل الشرائح.'))
        return super().write(vals)

    def action_activate(self):
        self._validate_block_layout(require_complete=True)
        self.write({'state': 'active'})
        return True

    def action_set_draft(self):
        self.write({'state': 'draft'})
        return True


class UtilityBlockTariffConfigLine(models.Model):
    _name = 'utility.block.tariff.config.line'
    _description = 'شريحة إعداد التعرفة'
    _order = 'config_id, from_kwh, sequence, id'

    config_id = fields.Many2one('utility.block.tariff.config', string='إعداد التعرفة', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='config_id.company_id', store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related='config_id.currency_id', readonly=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='اسم الشريحة', required=True)
    from_kwh = fields.Float(string='من (kWh)', required=True, default=0.0)
    to_kwh = fields.Float(string='إلى (kWh)', default=0.0, help='اتركه 0 للشريحة المفتوحة الأخيرة.')
    price_per_kwh = fields.Monetary(string='سعر kWh', required=True, currency_field='currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        configs = self.env['utility.block.tariff.config'].browse(
            {vals['config_id'] for vals in vals_list if vals.get('config_id')})
        if configs.filtered(lambda config: config.state == 'active'):
            raise UserError(_('أعد إعداد التعرفة إلى المسودة قبل إضافة أو تعديل الشرائح.'))
        return super().create(vals_list)

    def _ensure_config_is_draft(self, vals=None):
        configs = self.mapped('config_id')
        if vals and vals.get('config_id'):
            configs |= self.env['utility.block.tariff.config'].browse(vals['config_id'])
        if configs.filtered(lambda config: config.state == 'active'):
            raise UserError(_('أعد إعداد التعرفة إلى المسودة قبل إضافة أو تعديل الشرائح.'))

    def write(self, vals):
        self._ensure_config_is_draft(vals)
        return super().write(vals)

    def unlink(self):
        self._ensure_config_is_draft()
        return super().unlink()

    @api.constrains('config_id', 'from_kwh', 'to_kwh', 'price_per_kwh')
    def _check_values_and_overlap(self):
        for line in self:
            if line.from_kwh < 0 or line.to_kwh < 0 or line.price_per_kwh < 0:
                raise ValidationError(_('لا يمكن أن تحتوي الشريحة على قيم سالبة.'))
            if line.to_kwh and float_compare(line.to_kwh, line.from_kwh, precision_digits=6) <= 0:
                raise ValidationError(_('يجب أن يكون حد نهاية الشريحة أكبر من حد بدايتها.'))
            for other in line.config_id.line_ids - line:
                line_end = line.to_kwh or float('inf')
                other_end = other.to_kwh or float('inf')
                if line.from_kwh < other_end and other.from_kwh < line_end:
                    raise ValidationError(_(
                        'الشريحة "%(line)s" تتداخل مع شريحة أخرى في الإعداد. تأكد من عدم تداخل نطاقات kWh.'
                    ) % {'line': line.display_name})


class UtilityCustomerBlockLine(models.Model):
    """Immutable local copy of a central tariff for one utility customer."""

    _name = 'utility.customer.block.line'
    _description = 'شريحة تعرفة محلية للعميل'
    _order = 'customer_id, from_kwh, sequence, id'

    customer_id = fields.Many2one('utility.customer', string='العميل الكهربائي', required=True,
        ondelete='cascade', index=True, check_company=True)
    source_config_id = fields.Many2one('utility.block.tariff.config', string='إعداد التعرفة المصدر',
        readonly=True, ondelete='set null', index=True, check_company=True)
    company_id = fields.Many2one(related='customer_id.company_id', store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    billing_cycle = fields.Selection([('semi_monthly', 'نصف شهري'), ('monthly', 'شهري')],
        string='دورية الفوترة', required=True, readonly=True, index=True)
    sequence = fields.Integer(readonly=True)
    name = fields.Char(string='اسم الشريحة', required=True, readonly=True)
    from_kwh = fields.Float(string='من (kWh)', required=True, readonly=True)
    to_kwh = fields.Float(string='إلى (kWh)', readonly=True)
    price_per_kwh = fields.Monetary(string='سعر kWh', required=True, readonly=True,
        currency_field='currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('_allow_customer_tariff_block_mutation'):
            raise AccessError(_(
                'لا يمكن إنشاء الشرائح المحلية يدويًا. استخدم إجراء «تحديث التعرفة» من بطاقة العميل.'
            ))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('_allow_customer_tariff_block_mutation'):
            raise AccessError(_(
                'لا يمكن تعديل الشرائح المحلية يدويًا. أعد تطبيق إعداد التعرفة من بطاقة العميل.'
            ))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('_allow_customer_tariff_block_mutation'):
            raise AccessError(_(
                'لا يمكن حذف الشرائح المحلية يدويًا. أعد تطبيق إعداد التعرفة من بطاقة العميل.'
            ))
        return super().unlink()
