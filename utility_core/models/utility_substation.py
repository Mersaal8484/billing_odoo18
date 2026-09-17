from odoo import api, fields, models


class UtilitySubstation(models.Model):
    _name = 'utility.substation'
    _description = 'محطة فرعية'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المحطة', required=True)
    code = fields.Char('رمز المحطة', required=True)
    voltage_level = fields.Selection([
        ('lv', 'جهد منخفض'),
        ('mv', 'جهد متوسط'),
        ('hv', 'جهد عالي'),
    ], string='مستوى الجهد')
    capacity_kva = fields.Float('القدرة (kVA)')
    address = fields.Text('العنوان')
    status = fields.Selection([
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('fault', 'عطل'),
        ('maintenance', 'صيانة'),
    ], string='الحالة', default='active')
    feeder_ids = fields.One2many('utility.feeder', 'substation_id', string='المغذيات')
    transformer_ids = fields.One2many('utility.transformer', 'substation_id', string='المحولات')

    _sql_constraints = [
        ('unique_substation_code_company', 'unique(code, company_id)', 'رمز المحطة يجب أن يكون فريداً لكل شركة!'),
    ]
