"""
Phase 1 Tests — Billing Adjustment Debit Path & Historical Pricing Context

Tests that:
- difference > 0  → out_invoice (debit_invoice_id set)
- difference < 0  → out_refund  (credit_note_id set, existing behaviour preserved)
- difference == 0 → no accounting document
- Applied integrity constraint allows debit or credit (not both required)
- Credit-only guard (old line 376) is removed
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'billing_adjustment_debit', 'production_integrity_hardening')
class TestBillingAdjustmentDebit(TransactionCase):

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
        cls.Adjustment = cls.env['utility.billing.adjustment']

        cls.category = cls.Category.create({
            'name': 'فئة اختبار التعديل المزدوج',
            'code': 'ADJ-DUAL-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع اختبار التعديل المزدوج',
            'code': 'ADJ-DUAL-SUB',
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
            raise ValidationError('اختبارات التعديل المزدوج تحتاج حساب إيراد ودفتر مبيعات.')

        cls.product = cls.Product.create({
            'name': 'منتج اختبار التعديل المزدوج',
            'type': 'service',
        })
        cls.product.property_account_income_id = cls.income

        cls.template = cls.env['utility.contract.template'].create({
            'name': 'قالب اختبار التعديل المزدوج',
            'code': 'ADJ-DUAL-TPL',
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
            'price_per_kwh': 1.0,
            'service_charge': 10.0,
        })
        cls.env['utility.contract.template.line'].create([
            {
                'template_id': cls.template.id,
                'product_id': cls.product.id,
                'name': 'استهلاك',
                'meter_line_type': 'consumption',
            },
            {
                'template_id': cls.template.id,
                'product_id': cls.product.id,
                'name': 'خدمة',
                'meter_line_type': 'service_charge',
            },
        ])
        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'نوع فترة اختبار التعديل المزدوج',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار التعديل المزدوج',
            'period_code': 'ADJ-DUAL-2026-08',
            'cycle_key': 'ADJ-DUAL-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _make_chain(self, suffix, original_amount=1000.0):
        """Create a customer, sale.order and posted invoice chain."""
        partner = self.Partner.create({'name': 'مالك اختبار التعديل %s' % suffix})
        customer = self.Customer.create({
            'customer_number': 'ADJ-DUAL-%s' % suffix,
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
            'current_reading': 1000.0,
            'consumption': 1000.0,
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
                'name': 'فاتورة أصلية %s' % suffix,
                'quantity': 1.0,
                'price_unit': original_amount,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        return customer, order, invoice

    def _approve_and_apply(self, adj):
        """Submit → approve → apply an adjustment using admin user (env.su)."""
        adj.action_submit()
        # Approve: must be a different user — use sudo to bypass in tests
        adj.sudo().action_approve()
        adj.sudo().action_apply_correction()
        return adj

    # ── Test: Downward correction → Credit Note ────────────────────────────
    def test_negative_difference_creates_credit_note(self):
        """difference < 0  → credit_note_id set, debit_invoice_id is False."""
        customer, order, invoice = self._make_chain('CN-1', original_amount=1000.0)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار تصحيح تنازلي',
            'corrected_amount': 800.0,   # 800 < 1000 → difference = -200
        })
        self._approve_and_apply(adj)

        self.assertEqual(adj.state, 'applied')
        self.assertTrue(adj.credit_note_id, 'يجب إنشاء إشعار دائن للتصحيح التنازلي.')
        self.assertEqual(adj.credit_note_id.move_type, 'out_refund')
        self.assertEqual(adj.credit_note_id.state, 'posted')
        self.assertFalse(adj.debit_invoice_id, 'لا يجب إنشاء فاتورة مدين للتصحيح التنازلي.')

    # ── Test: Upward correction → Debit Invoice ────────────────────────────
    def test_positive_difference_creates_debit_invoice(self):
        """difference > 0  → debit_invoice_id set, credit_note_id is False."""
        customer, order, invoice = self._make_chain('DI-1', original_amount=1000.0)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار تصحيح تصاعدي — قراءة أقل من الفعلي',
            'corrected_amount': 1300.0,  # 1300 > 1000 → difference = +300
        })
        self._approve_and_apply(adj)

        self.assertEqual(adj.state, 'applied')
        self.assertTrue(adj.debit_invoice_id, 'يجب إنشاء فاتورة مدين للتصحيح التصاعدي.')
        self.assertEqual(adj.debit_invoice_id.move_type, 'out_invoice')
        self.assertEqual(adj.debit_invoice_id.state, 'posted')
        self.assertFalse(adj.credit_note_id, 'لا يجب إنشاء إشعار دائن للتصحيح التصاعدي.')

    # ── Test: Zero difference → No accounting document ─────────────────────
    def test_zero_difference_creates_no_document(self):
        """difference == 0 → no credit_note_id, no debit_invoice_id."""
        customer, order, invoice = self._make_chain('ZERO-1', original_amount=1000.0)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'تصحيح بدون أثر مالي — تسوية إدارية',
            'corrected_amount': 1000.0,  # Same → difference = 0
        })
        self._approve_and_apply(adj)

        self.assertEqual(adj.state, 'applied')
        self.assertFalse(adj.credit_note_id, 'لا يجب إنشاء إشعار دائن للفرق الصفري.')
        self.assertFalse(adj.debit_invoice_id, 'لا يجب إنشاء فاتورة مدين للفرق الصفري.')

    # ── Test: Old credit-only guard removed ────────────────────────────────
    def test_positive_difference_no_longer_raises_validation_error(self):
        """The old guard 'difference_amount >= 0 → raise' must not exist."""
        customer, order, invoice = self._make_chain('OLD-GUARD', original_amount=500.0)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'تأكيد إزالة الحراسة القديمة',
            'corrected_amount': 700.0,   # difference = +200
        })
        # Must NOT raise — this was the old behaviour that is now fixed
        try:
            self._approve_and_apply(adj)
        except ValidationError as e:
            if 'يدعم تخفيض الفاتورة' in str(e):
                self.fail('الحراسة القديمة لا تزال موجودة — يجب إزالتها.')
            raise
        self.assertEqual(adj.state, 'applied')

    # ── Test: Debit invoice uses same revenue account as original ──────────
    def test_debit_invoice_uses_original_revenue_account(self):
        """Debit invoice account_id must match the original invoice's line account."""
        customer, order, invoice = self._make_chain('ACCT-CHK', original_amount=1000.0)
        original_account = invoice.invoice_line_ids[:1].account_id
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار الحساب المستخدم في فاتورة المدين',
            'corrected_amount': 1500.0,
        })
        self._approve_and_apply(adj)

        debit_line = adj.debit_invoice_id.invoice_line_ids[:1]
        self.assertEqual(
            debit_line.account_id, original_account,
            'فاتورة المدين يجب أن تستخدم نفس حساب الإيراد للفاتورة الأصلية.'
        )

    # ── Test: Integrity constraint accepts debit_invoice_id alone ──────────
    def test_applied_integrity_accepts_debit_without_credit(self):
        """_check_applied_integrity must not fail when only debit_invoice_id is set."""
        customer, order, invoice = self._make_chain('INT-CHK', original_amount=1000.0)
        adj = self.Adjustment.create({
            'customer_id': customer.id,
            'billing_period_id': self.period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار قيد النزاهة مع فاتورة المدين فقط',
            'corrected_amount': 1200.0,
        })
        # Should not raise ValidationError from _check_applied_integrity
        self._approve_and_apply(adj)
        self.assertEqual(adj.state, 'applied')
        self.assertTrue(adj.debit_invoice_id)
        self.assertFalse(adj.credit_note_id)
        # Trigger the constraint explicitly to confirm it passes
        adj._check_applied_integrity()
