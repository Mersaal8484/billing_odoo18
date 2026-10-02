"""
Tests for Payment Allocation Reversal Decoupling, Exact Partial Reconciles Integrity, and Multi-Record ORM Safety
"""
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_financial')
class TestPaymentAllocationReversal(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        receivable_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', [self.company.id])
        ], limit=1)
        if not receivable_account:
            receivable_account = self.env['account.account'].create({
                'name': 'حساب مدينون للاختبار',
                'code': '110000.PAR',
                'account_type': 'asset_receivable',
                'reconcile': True,
                'company_ids': [(6, 0, [self.company.id])],
            })

        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', [self.company.id])
        ], limit=1)
        if not income_account:
            income_account = self.env['account.account'].create({
                'name': 'إيرادات مبيعات للاختبار',
                'code': '400000.PAR',
                'account_type': 'income',
                'company_ids': [(6, 0, [self.company.id])],
            })

        self.partner = self.env['res.partner'].create({
            'name': 'مشترك اختبار عكس التخصيص',
            'property_account_receivable_id': receivable_account.id,
        })
        self.partner_2 = self.env['res.partner'].create({
            'name': 'مشترك اختبار 2',
            'property_account_receivable_id': receivable_account.id,
        })

        self.category = self.env['utility.subscriber.category'].search([], limit=1) or self.env['utility.subscriber.category'].create({
            'name': 'فئة سكنية',
            'code': 'RES_PAR',
        })
        self.subscriber = self.env['utility.subscriber'].search([], limit=1) or self.env['utility.subscriber'].create({
            'name': 'مشترك عام',
            'code': 'SUB_PAR',
            'category_id': self.category.id,
        })

        self.customer = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'customer_number': 'CUST-PAR-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })
        self.customer_2 = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'customer_number': 'CUST-PAR-002',
            'partner_id': self.partner_2.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })

        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات PAR',
            'fiscal_year': False,
        })
        self.payment_range_type = self.env['date.range.type'].create({
            'name': 'فترة سداد PAR',
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'أبريل 2026 - PAR',
            'type_id': self.date_range_type.id,
            'date_start': '2026-04-01',
            'date_end': '2026-04-30',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد أبريل 2026 - PAR',
            'type_id': self.payment_range_type.id,
            'date_start': '2026-04-01',
            'date_end': '2026-05-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })

        self.product = self.env['product.product'].create({
            'name': 'كهرباء PAR',
            'type': 'service',
            'property_account_income_id': income_account.id,
        })

        self.journal_bank = self.env['account.journal'].search([
            ('code', '=', 'BNK01'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not self.journal_bank:
            self.journal_bank = self.env['account.journal'].create({
                'name': 'البنك الرئيسي',
                'code': 'BNK01',
                'type': 'bank',
                'company_id': self.company.id,
            })

    def _create_order_and_invoice(self, customer, amount):
        order = self.env['sale.order'].create({
            'customer_id': customer.id,
            'partner_id': customer.partner_id.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': amount,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()
        return order, invoice

    def test_01_exact_partial_reconcile_reversal_isolation(self):
        """Reversing Allocation A must unlink ONLY Allocation A's partial reconcile, keeping Allocation B intact."""
        order, invoice = self._create_order_and_invoice(self.customer, 1000.0)

        # Payment A = 400
        payment_a = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 400.0,
            'journal_id': self.journal_bank.id,
            'utility_payment_method': 'bank',
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'date_range_id': self.payment_period.id,
        })
        payment_a.action_post()
        allocation_a = self.env['utility.payment.allocation'].search([('payment_id', '=', payment_a.id)], limit=1)
        self.assertEqual(allocation_a.state, 'reconciled')
        self.assertAlmostEqual(invoice.amount_residual, 600.0, places=2)

        # Payment B = 300
        payment_b = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 300.0,
            'journal_id': self.journal_bank.id,
            'utility_payment_method': 'bank',
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'date_range_id': self.payment_period.id,
        })
        payment_b.action_post()
        allocation_b = self.env['utility.payment.allocation'].search([('payment_id', '=', payment_b.id)], limit=1)
        self.assertEqual(allocation_b.state, 'reconciled')
        self.assertAlmostEqual(invoice.amount_residual, 300.0, places=2)

        # Reverse Allocation A ONLY
        allocation_a.action_reverse_allocation(reason='خطأ في تخصيص الدفعة الأولى')

        self.assertEqual(allocation_a.state, 'reversed')
        self.assertTrue(allocation_a.reversed_at)
        self.assertEqual(allocation_a.reversed_by, self.env.user)
        self.assertEqual(allocation_a.reversal_reason, 'خطأ في تخصيص الدفعة الأولى')

        # Allocation B must remain reconciled
        self.assertEqual(allocation_b.state, 'reconciled')

        # Invoice residual should be restored from 300 to 700 (1000 - 300 from Payment B)
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 700.0, places=2)

        # Payment A remains POSTED (decoupled unallocation)
        self.assertEqual(payment_a.state, 'posted')

    def test_02_idempotency_and_double_reversal_guard(self):
        """Second call to action_reverse_allocation must raise ValidationError."""
        order, invoice = self._create_order_and_invoice(self.customer, 500.0)
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': self.journal_bank.id,
            'utility_payment_method': 'bank',
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'date_range_id': self.payment_period.id,
        })
        payment.action_post()
        allocation = self.env['utility.payment.allocation'].search([('payment_id', '=', payment.id)], limit=1)

        # First reversal succeeds
        allocation.action_reverse_allocation(reason='First reversal')
        self.assertEqual(allocation.state, 'reversed')

        # Second reversal must fail
        with self.assertRaises(ValidationError):
            allocation.action_reverse_allocation(reason='Second reversal attempt')

    def test_03_multi_record_payment_write_isolation(self):
        """Writing to multiple payments together must not mix collector journals or cross-pollute values."""
        collector_role = self.env.ref('utility_core.role_collector')
        
        staff_a = self.env['utility.staff'].create({
            'name': 'Staff Multi A',
            'role_ids': [(6, 0, [collector_role.id])],
            'company_id': self.company.id,
        })
        staff_b = self.env['utility.staff'].create({
            'name': 'Staff Multi B',
            'role_ids': [(6, 0, [collector_role.id])],
            'company_id': self.company.id,
        })

        order_a, invoice_a = self._create_order_and_invoice(self.customer, 200.0)
        order_b, invoice_b = self._create_order_and_invoice(self.customer_2, 300.0)

        pay_a = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 200.0,
            'collector_id': staff_a.id,
            'journal_id': staff_a.collection_journal_id.id,
            'utility_payment_method': 'cash',
            'utility_sale_order_id': order_a.id,
            'utility_invoice_id': invoice_a.id,
            'date_range_id': self.payment_period.id,
        })
        pay_b = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_2.id,
            'amount': 300.0,
            'collector_id': staff_b.id,
            'journal_id': staff_b.collection_journal_id.id,
            'utility_payment_method': 'cash',
            'utility_sale_order_id': order_b.id,
            'utility_invoice_id': invoice_b.id,
            'date_range_id': self.payment_period.id,
        })

        # Batch write on both payments
        payments = pay_a | pay_b
        payments.write({'utility_payment_method': 'cash'})

        # Verify no cross-pollution
        self.assertEqual(pay_a.collector_id, staff_a)
        self.assertEqual(pay_a.journal_id, staff_a.collection_journal_id)
        self.assertEqual(pay_a.utility_sale_order_id, order_a)

        self.assertEqual(pay_b.collector_id, staff_b)
        self.assertEqual(pay_b.journal_id, staff_b.collection_journal_id)
        self.assertEqual(pay_b.utility_sale_order_id, order_b)

    def test_04_permission_check_on_action_reverse_allocation(self):
        """Standard user or collector must NOT be allowed to reverse payment allocation without billing manager role."""
        order, invoice = self._create_order_and_invoice(self.customer, 500.0)
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 500.0,
            'journal_id': self.journal_bank.id,
            'utility_payment_method': 'bank',
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'date_range_id': self.payment_period.id,
        })
        payment.action_post()
        allocation = self.env['utility.payment.allocation'].search([('payment_id', '=', payment.id)], limit=1)

        user_collector = self.env['res.users'].create({
            'name': 'Collector Non-Manager',
            'login': 'col_non_mgr@test.local',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(4, self.env.ref('utility_core.group_utility_collector').id)],
        })

        # Calling action_reverse_allocation as collector must raise AccessError
        with self.assertRaises(AccessError):
            allocation.with_user(user_collector).action_reverse_allocation(reason='Unauthorized reversal')
