from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityCustomerWizardInventory(models.TransientModel):
    _inherit = 'utility.customer.wizard'

    available_meter_product_ids = fields.Many2many(
        'product.product', compute='_compute_available_meter_product_ids',
        string='منتجات العدادات المتاحة')
    meter_product_id = fields.Many2one('product.product', string='منتج العداد')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial للعداد')

    @api.depends('create_meter')
    def _compute_available_meter_product_ids(self):
        products = self.env['product.product'].search([
            ('tracking', '=', 'serial'),
            ('type', '=', 'consu'),
        ])
        for wizard in self:
            wizard.available_meter_product_ids = products

    @api.onchange('meter_product_id')
    def _onchange_meter_product_id_inventory(self):
        for wizard in self:
            wizard.lot_id = False
        return {
            'domain': {
                'meter_product_id': [('id', 'in', self.available_meter_product_ids.ids)],
                'lot_id': [('product_id', '=', self.meter_product_id.id)]
                if self.meter_product_id else [('id', '=', False)],
            }
        }

    def _get_dynamic_domains(self):
        result = super()._get_dynamic_domains()
        result.update({
            'meter_product_id': [('id', 'in', self.available_meter_product_ids.ids)],
            'lot_id': [('product_id', '=', self.meter_product_id.id)]
            if self.meter_product_id else [('id', '=', False)],
        })
        return result

    def _prepare_meter_vals(self):
        self.ensure_one()
        vals = super()._prepare_meter_vals()
        if not self.create_meter:
            return vals
        if not self.meter_product_id and not self.lot_id:
            # Physical inventory data is optional on subscriber onboarding;
            # it stays separate from the logical operational identifier and
            # can be completed later when the physical meter is assigned.
            return vals
        if self.meter_product_id:
            if self.meter_product_id.tracking != 'serial':
                raise ValidationError(_('منتج العداد يجب أن يستخدم التتبع التسلسلي.'))
            vals['product_id'] = self.meter_product_id.id
        if self.lot_id:
            if self.meter_product_id and self.lot_id.product_id != self.meter_product_id:
                raise ValidationError(_('Lot/Serial المختار لا يطابق منتج العداد.'))
            if self.lot_id.company_id and self.lot_id.company_id != self.env.company:
                raise ValidationError(_('Lot/Serial المختار تابع لشركة أخرى.'))
            vals.update({
                'product_id': (self.meter_product_id or self.lot_id.product_id).id,
                'lot_id': self.lot_id.id,
            })
        return vals
