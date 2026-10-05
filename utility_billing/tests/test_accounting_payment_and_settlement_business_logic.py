# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import fields


@tagged('post_install', '-at_install', 'utility_release', 'utility_financial')
class TestAccountingPaymentAndSettlementBusinessLogic(TransactionCase):
    """
    اختبارات منطق الأعمال المالي المتقدم:
    - التخصيص الدقيق للمدفوعات وعزل أرصدة الفواتير المتعددة لنفس العميل (Targeted Payment & Residual Isolation)
    - سداد الفاتورة الحالية أولاً ثم المتأخرات الأقدم من نفس ذمة العميل
    - إلغاء وعكس الدفعة وإعادة الرصيد المستحق بدقة (Unreconciliation & Reversal Integrity)
    - دورة شطب المديونيات والإعفاءات (Write-off) وتوليد إشعار دائن واحد فقط وحصانة السجل المطبق
    - تسوية عهد المحصلين وفصل المهام (Collector Custody Settlement & Segregation of Duties)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # الحسابات واليوميات الأساسية
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']
        cls.Partner = cls.env['res.partner']
        cls.Customer = cls.env['utility.customer']
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Product = cls.env['product.product']
        cls.Payment = cls.env['account.payment']
        cls.Move = cls.env['account.move']

        # حساب المدينين (Receivable)
        cls.receivable_account = cls.Account.search([
            ('company_ids', 'in', [cls.company.id]),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        if not cls.receivable_account:
            cls.receivable_account = cls.Account.create({
                'name': 'حساب مدينو الكهرباء للاختبار',
                'code': '120999',
                'account_type': 'asset_receivable',
                'reconcile': True,
                'company_ids': [(6, 0, [cls.company.id])],
            })

        # حساب الإيرادات
        cls.income_account = cls.Account.search([
            ('company_ids', 'in', [cls.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        if not cls.income_account:
            cls.income_account = cls.Account.create({
                'name': 'إيرادات كهرباء تجريبية',
                'code': '400999',
                'account_type': 'income',
                'company_ids': [(6, 0, [cls.company.id])],
            })

        # يوميات المبيعات والبنك
        cls.sale_journal = cls.Journal.search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        cls.bank_journal = cls.Journal.search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'bank'),
        ], limit=1)

        # حساب ويومية الإعفاءات والشطب (Write-off)
        cls.writeoff_account = cls.Account.search([
            ('company_ids', 'in', [cls.company.id]),
            ('code', '=', '600999'),
        ], limit=1)
        if not cls.writeoff_account:
            cls.writeoff_account = cls.Account.create({
                'name': 'حساب ديون معدومة وإعفاءات',
                'code': '600999',
                'account_type': 'expense',
                'company_ids': [(6, 0, [cls.company.id])],
            })
        cls.writeoff_journal = cls.Journal.search([
            ('company_id', '=', cls.company.id),
            ('code', '=', 'WROFF'),
        ], limit=1)
        if not cls.writeoff_journal:
            cls.writeoff_journal = cls.Journal.create({
                'name': 'يومية الإعفاءات والشطب',
                'code': 'WROFF',
                'type': 'sale',
                'company_id': cls.company.id,
            })

        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.writeoff_journal_id', str(cls.writeoff_journal.id)
        )
        cls.env['ir.config_parameter'].sudo().set_param(
            'utility.writeoff_account_id', str(cls.writeoff_account.id)
        )

        # منتج الطاقة
        cls.kwh_product = cls.Product.create({
            'name': 'طاقة كهربائية للاختبار المالي',
            'type': 'service',
            'invoice_policy': 'order',
        })
        cls.kwh_product.property_account_income_id = cls.income_account

        # بيانات العميل
        cls.category = cls.Category.create({
            'name': 'فئة الاختبار المالي المتقدم',
            'code': 'FIN-ADV-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع المشترك المالي المتقدم',
            'code': 'FIN-ADV-SUB',
            'category_id': cls.category.id,
        })
        cls.partner = cls.Partner.create({
            'name': 'العميل المالي متعدد الفواتير',
            'property_account_receivable_id': cls.receivable_account.id,
        })
        cls.customer = cls.Customer.create({
            'customer_number': 'CUST-FIN-MULTI-01',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        # دورة وفترة السداد
        range_type = cls.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'دورة مالية',
                'work_type': 'readings',
            })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة السداد 2026-09',
            'type_id': range_type.id,
            'date_start': '2026-09-01',
            'date_end': '2026-09-30',
            'state': 'open',
            'period_role': 'reading',
            'collection_state': 'open',
            'company_id': cls.company.id,
        })

    def _create_posted_bill(self, amount, suffix, period=None, invoice_date=None):
        """مساعد لإنشاء أمر بيع وفاتورة كهرباء منشورة بمبلغ محدد."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': (period or self.period).id,
            'consumption': amount,
            'amount_total': amount,
        })
        invoice = self.Move.create({
            'move_type': 'out_invoice',
            'journal_id': self.sale_journal.id,
            'partner_id': self.partner.id,
            'utility_customer_id': self.customer.id,
            'utility_sale_order_id': order.id,
            'invoice_date': invoice_date or date(2026, 9, 15),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.kwh_product.id,
                'name': f'استهلاك كهرباء {suffix}',
                'quantity': 1.0,
                'price_unit': amount,
                'account_id': self.income_account.id,
                # Keep this accounting-flow test independent from the demo
                # company's country-specific default sales taxes.
                'tax_ids': [(5, 0, 0)],
            })],
        })
        invoice.action_post()
        return order, invoice

    def _create_opening_receivable(self, amount, suffix='OPENING'):
        """Create the one explicit migration-style opening receivable move."""
        journal = self.Journal.search([
            ('company_id', '=', self.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not journal:
            journal = self.Journal.create({
                'name': 'Opening balance test journal',
                'code': 'OPNBAL',
                'type': 'general',
                'company_id': self.company.id,
            })
        move = self.Move.create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'partner_id': self.partner.id,
            'utility_customer_id': self.customer.id,
            'date': date(2026, 8, 1),
            'ref': 'Opening balance %s' % suffix,
            'line_ids': [
                (0, 0, {
                    'name': 'Opening receivable %s' % suffix,
                    'partner_id': self.partner.id,
                    'account_id': self.receivable_account.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Opening offset %s' % suffix,
                    'account_id': self.income_account.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        move.action_post()
        self.customer.opening_move_id = move.id
        return move

    def _opening_residual(self, move):
        return sum(move.line_ids.filtered(
            lambda line: line.account_id == self.receivable_account
            and line.debit > 0 and not line.reconciled
        ).mapped('amount_residual'))

    def test_01_targeted_allocation_multiple_invoices_residual_isolation(self):
        """
        التحقق من التخصيص الدقيق للمدفوعات وعزل الأرصدة:
        - العميل لديه فاتورتان: الفاتورة A بمبلغ 5,000 والفاتورة B بمبلغ 3,000 (إجمالي مديونية 8,000).
        - يتم دفع 3,500 مخصصة حصرياً للفاتورة A.
        - الرصيد المتبقي للفاتورة A يصبح 1,500.
        - الفاتورة B تظل برصيدها الكامل 3,000 دون أي تسوية أو تأثير (منع التخصيص العشوائي).
        """
        order_a, invoice_a = self._create_posted_bill(5000.0, 'A')
        prior_period = self.env['date.range'].create({
            'name': 'فترة اختبار عزل سابقة 2026-08',
            'type_id': self.period.type_id.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'state': 'open',
            'period_role': 'reading',
            'collection_state': 'open',
            'company_id': self.company.id,
        })
        order_b, invoice_b = self._create_posted_bill(
            3000.0, 'B', period=prior_period, invoice_date=date(2026, 8, 15))

        self.assertEqual(invoice_a.amount_residual, 5000.0)
        self.assertEqual(invoice_b.amount_residual, 3000.0)

        # سداد جزئي 3,500 للفاتورة A
        payment = self.Payment.create({
            'utility_sale_order_id': order_a.id,
            'utility_invoice_id': invoice_a.id,
            'partner_id': self.partner.id,
            'amount': 3500.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-TAR-001',
        })
        payment.action_post()

        invoice_a.invalidate_recordset()
        invoice_b.invalidate_recordset()

        # الفاتورة A خُصم منها السداد
        self.assertAlmostEqual(invoice_a.amount_residual, 1500.0, places=2)
        # الفاتورة B لم تتأثر إطلاقاً
        self.assertAlmostEqual(invoice_b.amount_residual, 3000.0, places=2)

        # التحقق من سجل التخصيص المستقل (utility.payment.allocation)
        allocations = self.env['utility.payment.allocation'].search([('payment_id', '=', payment.id)])
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations.invoice_id.id, invoice_a.id)
        self.assertEqual(allocations.allocated_amount, 3500.0)

    def test_02_customer_payment_settles_current_then_oldest_arrears(self):
        """One receivable payment settles current first, then oldest arrears."""
        old_period = self.env['date.range'].create({
            'name': 'فترة سداد سابقة 2026-08',
            'type_id': self.period.type_id.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            # The invoice remains collectible as an arrear; only the old
            # period's collection window is closed.
            'state': 'open',
            'period_role': 'reading',
            'collection_state': 'reconciled',
            'company_id': self.company.id,
        })
        _old_order_a, old_invoice_a = self._create_posted_bill(
            3000.0, 'OLD-A', period=old_period, invoice_date=date(2026, 8, 5))
        older_period = self.env['date.range'].create({
            'name': 'فترة سداد أقدم 2026-07',
            'type_id': self.period.type_id.id,
            'date_start': '2026-07-01',
            'date_end': '2026-07-31',
            'state': 'open',
            'period_role': 'reading',
            'collection_state': 'reconciled',
            'company_id': self.company.id,
        })
        _old_order_b, old_invoice_b = self._create_posted_bill(
            2000.0, 'OLD-B', period=older_period, invoice_date=date(2026, 7, 10))
        current_order, current_invoice = self._create_posted_bill(5000.0, 'CURRENT')

        payment = self.Payment.create({
            'utility_sale_order_id': current_order.id,
            'utility_invoice_id': current_invoice.id,
            'partner_id': self.partner.id,
            'amount': 9000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-MULTI-001',
        })
        payment.action_post()

        current_invoice.invalidate_recordset()
        old_invoice_a.invalidate_recordset()
        old_invoice_b.invalidate_recordset()
        self.assertAlmostEqual(current_invoice.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(old_invoice_a.amount_residual, 1000.0, places=2)
        self.assertAlmostEqual(old_invoice_b.amount_residual, 0.0, places=2)

        allocations = self.env['utility.payment.allocation'].search(
            [('payment_id', '=', payment.id)], order='id')
        self.assertEqual(len(allocations), 3)
        self.assertEqual(allocations[0].invoice_id, current_invoice)
        self.assertEqual(allocations[1].invoice_id, old_invoice_b)
        self.assertEqual(allocations[2].invoice_id, old_invoice_a)
        self.assertEqual(sum(allocations.mapped('allocated_amount')), 9000.0)
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.receivable_account)
        self.assertTrue(receivable_lines)
        self.assertTrue(all(line.partner_id == self.partner for line in receivable_lines))

    def test_02b_excess_stays_as_partner_receivable_credit(self):
        order, invoice = self._create_posted_bill(5000.0, 'CREDIT')
        payment = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': self.partner.id,
            'amount': 6000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-CREDIT-001',
        })
        payment.action_post()

        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        credit_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.receivable_account
            and line.partner_id == self.partner and not line.reconciled)
        self.assertTrue(credit_lines)
        self.assertAlmostEqual(sum(abs(line.amount_residual) for line in credit_lines), 1000.0, places=2)

    def test_02c_bill_shows_live_current_due_plus_prior_arrears(self):
        """Printed/onscreen totals are a live Receivable breakdown, not a snapshot."""
        old_period = self.env['date.range'].create({
            'name': 'فترة متأخرات لاختبار العرض 2026-08',
            'type_id': self.period.type_id.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'state': 'open',
            'period_role': 'reading',
            'collection_state': 'reconciled',
            'company_id': self.company.id,
        })
        _old_order, _old_invoice = self._create_posted_bill(
            3000.0, 'DISPLAY-OLD', period=old_period,
            invoice_date=date(2026, 8, 15))
        current_order, _current_invoice = self._create_posted_bill(
            5000.0, 'DISPLAY-CURRENT')

        current_order.invalidate_recordset()
        self.assertAlmostEqual(current_order.balance_due, 5000.0, places=2)
        self.assertAlmostEqual(current_order.previous_balance, 3000.0, places=2)
        self.assertAlmostEqual(current_order.total_due_amount, 8000.0, places=2)


    def test_02d_current_invoice_then_opening_balance(self):
        """120 settles current 40 then the explicit opening debt by 80."""
        opening_move = self._create_opening_receivable(100.0, 'CURRENT-FIRST')
        order, invoice = self._create_posted_bill(40.0, 'CURRENT-OPENING')
        payment = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': self.partner.id,
            'amount': 120.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-OPENING-120',
        })
        payment.action_post()

        invoice.invalidate_recordset(['amount_residual'])
        opening_move.invalidate_recordset(['line_ids'])
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(self._opening_residual(opening_move), 20.0, places=2)
        allocations = self.env['utility.payment.allocation'].search(
            [('payment_id', '=', payment.id)], order='id')
        self.assertEqual(allocations.mapped('invoice_id'), invoice | opening_move)
        self.assertAlmostEqual(sum(allocations.mapped('allocated_amount')), 120.0, places=2)

    def test_02e_opening_balance_can_be_paid_directly(self):
        """Only the exact customer-linked opening move is valid without a bill."""
        opening_move = self._create_opening_receivable(100.0, 'DIRECT')
        payment = self.Payment.create({
            'opening_customer_id': self.customer.id,
            'utility_opening_move_id': opening_move.id,
            'utility_invoice_id': opening_move.id,
            'partner_id': self.partner.id,
            'amount': 60.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-OPENING-DIRECT',
        })
        payment.action_post()

        opening_move.invalidate_recordset(['line_ids'])
        self.assertAlmostEqual(self._opening_residual(opening_move), 40.0, places=2)
        allocation = self.env['utility.payment.allocation'].search([
            ('payment_id', '=', payment.id),
        ], limit=1)
        self.assertEqual(allocation.invoice_id, opening_move)
        self.assertAlmostEqual(allocation.allocated_amount, 60.0, places=2)

    def test_03_payment_unreconciliation_and_reversal_integrity(self):
        """
        إلغاء وعكس الدفعة واستعادة الرصيد المستحق (Unreconcile on Cancel):
        - فاتورة بقيمة 4,000 يتم سدادها بالكامل.
        - يصبح الرصيد المستحق 0.0.
        - عند إلغاء الدفعة، يتم فك المقاصة وتعود الفاتورة إلى الرصيد 4,000 بالكامل.
        """
        order, invoice = self._create_posted_bill(4000.0, 'CANCEL-TEST')
        payment = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': self.partner.id,
            'amount': 4000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-CANCEL-001',
        })
        payment.action_post()

        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)

        # إلغاء الدفعة
        payment.action_cancel()

        invoice.invalidate_recordset()
        # استعادة الرصيد المتبقي بدقة تامة
        self.assertAlmostEqual(invoice.amount_residual, 4000.0, places=2)

    def test_04_writeoff_lifecycle_single_credit_note_and_residual_reduction(self):
        """
        دورة شطب المديونية والإعفاء (Write-off Lifecycle):
        - فاتورة بمبلغ 10,000 تم سداد 6,000 منها ومتبقي 4,000.
        - إنشاء إعفاء بقيمة 4,000 واعتماده وتطبيقه.
        - التحقق من:
          1. توليد إشعار دائن واحد فقط (account.move من نوع out_refund).
          2. مقاصة إشعار الدائن مع الفاتورة وتخفيض الرصيد المستحق إلى 0.0.
          3. حالة الإعفاء تنتقل إلى applied.
        """
        order, invoice = self._create_posted_bill(10000.0, 'WRITEOFF-TEST')

        # سداد جزئي 6,000
        p = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': self.partner.id,
            'amount': 6000.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': 'bank',
            'journal_id': self.bank_journal.id,
            'date_range_id': self.period.id,
            'date': date(2026, 9, 20),
            'electronic_doc_no': 'PAY-PART-WR',
        })
        p.action_post()
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 4000.0, places=2)

        # إنشاء إعفاء بمبلغ 4,000
        writeoff = self.env['utility.writeoff'].create({
            'customer_id': self.customer.id,
            'sale_order_id': order.id,
            'amount': 4000.0,
            'reason': 'إعفاء استثنائي معتمد',
        })
        self.assertEqual(writeoff.state, 'draft')

        # الاعتماد
        writeoff.action_approve()
        self.assertEqual(writeoff.state, 'approved')

        # التطبيق المالي
        writeoff.action_apply()
        self.assertEqual(writeoff.state, 'applied')
        self.assertTrue(writeoff.move_id)
        self.assertEqual(writeoff.move_id.move_type, 'out_refund')
        self.assertEqual(writeoff.move_id.state, 'posted')

        invoice.invalidate_recordset()
        # تسوية الرصيد المتبقي بالكامل
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)

    def test_05_writeoff_immutability_and_double_apply_prevention(self):
        """
        حصانة سجل الإعفاء بعد التطبيق:
        - منع إعادة التطبيق (Double Apply).
        - منع إعادة السجل إلى مسودة بعد التطبيق المالي.
        """
        order, _invoice = self._create_posted_bill(2000.0, 'WR-IMMUTABLE')
        writeoff = self.env['utility.writeoff'].create({
            'customer_id': self.customer.id,
            'sale_order_id': order.id,
            'amount': 2000.0,
            'reason': 'إعفاء كامل',
        })
        writeoff.action_approve()
        writeoff.action_apply()

        # محاولة التطبيق مرة أخرى
        with self.assertRaises(UserError):
            writeoff.action_apply()

        # محاولة إعادة السجل للمسودة
        with self.assertRaises(UserError):
            writeoff.action_draft()
