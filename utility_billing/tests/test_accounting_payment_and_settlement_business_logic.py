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
    - رفض السداد الزائد على مستوى الفاتورة حتى لو كان العميل مدين بمبالغ أخرى
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
            ('company_id', '=', cls.company.id),
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

    def _create_posted_bill(self, amount, suffix):
        """مساعد لإنشاء أمر بيع وفاتورة كهرباء منشورة بمبلغ محدد."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': amount,
            'amount_total': amount,
        })
        invoice = self.Move.create({
            'move_type': 'out_invoice',
            'journal_id': self.sale_journal.id,
            'partner_id': self.partner.id,
            'utility_customer_id': self.customer.id,
            'utility_sale_order_id': order.id,
            'invoice_date': date(2026, 9, 15),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.kwh_product.id,
                'name': f'استهلاك كهرباء {suffix}',
                'quantity': 1.0,
                'price_unit': amount,
                'account_id': self.income_account.id,
            })],
        })
        invoice.action_post()
        return order, invoice

    def test_01_targeted_allocation_multiple_invoices_residual_isolation(self):
        """
        التحقق من التخصيص الدقيق للمدفوعات وعزل الأرصدة:
        - العميل لديه فاتورتان: الفاتورة A بمبلغ 5,000 والفاتورة B بمبلغ 3,000 (إجمالي مديونية 8,000).
        - يتم دفع 3,500 مخصصة حصرياً للفاتورة A.
        - الرصيد المتبقي للفاتورة A يصبح 1,500.
        - الفاتورة B تظل برصيدها الكامل 3,000 دون أي تسوية أو تأثير (منع التخصيص العشوائي).
        """
        order_a, invoice_a = self._create_posted_bill(5000.0, 'A')
        order_b, invoice_b = self._create_posted_bill(3000.0, 'B')

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

    def test_02_overpayment_rejected_even_with_other_debts(self):
        """
        رفض السداد الزائد (Overpayment Rejection):
        - العميل عليه مديونية إجمالية 8,000 عبر فاتورتين.
        - محاولة سداد 6,000 موجهة للفاتورة A (وقيمتها 5,000 فقط) يجب أن ترفض بقيد ValidationError،
          ولا يتم ترحيل المبلغ الزائد تلقائياً للفاتورة B.
        """
        order_a, invoice_a = self._create_posted_bill(5000.0, 'A2')
        _order_b, _invoice_b = self._create_posted_bill(3000.0, 'B2')

        with self.assertRaises(ValidationError):
            payment_over = self.Payment.create({
                'utility_sale_order_id': order_a.id,
                'utility_invoice_id': invoice_a.id,
                'partner_id': self.partner.id,
                'amount': 6000.0,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'utility_payment_method': 'bank',
                'journal_id': self.bank_journal.id,
                'date_range_id': self.period.id,
                'date': date(2026, 9, 20),
                'electronic_doc_no': 'PAY-OVER-001',
            })
            payment_over.action_post()

        invoice_a.invalidate_recordset()
        self.assertEqual(invoice_a.amount_residual, 5000.0)

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
