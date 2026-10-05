from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityFeeder(models.Model):
    _name = 'utility.feeder'
    _description = 'مغذٍ (خلية)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم الفيدر / الخلية', required=True, tracking=True)
    code = fields.Char('الرمز', required=True)
    feeder_type = fields.Selection([
        ('distribution', 'توزيع'),
        ('production_area', 'منطقة إنتاج'),
    ], string='نوع الفيدر', required=True, default='distribution', index=True,
       tracking=True)

    # ===== الموقع في الشبكة =====
    substation_id = fields.Many2one('utility.substation', 'المحطة', index=True)
    region_id = fields.Many2one('utility.region', 'المنطقة', domain="[('type', '=', 'region')]", tracking=True)
    area_id = fields.Many2one(
        'utility.region', 'المنطقة الفرعية / الفرع',
        domain="[('type', '=', 'area'), ('parent_id', '=', region_id)]",
        tracking=True,
    )

    # ===== المواصفات الكهربائية =====
    voltage_level = fields.Selection([
        ('lv', 'جهد منخفض (LV)'),
        ('mv', 'جهد متوسط (MV)'),
        ('hv', 'جهد عالي (HV)'),
    ], string='مستوى الجهد')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور', tracking=True,
       help='الطور التشغيلي للفيدر. لا يمكن ربطه بعداد بطور مختلف.')
    rated_capacity = fields.Float('الطاقة الاسمية (kVA)')
    current_load = fields.Float('الحمل الحالي (kVA)')
    load_percentage = fields.Float('نسبة التحميل %', compute='_compute_load_percentage', store=True)

    # ===== العدادات =====
    coupling_meter_id = fields.Many2one(
        'utility.meter', 'عداد الربط (المقارنة والرصد)',
        domain="[('feeder_id', '=', id)]",
        help='العداد الذي يقيس إجمالي الطاقة الداخلة إلى المحول أو الفيدر',
        tracking=True,
    )
    transformer_ids = fields.One2many('utility.transformer', 'feeder_id', string='المحولات')
    meter_ids = fields.One2many('utility.meter', 'feeder_id', string='جميع العدادات')

    # ===== القراءات =====
    coupling_reading_ids = fields.One2many(
        'utility.reading', 'feeder_id',
        string='قراءات الربط',
        domain=[('reading_category', 'in', ['feeder', 'transformer'])],
    )
    feeder_reading_ids = fields.One2many(
        'utility.reading', 'feeder_id',
        string='قراءات الفيدر',
        domain=[('reading_category', '=', 'feeder')],
    )

    # ===== الأرصدة والفاقد =====
    transformer_count = fields.Integer(
        'عدد المحولات',
        compute='_compute_feeder_stats', store=True
    )
    supplied_kwh = fields.Float(
        'الطاقة المزوّدة (kWh)',
        compute='_compute_feeder_stats', store=True
    )

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_feeder_code_substation', 'unique(code, company_id)', 'رمز الفيدر يجب أن يكون فريداً!'),
    ]

    # ===== Onchange =====
    @api.onchange('substation_id')
    def _onchange_substation_id(self):
        if self.substation_id:
            self.company_id = self.substation_id.company_id

    @api.onchange('region_id')
    def _onchange_region_id_clear_foreign_area(self):
        if self.region_id and self.area_id and self.area_id.parent_id != self.region_id:
            self.area_id = False

    @api.constrains('region_id', 'area_id')
    def _check_region_area_consistency(self):
        for feeder in self:
            if feeder.region_id and feeder.area_id and feeder.area_id.parent_id != feeder.region_id:
                raise ValidationError(_(
                    'الفرع "%s" لا يتبع المنطقة "%s".'
                ) % (feeder.area_id.display_name, feeder.region_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            station_id = vals.get('substation_id')
            if station_id:
                station = self.env['utility.substation'].browse(station_id)
                vals.setdefault('company_id', station.company_id.id)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('substation_id'):
            station = self.env['utility.substation'].browse(vals['substation_id'])
            vals['company_id'] = station.company_id.id
        return super().write(vals)

    @api.constrains('substation_id', 'company_id', 'coupling_meter_id')
    def _check_network_consistency(self):
        for feeder in self:
            station = feeder.substation_id
            if station:
                if station.company_id != feeder.company_id:
                    raise ValidationError(_('شركة الفيدر يجب أن تطابق شركة المحطة.'))
            meter = feeder.coupling_meter_id
            if meter and (meter.connection_type != 'feeder' or meter.linked_feeder_id != feeder):
                raise ValidationError(_('عداد الربط يجب أن يكون عداد فيدر مرتبطًا بهذا الفيدر نفسه.'))

    # ===== Compute =====
    @api.depends('current_load', 'rated_capacity')
    def _compute_load_percentage(self):
        for r in self:
            if r.rated_capacity:
                r.load_percentage = (r.current_load / r.rated_capacity) * 100.0
            else:
                r.load_percentage = 0.0

    @api.depends('transformer_ids', 'coupling_reading_ids.consumption')
    def _compute_feeder_stats(self):
        for rec in self:
            rec.transformer_count = len(rec.transformer_ids)

            last_coupling = rec.coupling_reading_ids.filtered(
                lambda r: r.state == 'approved'
            )[:1]
            rec.supplied_kwh = last_coupling.consumption if last_coupling else 0.0

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('قراءات %s') % self.name,
            'res_model': 'utility.reading',
            'domain': [('feeder_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
            'context': {
                'default_feeder_id': self.id,
                'default_reading_category': 'feeder',
            },
        }

    def action_view_meters(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('عدادات %s') % self.name,
            'res_model': 'utility.meter',
            'domain': [('feeder_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
            'context': {'default_feeder_id': self.id},
        }
