from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityTeam(models.Model):
    _name = 'utility.team'
    _description = 'فريق عمل'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم الفريق', required=True)
    code = fields.Char('رمز الفريق', required=True)
    team_leader_id = fields.Many2one('utility.staff', 'قائد الفريق')
    region_id = fields.Many2one(
        'utility.region', 'المنطقة',
        domain="[('type', '=', 'region')]",
        index=True,
    )
    area_id = fields.Many2one(
        'utility.region', 'المنطقة الفرعية',
        domain="[('type', '=', 'area'), ('parent_id', '=', region_id)]",
    )
    staff_ids = fields.One2many('utility.staff', 'team_id', string='الأعضاء')
    member_count = fields.Integer('عدد الأعضاء', compute='_compute_member_count', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('area_id') and not vals.get('region_id'):
                area = self.env['utility.region'].browse(vals['area_id'])
                vals['region_id'] = area.parent_id.id
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('area_id') and 'region_id' not in vals:
            area = self.env['utility.region'].browse(vals['area_id'])
            vals['region_id'] = area.parent_id.id
        elif 'region_id' in vals and 'area_id' not in vals:
            new_region = self.env['utility.region'].browse(vals['region_id'])
            if any(team.area_id and team.area_id.parent_id != new_region for team in self):
                vals['area_id'] = False
        return super().write(vals)

    @api.onchange('area_id')
    def _onchange_area_id_set_region(self):
        if self.area_id:
            self.region_id = self.area_id.parent_id

    @api.onchange('region_id')
    def _onchange_region_id_clear_area(self):
        if self.area_id and self.area_id.parent_id != self.region_id:
            self.area_id = False

    @api.constrains('region_id', 'area_id')
    def _check_area_belongs_to_region(self):
        for team in self:
            if not team.region_id or team.region_id.type != 'region':
                raise ValidationError(_('يجب تحديد منطقة رئيسية للفريق.'))
            if team.area_id and (
                team.area_id.type != 'area' or team.area_id.parent_id != team.region_id
            ):
                raise ValidationError(_('يجب أن تكون المنطقة الفرعية تابعة للمنطقة المحددة للفريق.'))

    @api.depends('staff_ids')
    def _compute_member_count(self):
        for r in self:
            r.member_count = len(r.staff_ids)
