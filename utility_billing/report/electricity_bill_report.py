from odoo import api, models


class ReportElectricityBill(models.AbstractModel):
    """Presentation-only data mapping for the utility electricity bill."""

    _name = 'report.utility_billing.report_electricity_bill'
    _description = 'Electricity Bill Print Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        orders = self.env['sale.order'].browse(docids)
        report_data = {}
        Payment = self.env['account.payment']
        Settlement = self.env['utility.financial.settlement']

        for order in orders:
            line_amounts = {
                'service': 0.0,
                'municipality': 0.0,
                'cleaning': 0.0,
                'mu_allim': 0.0,
            }
            for line in order.order_line.filtered(lambda item: not item.display_type):
                amount = line.price_total
                if line.meter_line_type in ('service_charge', 'fixed_fee'):
                    line_amounts['service'] += amount
                elif line.meter_line_type in line_amounts:
                    line_amounts[line.meter_line_type] += amount

            customer = order.customer_id
            current_payments = order.payment_ids.filtered(
                lambda payment: payment.state == 'posted')
            previous_payments = Payment.browse()
            previous_settlements = Settlement.browse()
            current_settlements = Settlement.browse()
            if customer and order.period_start:
                previous_payments = Payment.search([
                    ('utility_customer_id', '=', customer.id),
                    ('state', '=', 'posted'),
                    ('date', '<', order.period_start),
                ])
                previous_settlements = Settlement.search([
                    ('account_id', '=', customer.id),
                    ('state', '=', 'applied'),
                    ('date', '<', order.period_start),
                ])
            if customer and order.period_start and order.period_end:
                current_settlements = Settlement.search([
                    ('account_id', '=', customer.id),
                    ('state', '=', 'applied'),
                    ('date', '>=', order.period_start),
                    ('date', '<=', order.period_end),
                ])

            def settlement_net(records):
                return sum(
                    record.amount if record.settlement_type == 'debit' else -record.amount
                    for record in records
                )

            last_payment = current_payments.sorted(
                key=lambda payment: (payment.date or False, payment.id), reverse=True)[:1]
            collector = last_payment.collector_id if last_payment else self.env['utility.staff']
            report_data[order.id] = {
                'service_fee': line_amounts['service'],
                'municipality_fee': line_amounts['municipality'],
                'cleaning_fee': line_amounts['cleaning'],
                'mu_allim_fee': line_amounts['mu_allim'],
                'previous_payment': sum(previous_payments.mapped('amount')),
                'current_payment': sum(current_payments.mapped('amount')),
                'previous_settlement': settlement_net(previous_settlements),
                'current_settlement': settlement_net(current_settlements),
                'collector_name': collector.name if collector else False,
            }

        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': orders,
            'report_data': report_data,
        }
