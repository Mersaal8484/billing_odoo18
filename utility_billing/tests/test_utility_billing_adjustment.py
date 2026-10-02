from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUtilityBillingAdjustment(TransactionCase):
    """Self-contained coverage for the posted-invoice correction workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Product = cls.env['product.product']
        cls.Account = cls.env['account.account']
        cls.category = cls.Category.create({
            'name': 'فئة اختبار تعديلات الفوترة',
            'code': 'BILL-ADJ-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع اختبار تعديلات الفوترة',
            'code': 'BILL-ADJ-SUB',
            'category_id': cls.category.id,
        })
        cls.income = cls.Account.search([
            ('company_ids', 'in', [cls.env.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        if not cls.income or not cls.journal:
            raise ValidationError('تحتاج اختبارات تعديلات الفوترة إلى حساب إيراد ودفتر مبيعات.')
        cls.product = cls.Product.create({
            'name': 'منتج اختبار الفوترة',
            'type': 'service',
        })
        cls.product.property_account_income_id = cls.income
        cls.template = cls.env['utility.contract.template'].create({
            'name': 'قالب اختبار تعديلات الفوترة',
            'code': 'BILL-ADJ-TPL',
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
            'price_per_kwh': 1.0,
            'service_charge': 10.0,
        })
        cls.env['utility.contract.template.line'].create([
            {
                'template_id': cls.template.id,
                'product_id': cls.product.id,
                'name': 'استهلاك اختبار',
                'meter_line_type': 'consumption',
            },
            {
                'template_id': cls.template.id,
                'product_id': cls.product.id,
                'name': 'خدمة اختبار',
                'meter_line_type': 'service_charge',
            },
        ])
        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'دورة تعديلات الفوترة',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار تعديلات الفوترة',
            'period_code': 'BILL-ADJ-2026-08',
            'cycle_key': 'BILL-ADJ-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _create_bill_chain(self, suffix, consumption=1000.0):
        partner = self.Partner.create({'name': 'مالك اختبار التعديل %s' % suffix})
        customer = self.Customer.create({
            'customer_number': 'BILL-ADJ-%s' % suffix,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'customer_id': customer.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
            'previous_reading': 0.0,
            'current_reading': consumption,
            'consumption': consumption,
        })
        order._calculate_amounts()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.journal.id,
            'partner_id': partner.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'فاتورة اختبار أصلية',
                'quantity': 1.0,
                'price_unit': 1000.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        return customer, order, invoice

    def _apply(self, values):
        adjustment = self.env['utility.billing.adjustment'].create(values)
        adjustment.action_submit()
        adjustment.action_approve()
        adjustment.action_apply_correction()
        return adjustment

    def test_partial_adjustment_is_self_contained_and_posted(self):
        customer, order, invoice = self._create_bill_chain('PARTIAL')
        adjustment = self._apply({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار تصحيح جزئي مستقل',
            'corrected_amount': invoice.amount_total - 1.0,
        })
        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.credit_note_id.state, 'posted')
        self.assertEqual(adjustment.credit_note_id.reversed_entry_id, invoice)

    def test_zero_corrected_consumption_is_preserved_in_full_rebill(self):
        customer, order, invoice = self._create_bill_chain('ZERO')
        adjustment = self._apply({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'consumption_correction',
            'reason': 'اختبار استهلاك مصحح بصفر',
            'rebill': True,
            'corrected_consumption': 0.0,
            'corrected_amount': 10.0,
        })
        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.replacement_sale_order_id.consumption, 0.0)
        self.assertEqual(adjustment.replacement_invoice_id.state, 'posted')

