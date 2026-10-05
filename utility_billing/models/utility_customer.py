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
    opening_receivable_residual = fields.Monetary(
        string='متبقي المديونية المرحلة',
        compute='_compute_opening_receivable_residual',
        currency_field='company_currency_id',
        readonly=True,
    )

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

    @api.depends(
        'opening_move_id.state', 'opening_move_id.partner_id',
        'opening_move_id.line_ids.amount_residual',
        'opening_move_id.line_ids.reconciled',
        'opening_move_id.line_ids.account_id.account_type',
    )
    def _compute_opening_receivable_residual(self):
        for customer in self:
            move = customer.opening_move_id
            if not move or move.state != 'posted' or move.partner_id != customer.partner_id:
                customer.opening_receivable_residual = 0.0
                continue
            lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and line.partner_id == customer.partner_id
                and line.debit > 0
                and not line.reconciled
            )
            customer.opening_receivable_residual = sum(lines.mapped('amount_residual'))

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

    def action_register_opening_balance_payment(self):
        """Open a payment draft for this account's one audited opening debt."""
        self.ensure_one()
        opening_move = self.opening_move_id
        if not opening_move or self.opening_receivable_residual <= 0:
            raise UserError(_('لا توجد مديونية مرحلة مفتوحة قابلة للسداد لهذا الحساب.'))
        if (opening_move.state != 'posted'
                or opening_move.move_type != 'entry'
                or opening_move.utility_customer_id != self
                or opening_move.partner_id != self.partner_id):
            raise UserError(_('قيد المديونية المرحلة غير صالح لهذا الحساب.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('سداد المديونية المرحلة'),
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_opening_customer_id': self.id,
                'default_utility_opening_move_id': opening_move.id,
                'default_utility_invoice_id': opening_move.id,
                'default_amount': self.opening_receivable_residual,
            },
        }

