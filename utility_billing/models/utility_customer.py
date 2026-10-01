from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityCustomer(models.Model):
    _inherit = 'utility.customer'

    service_charge_ids = fields.One2many(
        'utility.service.charge', 'account_id', string='رسوم إدخال الخدمة')
    service_charge_count = fields.Integer(
        'عدد رسوم إدخال الخدمة', compute='_compute_service_charge_count')
    payment_allocation_ids = fields.One2many(
        'utility.payment.allocation', 'utility_customer_id',
        string='تخصيصات التحصيل', readonly=True)
    payment_allocation_count = fields.Integer(
        'عدد تخصيصات التحصيل', compute='_compute_payment_allocation_count')

    @api.depends('service_charge_ids')
    def _compute_service_charge_count(self):
        counts = self.env['utility.service.charge'].read_group(
            [('account_id', 'in', self.ids)], ['account_id'], ['account_id']) if self.ids else []
        count_map = {item['account_id'][0]: item['account_id_count'] for item in counts}
        for customer in self:
            customer.service_charge_count = count_map.get(customer.id, 0)

    @api.depends('payment_allocation_ids')
    def _compute_payment_allocation_count(self):
        for customer in self:
            customer.payment_allocation_count = len(customer.payment_allocation_ids)

    @api.model_create_multi
    def create(self, vals_list):
        customers = super().create(vals_list)
        active_customers = customers.filtered(lambda customer: customer.state == 'active')
        active_customers._ensure_activation_service_charge('new_contract')
        return customers

    def write(self, vals):
        to_activate = self.filtered(lambda customer: customer.state != 'active') if vals.get('state') == 'active' else self.env['utility.customer']
        result = super().write(vals)
        to_activate._ensure_activation_service_charge('legacy_activation')
        return result

    def _ensure_activation_service_charge(self, activation_type):
        """Create exactly one entry-service charge when an account becomes active."""
        customers = self.filtered(lambda customer: customer.state == 'active')
        if not customers or self.env.context.get('skip_service_activation_charge'):
            return self.env['utility.service.charge']
        existing = self.env['utility.service.charge'].search([('account_id', 'in', customers.ids)])
        existing_ids = set(existing.mapped('account_id').ids)
        pending = customers.filtered(lambda customer: customer.id not in existing_ids)
        if not pending:
            return existing
        product = self.env.ref('utility_core.utility_product_service_charge', raise_if_not_found=False)
        if not product or product.lst_price <= 0:
            return self.env['utility.service.charge']
        charges = self.env['utility.service.charge'].create([{
            'account_id': customer.id,
            'activation_type': activation_type,
            'product_id': product.id,
            'description': _('رسم إدخال الخدمة - %s') % customer.display_name,
            'quantity': 1.0,
            'price_unit': product.lst_price,
            'tax_ids': [(6, 0, product.taxes_id.filtered(
                lambda tax: tax.company_id == customer.company_id or not tax.company_id).ids)],
            'billing_method': 'direct_payment',
            'company_id': customer.company_id.id,
        } for customer in pending])
        charges.action_confirm()
        return charges

    def action_view_service_charges(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('رسم إدخال الخدمة'),
            'res_model': 'utility.service.charge', 'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_view_payment_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('تخصيصات التحصيل'),
            'res_model': 'utility.payment.allocation',
            'view_mode': 'list,form',
            'domain': [('utility_customer_id', '=', self.id)],
            'context': {'default_utility_customer_id': self.id, 'create': False},
        }

