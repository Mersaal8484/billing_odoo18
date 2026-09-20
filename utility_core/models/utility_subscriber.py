from odoo import api, fields, models, _

class UtilitySubscriber(models.Model):
    _name = 'utility.subscriber'
    _description = 'مشترك'
    _order = 'sequence, code'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الكود', required=True)
    sequence = fields.Integer('الترتيب', default=10)
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة الرئيسية', required=True, ondelete='restrict')

    # الخصم المدعوم
    subsidized_enabled = fields.Boolean('تفعيل الخصم المدعوم', default=False)
    sponsor_id = fields.Many2one(
        'res.partner', string='الجهة الداعمة',
        domain="[('utility_partner_type', '=', 'donor')]",
        help='الجهة التي سيتم تقييد قيمة الخصم كمديونية عليها')
    subsidized_max_units = fields.Float('الحد الأقصى للوحدات المدعومة', default=100.0)
    subsidized_percentage = fields.Float('نسبة الدعم (%)', default=100.0)
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    subsidized_price_per_kwh = fields.Monetary('سعر الوحدة المدعومة', currency_field='currency_id')

    # إعدادات الحسابات المحاسبية
    subsidy_account_id = fields.Many2one('account.account', 'حساب مصروف الدعم')
    revenue_account_id = fields.Many2one('account.account', 'حساب الإيراد')

    # إعدادات الفوترة

    default_contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد الافتراضي')

    description = fields.Text('الوصف')
    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_unique_per_company', 'unique(code, company_id)',
         'كود المشترك يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.depends('category_id.name', 'name', 'code')
    def _compute_display_name(self):
        for rec in self:
            name = f"[{rec.code}] {rec.name}"
            if rec.category_id:
                name = f"{rec.category_id.name} / {name}"
            rec.display_name = name

    def _get_subsidized_amount(self, consumption, tariff):
        """حساب مبلغ الخصم المدعوم حسب النوع والاستهلاك"""
        self.ensure_one()
        if not self.subsidized_enabled or consumption <= 0:
            return (0.0, 0.0, '')

        subsidized_units = min(consumption, self.subsidized_max_units)

        if self.subsidized_price_per_kwh:
            unit_price = -abs(self.subsidized_price_per_kwh)
        elif tariff and tariff.price_per_kwh:
            discount_price = tariff.price_per_kwh * (self.subsidized_percentage / 100.0)
            unit_price = -abs(discount_price)
        else:
            unit_price = -130.0

        return (subsidized_units, unit_price, f'خصم استهلاك مدعوم - {subsidized_units} وحدة')
