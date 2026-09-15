from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from .utility_date_range import BILLING_PERIOD_TYPES, normalize_billing_cadence


class UtilityRegion(models.Model):
    _name = 'utility.region'
    _description = 'منطقة'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('الاسم', required=True, index=True)
    code = fields.Char('الرمز', required=True, index=True)
    
    type = fields.Selection([
        ('region', 'منطقة'),
        ('area', 'منطقة فرعية'),
        ('zone', 'منطقة تفصيلية'),
    ], string='النوع', default='region', required=True)
    
    parent_id = fields.Many2one('utility.region', string='العنصر الأب', index=True, ondelete='cascade')
    child_ids = fields.One2many('utility.region', 'parent_id', string='العناصر الفرعية')
    
    area_ids = fields.One2many('utility.region', 'parent_id', string='المناطق', domain=[('type', '=', 'area')])
    zone_ids = fields.One2many('utility.region', 'parent_id', string='النواحي', domain=[('type', '=', 'zone')])
    
    area_count = fields.Integer('عدد المناطق الفرعية', compute='_compute_area_count', store=True)
    zone_count = fields.Integer('عدد المناطق التفصيلية', compute='_compute_zone_count', store=True)
    recurring_rule_type = fields.Selection(
        BILLING_PERIOD_TYPES,
        string='نوع دورة الفوترة',
        default='monthly',
        required=True
    )
    
    cash_journal_id = fields.Many2one('account.journal', string='يومية الصندوق', domain=[('type', '=', 'cash')], help='يومية الصندوق الخاصة بهذه المنطقة')
    bank_journal_ids = fields.Many2many(
        'account.journal', 
        'utility_region_bank_journal_rel', 
        'region_id', 
        'journal_id', 
        string='الحسابات البنكية', 
        domain=[('type', '=', 'bank')],
        help='اليوميات البنكية التابعة لهذه المنطقة'
    )
    financial_manager_id = fields.Many2one('res.users', string='المدير المالي للمنطقة', help='المسؤول المالي عن هذه المنطقة')

    transformer_origin_id = fields.Many2one(
        'utility.transformer', 'المحول المرتبط (1:1)',
        readonly=True, copy=False, ondelete='restrict', index=True,
        help='التمثيل الفني الواحد-لواحد للـZone. يُدار من سجل المحول.'
    )
    private_transformer_id = fields.Many2one(
        'utility.transformer', 'المحول الخاص',
        domain="[('is_private', '=', True), ('company_id', '=', company_id)]",
        ondelete='restrict',
        help='ربط جغرافي وصفي لا ينقل ملكية الحساب الكهربائي.')

    _sql_constraints = [
        ('unique_code_parent_company', 'unique(code, parent_id, company_id)', 'الرمز يجب أن يكون فريداً لكل عنصر أب/شركة!'),
        ('unique_zone_transformer_origin', 'unique(transformer_origin_id)',
         'لا يمكن ربط أكثر من Zone واحد بنفس المحول.'),
    ]

    @api.depends('area_ids')
    def _compute_area_count(self):
        for r in self:
            r.area_count = len(r.area_ids)

    @api.depends('zone_ids')
    def _compute_zone_count(self):
        for r in self:
            r.zone_count = len(r.zone_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('parent_id') and not vals.get('recurring_rule_type'):
                parent = self.browse(vals['parent_id'])
                if parent.exists() and parent.recurring_rule_type:
                    vals['recurring_rule_type'] = parent.recurring_rule_type
        return super().create(vals_list)

    @api.onchange('parent_id')
    def _onchange_parent_id_inherit_cadence(self):
        if self.parent_id and self.parent_id.recurring_rule_type:
            self.recurring_rule_type = normalize_billing_cadence(self.parent_id.recurring_rule_type)

    @api.constrains('parent_id', 'recurring_rule_type')
    def _check_parent_cadence_consistency(self):
        for r in self:
            if r.parent_id:
                root = r
                while root.parent_id:
                    root = root.parent_id
                if normalize_billing_cadence(root.recurring_rule_type) != normalize_billing_cadence(r.recurring_rule_type):
                    raise ValidationError(_(
                        "دورية الفوترة للمنطقة الفرعية '%s' (%s) يجب أن تطابق دورية المنطقة الرئيسية '%s' (%s)."
                    ) % (r.name, r.recurring_rule_type, root.name, root.recurring_rule_type))

    @api.constrains('type', 'private_transformer_id')
    def _check_private_transformer_context(self):
        for region in self.filtered('private_transformer_id'):
            if region.type != 'zone':
                raise ValidationError(_('المحول الخاص يمكن ربطه بالناحية من نوع zone فقط.'))
            transformer = region.private_transformer_id
            if not transformer.is_private:
                raise ValidationError(_('لا يمكن اختيار إلا محول مصنفًا كمحول خاص.'))
            if transformer.company_id != region.company_id:
                raise ValidationError(_('شركة المحول الخاص يجب أن تطابق شركة الناحية.'))
            if transformer.zone_region_id and transformer.zone_region_id != region:
                raise ValidationError(_('المحول الخاص لا ينتمي إلى الناحية المحددة.'))

    @api.constrains('type', 'transformer_origin_id', 'company_id')
    def _check_transformer_origin_link(self):
        for region in self.filtered('transformer_origin_id'):
            transformer = region.transformer_origin_id
            if region.type != 'zone':
                raise ValidationError(_('يمكن ربط المحول بكيان جغرافي من نوع Zone فقط.'))
            if transformer.company_id != region.company_id:
                raise ValidationError(_('شركة المحول المرتبط يجب أن تطابق شركة الـZone.'))
            if transformer.zone_region_id != region:
                raise ValidationError(
                    _('يجب أن يشير المحول المرتبط إلى الـZone نفسه لضمان العلاقة واحد-لواحد.')
                )

    def action_migrate_biweekly_to_semi_monthly(self):
        """ميجريشن تصحيحي لجميع المناطق الفرعية والرئيسية لتحويل biweekly إلى semi_monthly"""
        biweekly_regions = self.search([('recurring_rule_type', '=', 'biweekly')])
        biweekly_regions.write({'recurring_rule_type': 'semi_monthly'})
        return len(biweekly_regions)
