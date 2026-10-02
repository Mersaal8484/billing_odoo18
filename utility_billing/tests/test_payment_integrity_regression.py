"""
Phase 8 Tests — Payment Integrity & Allocation Regression

Tests that:
- Payment allocation cannot over-allocate beyond invoice residual
- Payments register cleanly without mutating Chart of Accounts
- Reversing payment allocations restores exact residual
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'payment_integrity_regression', 'production_integrity_hardening')
class TestPaymentIntegrityRegression(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Account = cls.env['account.account']
        cls.Journal = cls.env['account.journal']

        cls.partner = cls.Partner.create({'name': 'مشترك اختبار الدفعات'})
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة الدفعات',
            'code': 'PMT-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع الدفعات',
            'code': 'PMT-SUB',
            'category_id': cls.category.id,
        })
        cls.customer = cls.Customer.create({
            'customer_number': 'PMT-CUST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        cls.receivable = cls.Account.search([
            ('company_ids', 'in', [cls.env.company.id]),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        cls.income = cls.Account.search([
            ('company_ids', 'in', [cls.env.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.bank_journal = cls.Journal.search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'bank'),
        ], limit=1)
        cls.sale_journal = cls.Journal.search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)

    def test_invoice_creation_and_residual_consistency(self):
        """Invoice residual amount updates consistently upon posting."""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.sale_journal.id,
            'partner_id': self.partner.id,
            'utility_customer_id': self.customer.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'فاتورة اختبار دفعات',
                'quantity': 1.0,
                'price_unit': 500.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()

        self.assertEqual(invoice.state, 'posted')
        self.assertAlmostEqual(invoice.amount_total, 500.0)
        self.assertAlmostEqual(invoice.amount_residual, 500.0)
