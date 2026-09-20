import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityContractTemplate(models.Model):
    _inherit = 'utility.contract.template'

    def _prepare_sale_order_data(self, account, reading):
        """تحضير بيانات أمر البيع من العقد والقراءة المعتمدة"""
        template = account.contract_template_id
        consumption = reading.consumption
        lines = []
        for line in self.line_ids:
            if line.meter_line_type == 'discount' and not template.subsidy_enabled:
                continue
            qty = line.quantity
            price = line.specific_price or 0.0
            name = line.name or line.product_id.name
            if line.meter_line_type == 'consumption' and template:
                qty = consumption
                price = template.price_per_kwh or 0.0
                name = line.name or f'استهلاك ({consumption} kWh × {price})'
            elif line.qty_formula_id:
                category = account.subscriber_id
                qty, computed_name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=reading.previous_reading,
                    current_reading=reading.reading_value,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
                if computed_name:
                    name = computed_name
            elif line.is_subsidized and account.subscriber_id:
                category = account.subscriber_id
                if category.subsidized_enabled and consumption > 0:
                    qty, price, name = category._get_subsidized_amount(consumption, template)
            if qty or price:
                lines.append((0, 0, {
                    'product_id': line.product_id.id if line.product_id else False,
                    'name': name,
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'meter_line_type': line.meter_line_type,
                }))
        return {
            'partner_id': account.partner_id.id if account.partner_id else self.env.company.partner_id.id,
            'customer_id': account.id,
            'meter_id': account.meter_id.id,
            'reading_id': reading.id,
            'date_range_id': reading.date_range_id.id,
            'contract_template_id': template.id if template else False,
            'period_start': reading.date_range_id.date_start or (
                reading.previous_reading_date.date() if reading.previous_reading_date else fields.Date.today()),
            'period_end': reading.date_range_id.date_end or (
                reading.reading_date.date() if reading.reading_date else fields.Date.today()),
            'previous_reading': reading.previous_reading,
            'current_reading': reading.reading_value,
            'consumption': consumption,
            'order_line': lines,
        }

    def cron_generate_recurring_invoices(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.recurring_batch_size', 200))
        accounts = self.env['utility.customer'].search([
            ('state', '=', 'active'),
            ('contract_template_id', '!=', False),
        ], limit=batch_size)
        if not accounts:
            return

        approved_readings = self.env['utility.reading'].search([
            ('account_id', 'in', accounts.ids),
            ('state', '=', 'approved'),
        ])
        reading_by_account = {}
        for r in approved_readings:
            if r.date_range_id:
                if r.account_id.id not in reading_by_account:
                    reading_by_account[r.account_id.id] = r
                elif r.reading_date > reading_by_account[r.account_id.id].reading_date:
                    reading_by_account[r.account_id.id] = r

        existing_orders = self.env['sale.order'].search([
            ('reading_id', 'in', approved_readings.ids),
            ('state', '!=', 'cancel'),
        ])
        existing_reading_ids = existing_orders.mapped('reading_id').ids

        success = 0
        errors = 0
        for account in accounts:
            reading = reading_by_account.get(account.id)
            if not reading:
                continue
            if reading.id in existing_reading_ids:
                continue
            try:
                with self.env.cr.savepoint():
                    order = self.env['sale.order'].create(
                        account.contract_template_id._prepare_sale_order_data(account, reading)
                    )
                    order._calculate_amounts()
                    reading.state = 'billed'
                    account.write({
                        'last_reading_date': reading.reading_date,
                        'last_reading_value': reading.reading_value,
                        'last_invoice_date': fields.Datetime.now(),
                        'last_invoice_reading': reading.reading_value,
                    })
                success += 1
            except (UserError, ValidationError) as e:
                _logger.warning(
                    "Recurring invoice validation failed for account %s (reading %s): %s",
                    account.customer_number, reading.id, e)
                errors += 1
            except Exception:
                _logger.error(
                    "Unexpected error generating invoice for account %s (reading %s)",
                    account.customer_number, reading.id, exc_info=True)
                errors += 1
        if errors:
            _logger.info(
                "Recurring billing: %d success, %d errors (batch %d)",
                success, errors, batch_size)
