from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_concurrency')
class TestPaymentAllocationConcurrency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        receivable_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', [self.env.company.id])
        ], limit=1)
        if not receivable_account:
            receivable_account = self.env['account.account'].create({
                'name': 'حساب مدينون للاختبار',
                'code': '110000.TEST',
                'account_type': 'asset_receivable',
                'reconcile': True,
                'company_ids': [(6, 0, [self.env.company.id])],
            })
        self.partner = self.env['res.partner'].create({
            'name': 'اختبار تخصيص الدفعات',
            'property_account_receivable_id': receivable_account.id,
        })
        self.category = self.env['utility.subscriber.category'].search([
            ('code', '=', 'RES_ALLOC_CONC'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.category:
            self.category = self.env['utility.subscriber.category'].create({
                'name': 'سكني تخصيص',
                'code': 'RES_ALLOC_CONC',
            })
        self.sub_type = self.env['utility.subscriber'].search([
            ('code', '=', 'RES_GEN_ALLOC'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.sub_type:
            self.sub_type = self.env['utility.subscriber'].create({
                'name': 'سكني عام تخصيص',
                'code': 'RES_GEN_ALLOC',
                'category_id': self.category.id,
            })
        self.template = self.env['utility.contract.template'].search([
            ('code', '=', 'TPL_ALLOC'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.template:
            self.template = self.env['utility.contract.template'].create({
                'name': 'قالب عقد تخصيص',
                'code': 'TPL_ALLOC',
                'subscriber_category_ids': [(6, 0, [self.category.id])],
                'subscriber_ids': [(6, 0, [self.sub_type.id])],
            })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-ALLOC-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات تخصيص',
            'fiscal_year': False,
        })
        self.payment_range_type = self.env['date.range.type'].create({
            'name': 'فترة سداد تخصيص',
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'أبريل 2026 - تخصيص',
            'type_id': self.date_range_type.id,
            'date_start': '2026-04-01',
            'date_end': '2026-04-30',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد أبريل 2026 - تخصيص',
            'type_id': self.payment_range_type.id,
            'date_start': '2026-04-01',
            'date_end': '2026-05-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', [self.env.company.id])
        ], limit=1)
        if not income_account:
            income_account = self.env['account.account'].create({
                'name': 'إيرادات مبيعات الكهرباء للاختبار',
                'code': '400000.TEST',
                'account_type': 'income',
                'company_ids': [(6, 0, [self.env.company.id])],
            })
        self.product = self.env['product.product'].create({
            'name': 'خدمة كهرباء - تخصيص',
            'type': 'service',
            'property_account_income_id': income_account.id,
        })
        self.order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 400.0,
            })],
        })
        self.order.action_confirm()
        self.invoice = self.order._create_invoices()
        self.invoice.action_post()

        self.journal = self.env['account.journal'].search([
            ('code', '=', 'AL01'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not self.journal:
            self.journal = self.env['account.journal'].create({
                'name': 'يومية تخصيص',
                'code': 'AL01',
                'type': 'bank',
                'company_id': self.env.company.id,
            })

    def test_payment_allocation_idempotency_and_locking(self):
        """Test that calling allocate_payment twice on the same payment returns the existing allocation."""
        payment = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 400.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        payment.action_post()

        allocation1 = self.env['utility.payment.allocation'].search([('payment_id', '=', payment.id)], limit=1)
        self.assertTrue(allocation1)
        self.assertEqual(allocation1.allocated_amount, 400.0)

        # Calling allocate_payment again on already reconciled payment must return existing allocation
        allocation2 = self.env['utility.payment.allocation'].allocate_payment(payment)
        self.assertEqual(allocation1.id, allocation2.id)

        # Verify only 1 allocation record exists for this payment
        allocations = self.env['utility.payment.allocation'].search([('payment_id', '=', payment.id)])
        self.assertEqual(len(allocations), 1)
