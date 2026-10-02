from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_financial')
class TestFinancialLifecycle(TransactionCase):

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
            'name': 'مشترك دورة مالية كاملة',
            'property_account_receivable_id': receivable_account.id,
        })
        self.category = self.env['utility.subscriber.category'].search([
            ('code', '=', 'RES_FIN_LIFE'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.category:
            self.category = self.env['utility.subscriber.category'].create({
                'name': 'سكني مالية',
                'code': 'RES_FIN_LIFE',
            })
        self.sub_type = self.env['utility.subscriber'].search([
            ('code', '=', 'RES_GEN_FIN'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.sub_type:
            self.sub_type = self.env['utility.subscriber'].create({
                'name': 'سكني عام مالية',
                'code': 'RES_GEN_FIN',
                'category_id': self.category.id,
            })
        self.template = self.env['utility.contract.template'].search([
            ('code', '=', 'TPL_FIN_LIFE'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.template:
            self.template = self.env['utility.contract.template'].create({
                'name': 'قالب عقد مالية',
                'code': 'TPL_FIN_LIFE',
                'subscriber_category_ids': [(6, 0, [self.category.id])],
                'subscriber_ids': [(6, 0, [self.sub_type.id])],
            })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-FIN-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.sub_type.id,
            'contract_template_id': self.template.id,
        })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات مالية',
            'fiscal_year': False,
        })
        self.payment_range_type = self.env['date.range.type'].create({
            'name': 'فترة سداد مالية',
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'مارس 2026 - مالية',
            'type_id': self.date_range_type.id,
            'date_start': '2026-03-01',
            'date_end': '2026-03-31',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد مارس 2026 - مالية',
            'type_id': self.payment_range_type.id,
            'date_start': '2026-03-01',
            'date_end': '2026-04-15',
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
            'name': 'خدمة استهلاك كهرباء - مالية',
            'type': 'service',
            'property_account_income_id': income_account.id,
        })
        self.journal = self.env['account.journal'].search([
            ('code', '=', 'BNK01'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not self.journal:
            self.journal = self.env['account.journal'].create({
                'name': 'يومية البنك الرئيسي',
                'code': 'BNK01',
                'type': 'bank',
                'company_id': self.company.id,
            })

    def test_full_accounting_lifecycle_sign_convention(self):
        """Test accounting_balance signs across Invoice (+500), Partial Payment (-200), Credit Note (-100), Final Payment (-200)."""
        # Initial balance = 0
        self.customer._compute_accounting_balance()
        self.assertEqual(self.customer.accounting_balance, 0.0)

        # 1. Issue Invoice (+500)
        order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 500.0,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 500.0, places=2)

        # 2. Partial Payment (-200) -> Balance = 300
        payment1 = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 200.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        payment1.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 300.0, places=2)

        # 3. Credit Note (-100) -> Balance = 200
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner.id,
            'date': self.date_range.date_start,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        credit_note.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 200.0, places=2)

        # 4. Final Payment (-200) -> Balance = 0
        payment2 = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 200.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        payment2.action_post()

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 0.0, places=2)

    def test_writeoff_accounting_integrity(self):
        """Test that utility write-off applies credit note, reconciles invoice residual, and updates accounting balance."""
        writeoff_journal = self.env['account.journal'].create({
            'name': 'يومية الإثباتات والإنهاءات',
            'code': 'WOJ01',
            'type': 'sale',
            'company_id': self.company.id,
        })
        expense_account = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company.id])
        ], limit=1)
        if not expense_account:
            expense_account = self.env['account.account'].create({
                'name': 'مصروفات الإثباتات والديون المعدومة',
                'code': '690000.TEST',
                'account_type': 'expense',
                'company_ids': [(6, 0, [self.company.id])],
            })

        self.company.write({
            'writeoff_journal_id': writeoff_journal.id,
            'writeoff_account_id': expense_account.id,
        })

        order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 500.0,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()

        writeoff = self.env['utility.writeoff'].create({
            'customer_id': self.customer.id,
            'sale_order_id': order.id,
            'amount': 100.0,
            'reason': 'إعفاء جزء من المستحقات للاختبار',
        })
        writeoff.action_approve()
        writeoff.action_apply()

        self.assertEqual(writeoff.state, 'applied')
        self.assertTrue(writeoff.move_id)
        self.assertEqual(writeoff.move_id.state, 'posted')

        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)

        self.customer._compute_accounting_balance()
        self.assertAlmostEqual(self.customer.accounting_balance, 400.0, places=2)

    def test_writeoff_can_reopen_only_before_financial_application(self):
        """An approved write-off may be returned to draft only before apply."""
        writeoff = self.env['utility.writeoff'].create({
            'customer_id': self.customer.id,
            'amount': 25.0,
            'reason': 'اختبار إعادة فتح آمن',
        })
        writeoff.action_approve()
        writeoff.action_draft()
        self.assertEqual(writeoff.state, 'draft')

        with self.assertRaises(ValidationError):
            writeoff.action_draft()

    def test_writeoff_application_is_idempotent(self):
        """Applying a write-off twice never creates a second credit note."""
        journal = self.env['account.journal'].create({
            'name': 'يومية اختبار idempotency',
            'code': 'WID01',
            'type': 'sale',
            'company_id': self.company.id,
        })
        account = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', [self.company.id]),
        ], limit=1)
        if not account:
            account = self.env['account.account'].create({
                'name': 'حساب اختبار idempotency',
                'code': '690001.TEST',
                'account_type': 'expense',
                'company_ids': [(6, 0, [self.company.id])],
            })
        self.company.write({
            'writeoff_journal_id': journal.id,
            'writeoff_account_id': account.id,
        })
        order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
        })
        writeoff = self.env['utility.writeoff'].create({
            'customer_id': self.customer.id,
            'sale_order_id': order.id,
            'amount': 25.0,
            'reason': 'اختبار عدم تكرار الإشعار الدائن',
        })
        writeoff.action_approve()
        writeoff.action_apply()
        move = writeoff.move_id

        with self.assertRaises(UserError):
            writeoff.action_apply()
        with self.assertRaises(UserError):
            writeoff.action_draft()
        with self.assertRaises(ValidationError):
            writeoff.action_approve()

        self.assertEqual(writeoff.state, 'applied')
        self.assertEqual(writeoff.move_id, move)
        self.assertEqual(
            self.env['account.move'].search_count([
                ('utility_sale_order_id', '=', order.id),
                ('ref', 'ilike', writeoff.writeoff_number),
                ('move_type', '=', 'out_refund'),
            ]),
            1,
        )
