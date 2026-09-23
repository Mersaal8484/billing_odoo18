from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMigrationMapping(models.Model):
    _name = 'utility.migration.mapping'
    _description = 'جدول ترميز البيانات'
    _rec_name = 'legacy_code'

    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)

    mapping_type = fields.Selection([
        ('region', 'المنطقة'),
        ('area', 'الفرع'),
        ('category', 'الفئة'),
        ('subscriber', 'نوع المشترك'),
        ('contract', 'قالب العقد'),
    ], string='نوع الترميز', required=True, index=True)

    legacy_code = fields.Char('الرمز القديم', required=True, index=True)

    # Odoo References
    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)', domain="[('type', '=', 'area')]")
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (Odoo)')
    subscriber_type_id = fields.Many2one('utility.subscriber', string='نوع المشترك (Odoo)')
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد (Odoo)')

    _sql_constraints = [
        ('unique_mapping', 'unique(company_id, mapping_type, legacy_code)',
         'لا يمكن تكرار نفس الرمز القديم لنفس النوع لنفس الشركة!')
    ]

    @api.onchange('mapping_type')
    def _onchange_mapping_type(self):
        self.region_id = False
        self.area_id = False
        self.category_id = False
        self.subscriber_type_id = False
        self.contract_template_id = False

    @api.constrains('company_id', 'mapping_type', 'region_id', 'area_id', 'category_id', 'subscriber_type_id', 'contract_template_id')
    def _check_mapping_target(self):
        for rec in self:
            targets = {
                'region': rec.region_id,
                'area': rec.area_id,
                'category': rec.category_id,
                'subscriber': rec.subscriber_type_id,
                'contract': rec.contract_template_id,
            }
            target_val = targets.get(rec.mapping_type)
            if not target_val:
                raise ValidationError(_('يجب تحديد التعيين المطلوب (Target) لنوع الترميز "%s".') % rec.mapping_type)

            # Enforce that all other 4 target fields are EMPTY
            other_targets = [val for k, val in targets.items() if k != rec.mapping_type and val]
            if other_targets:
                raise ValidationError(_('يجب تحديد تعيين واحد فقط (Target) يطابق نوع الترميز المطابق (%s).') % rec.mapping_type)

            # Enforce target company consistency where target has company_id
            if hasattr(target_val, 'company_id') and target_val.company_id and target_val.company_id != rec.company_id:
                raise ValidationError(_('الهدف المحدد (Target) تابع لشركة (%s) يختلف عن شركة جدول الترميز (%s).') % (
                    target_val.company_id.name, rec.company_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('legacy_code'):
                vals['legacy_code'] = vals['legacy_code'].strip()
        
        if self.env.context.get('install_mode') or self.env.context.get('install_module'):
            import psycopg2
            records = self.env['utility.migration.mapping']
            for vals in vals_list:
                try:
                    with self.env.cr.savepoint():
                        records |= super().create([vals])
                except psycopg2.errors.UniqueViolation:
                    existing = self.search([
                        ('company_id', '=', vals.get('company_id', self.env.company.id)),
                        ('mapping_type', '=', vals.get('mapping_type')),
                        ('legacy_code', '=', vals.get('legacy_code')),
                    ], limit=1)
                    if existing:
                        records |= existing
                    else:
                        raise
            return records

        return super().create(vals_list)

    def write(self, vals):
        if 'legacy_code' in vals and vals['legacy_code']:
            vals['legacy_code'] = vals['legacy_code'].strip()
        return super().write(vals)

    @api.model
    def get_mapping_cache(self, company_id):
        """إرجاع ذاكرة تخزين مؤقت (In-Memory Cache) لخرائط الترميز للشركة المحددة."""
        mappings = self.search([('company_id', '=', company_id)])
        cache = {}
        for m in mappings:
            code = (m.legacy_code or '').strip()
            key = (m.mapping_type, code)
            if m.mapping_type == 'region':
                cache[key] = m.region_id
            elif m.mapping_type == 'area':
                cache[key] = m.area_id
            elif m.mapping_type == 'category':
                cache[key] = m.category_id
            elif m.mapping_type == 'subscriber':
                cache[key] = m.subscriber_type_id
            elif m.mapping_type == 'contract':
                cache[key] = m.contract_template_id
        return cache
