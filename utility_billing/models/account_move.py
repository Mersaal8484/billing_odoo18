from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', string='حساب الكهرباء', index=True,
        copy=False, readonly=True)
    utility_adjustment_id = fields.Many2one(
        'utility.billing.adjustment', string='تعديل الفوترة', index=True,
        copy=False, readonly=True)
    utility_replacement_of_id = fields.Many2one(
        'account.move', string='الفاتورة الأصلية المستبدلة', index=True,
        copy=False, readonly=True)
    utility_replacement_invoice_ids = fields.One2many(
        'account.move', 'utility_replacement_of_id', string='الفواتير البديلة',
        copy=False, readonly=True)
    service_charge_id = fields.Many2one('utility.service.charge', string='رسم الخدمة', index=True, copy=False, check_company=True)
    meter_number = fields.Char(related='utility_sale_order_id.meter_id.meter_number', string='رقم العداد', store=True)
    current_meter_reading = fields.Float(related='utility_sale_order_id.current_reading', string='القراءة الحالية للعداد', store=True)
    consumption_units = fields.Float(related='utility_sale_order_id.consumption', string='وحدات الاستهلاك', store=True)
    consumption_alert = fields.Selection(related='utility_sale_order_id.reading_id.consumption_alert', string='حالة الاستهلاك')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get('utility_sale_order_id')
            if order_id:
                order = self.env['sale.order'].browse(order_id).exists()
                if not order or not order.customer_id:
                    raise ValidationError(_('فاتورة الكهرباء يجب أن ترتبط بحساب كهربائي صحيح.'))
                expected_partner_id = order.customer_id.partner_id.id
                if vals.get('partner_id') and vals['partner_id'] != expected_partner_id:
                    raise ValidationError(_('شريك الفاتورة يجب أن يطابق شريك الحساب الكهربائي.'))
                vals['partner_id'] = expected_partner_id
                vals['utility_customer_id'] = order.customer_id.id
                if not vals.get('invoice_date') and order.date_range_id and order.date_range_id.date_start:
                    vals['invoice_date'] = order.date_range_id.date_start
            customer_id = vals.get('utility_customer_id')
            if customer_id and not order_id:
                customer = self.env['utility.customer'].browse(customer_id).exists()
                if not customer:
                    raise ValidationError(_('حساب الكهرباء المحدد غير موجود.'))
                if vals.get('partner_id') and vals['partner_id'] != customer.partner_id.id:
                    raise ValidationError(_('شريك القيد يجب أن يطابق شريك الحساب الكهربائي.'))
                vals['partner_id'] = customer.partner_id.id
        return super().create(vals_list)

    @api.constrains('utility_sale_order_id', 'utility_customer_id', 'partner_id')
    def _check_utility_invoice_partner(self):
        for move in self.filtered(lambda record: record.utility_sale_order_id or record.utility_customer_id):
            customer = move.utility_customer_id or move.utility_sale_order_id.customer_id
            expected = customer.partner_id
            if (move.utility_sale_order_id
                    and move.utility_sale_order_id.customer_id != customer):
                raise ValidationError(_('حساب القيد لا يطابق فاتورة الكهرباء المرتبطة.'))
            if move.partner_id != expected:
                raise ValidationError(_(
                    'شريك الفاتورة %s لا يطابق الشريك المحاسبي للحساب الكهربائي %s.'
                ) % (move.partner_id.display_name, expected.display_name))


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    utility_customer_id = fields.Many2one(
        'utility.customer', related='move_id.utility_customer_id',
        string='حساب الكهرباء', store=True, index=True, readonly=True)

    @api.constrains('move_id', 'partner_id')
    def _check_utility_move_line_partner(self):
        for line in self.filtered('utility_customer_id'):
            expected = line.utility_customer_id.partner_id
            if line.partner_id != expected:
                raise ValidationError(_(
                    'شريك سطر القيد يجب أن يطابق شريك الحساب الكهربائي.'
                ))

