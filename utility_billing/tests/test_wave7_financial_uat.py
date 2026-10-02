from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestWave7FinancialUAT(TransactionCase):
    """Deterministic end-to-end UAT for the Wave 7 financial chain."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Customer = cls.env['utility.customer']
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Account = cls.env['account.account']
        cls.Product = cls.env['product.product']
        cls.Move = cls.env['account.move']
        cls.Payment = cls.env['account.payment']

        cls.category = cls.Category.create({
            'name': 'فئة UAT المالي Wave 7',
            'code': 'W7-UAT-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع UAT المالي Wave 7',
            'code': 'W7-UAT-SUB',
            'category_id': cls.category.id,
        })
        cls.income = cls.Account.search([
            ('company_ids', 'in', [cls.env.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.sale_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        cls.bank_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'bank'),
        ], limit=1)
        if not cls.income or not cls.sale_journal or not cls.bank_journal:
            raise ValidationError('بيئة UAT تحتاج حساب دخل ويومية مبيعات وبنك.')

        cls.company = cls.env.company
        cls.deposit_clearing = cls.company.deposit_clearing_account_id
        if not cls.deposit_clearing:
            cls.deposit_clearing = cls.Account.create({
                'name': 'حساب مقاصة إيداع UAT Wave 7',
                'code': 'W7DEP01',
                'account_type': 'asset_current',
                'reconcile': True,
                'company_ids': [(6, 0, [cls.company.id])],
            })
            cls.company.deposit_clearing_account_id = cls.deposit_clearing
        elif not cls.deposit_clearing.reconcile:
            cls.deposit_clearing.reconcile = True
        cls.settlement_journal = cls.company.settlement_journal_id
        if not cls.settlement_journal:
            cls.settlement_journal = cls.env['account.journal'].create({
                'name': 'يومية تسويات UAT Wave 7',
                'code': 'W7STL',
                'type': 'general',
                'company_id': cls.company.id,
            })
            cls.company.settlement_journal_id = cls.settlement_journal
        if not cls.bank_journal.default_account_id:
            raise ValidationError('يومية البنك في بيئة UAT يجب أن تحتوي حساب سيولة.')
        if not cls.bank_journal.suspense_account_id:
            cls.bank_journal.suspense_account_id = cls.deposit_clearing

        cls.product = cls.Product.create({
            'name': 'منتج UAT مالي Wave 7',
            'type': 'service',
            'invoice_policy': 'order',
        })
        cls.product.property_account_income_id = cls.income
        cls.template = cls.env['utility.contract.template'].create({
            'name': 'قالب إعادة فوترة UAT Wave 7',
            'code': 'W7-UAT-TPL',
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
            'price_per_kwh': 1.0,
        })
        cls.env['utility.contract.template.line'].create({
            'template_id': cls.template.id,
            'product_id': cls.product.id,
            'name': 'مكوّن إعادة فوترة UAT',
            'meter_line_type': 'consumption',
        })

        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'نوع فترة UAT Wave 7',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        cls.reading_period = cls.env['date.range'].create({
            'name': 'فترة قراءة UAT Wave 7',
            'period_code': 'W7-UAT-READING',
            'cycle_key': 'W7-UAT-READING',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'type_id': range_type.id,
            'date_start': '2099-01-01',
            'date_end': '2099-01-31',
            'state': 'open',
        })
        cls.payment_period = cls.env['date.range'].create({
            'name': 'فترة دفع UAT Wave 7',
            'period_code': 'W7-UAT-PAYMENT',
            'cycle_key': 'W7-UAT-PAYMENT',
            'period_role': 'payment',
            'billing_cadence': 'monthly',
            'reading_period_id': cls.reading_period.id,
            'date_start': '2099-02-01',
            'date_end': '2099-02-28',
            'state': 'open',
        })

    def _create_collector(self, suffix):
        role = self.env.ref('utility_core.role_collector')
        return self.env['utility.staff'].create({
            'name': 'محصل UAT Wave 7 %s' % suffix,
            'employee_code': 'W7-%s' % suffix,
            'company_id': self.company.id,
            'role_ids': [(6, 0, [role.id])],
        })

    def _create_invoice(self, suffix='BASE', amount=1000.0):
        partner = self.Partner.create({'name': 'عميل UAT المالي Wave 7 %s' % suffix})
        customer = self.Customer.create({
            'customer_number': 'W7-UAT-%s' % suffix,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'customer_id': customer.id,
            'date_range_id': self.reading_period.id,
            'period_start': self.reading_period.date_start,
            'period_end': self.reading_period.date_end,
            'previous_reading': 0.0,
            'current_reading': amount,
            'consumption': amount,
        })
        invoice = self.Move.create({
            'move_type': 'out_invoice',
            'journal_id': self.sale_journal.id,
            'partner_id': partner.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'UAT استهلاك كهرباء',
                'quantity': 1.0,
                'price_unit': amount,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        return customer, order, invoice

    def _create_payment(self, order, invoice, amount, reference,
                        payment_method='bank', collector=None):
        payment = self.Payment.create({
            'utility_sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'partner_id': order.partner_id.id,
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'utility_payment_method': payment_method,
            'journal_id': self.bank_journal.id if payment_method != 'cash' else False,
            'collector_id': collector.id if collector else False,
            'date_range_id': self.payment_period.id,
            'date': date(2099, 2, 10),
            'electronic_doc_no': reference,
        })
        payment.action_post()
        return payment

    def _create_posted_collector_settlement(self, suffix='COLL'):
        _customer, order, invoice = self._create_invoice(suffix, 100.0)
        collector = self._create_collector(suffix)
        payment = self._create_payment(
            order, invoice, 100.0, 'W7-%s-PAY' % suffix,
            payment_method='cash', collector=collector)
        collection = self.env['utility.collection'].search([
            ('payment_id', '=', payment.id),
        ], limit=1)
        self.assertEqual(collection.state, 'posted')
        settlement = self.env['utility.collection.settlement'].create({
            'company_id': self.company.id,
            'collector_id': collector.id,
            'currency_id': self.company.currency_id.id,
            'declared_amount': 100.0,
            'settlement_method': 'bank_transfer',
            'line_ids': [(0, 0, {
                'collection_id': collection.id,
                'amount': 100.0,
            })],
        })
        settlement.action_confirm()
        settlement.action_post()
        self.assertEqual(settlement.state, 'posted')
        self.assertEqual(collection.state, 'settled')
        self.assertEqual(settlement.account_move_id.state, 'posted')
        return settlement

    def test_partial_payments_preserve_accounting_residual(self):
        _customer, order, invoice = self._create_invoice()
        first = self._create_payment(order, invoice, 600.0, 'W7-UAT-P1')
        invoice.invalidate_recordset()
        self.assertEqual(first.state, 'posted')
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)
        self.assertEqual(first.allocation_count, 1)
        self.assertAlmostEqual(
            first.allocation_ids.allocated_amount, 600.0, places=2)
        self.assertTrue(first.allocation_ids.partial_reconcile_ids)

        second = self._create_payment(order, invoice, 400.0, 'W7-UAT-P2')
        invoice.invalidate_recordset()
        self.assertEqual(second.state, 'posted')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertEqual(second.allocation_count, 1)
        # Bank journals may remain ``in_payment`` until the bank statement
        # clears the outstanding account; the receivable invariant is already
        # proven by the zero residual and exact partial reconciliations.
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    def test_overpayment_is_rejected_before_accounting_post(self):
        _customer, order, invoice = self._create_invoice()
        self._create_payment(order, invoice, 600.0, 'W7-UAT-P3')
        with self.assertRaises(ValidationError):
            self._create_payment(order, invoice, 500.0, 'W7-UAT-P4')
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)

    def test_cash_collection_collector_settlement_is_posted_exactly_once(self):
        settlement = self._create_posted_collector_settlement('COLL-UAT')
        move = settlement.account_move_id
        clearing_lines = move.line_ids.filtered(
            lambda line: line.account_id == self.deposit_clearing)
        self.assertEqual(len(clearing_lines), 1)
        self.assertAlmostEqual(clearing_lines.debit, 100.0, places=2)
        self.assertAlmostEqual(
            sum(move.line_ids.filtered(lambda line: line.credit).mapped('credit')),
            100.0, places=2)

    def test_bank_settlement_reconciles_collector_deposit(self):
        source = self._create_posted_collector_settlement('BANK-UAT')
        reference = 'W7-BANK-UAT-REF'
        bank_settlement = self.env['utility.bank.settlement'].create({
            'company_id': self.company.id,
            'bank_journal_id': self.bank_journal.id,
            'bank_account_id': self.bank_journal.default_account_id.id,
            'currency_id': self.company.currency_id.id,
            'bank_reference': reference,
            'collector_id': source.collector_id.id,
            'deposit_amount': 100.0,
        })
        bank_settlement.action_confirm()
        bank_settlement.action_post()
        self.assertEqual(bank_settlement.state, 'settled')
        self.assertTrue(bank_settlement.created_automatically)
        self.assertEqual(bank_settlement.settlement_key, 'BANK-DEPOSIT:%s:%s' % (
            self.company.id, reference))
        self.assertTrue(bank_settlement.account_move_id)
        self.assertEqual(source.state, 'reconciled')
        self.assertTrue(self.env['account.partial.reconcile'].search([
            '|',
            ('debit_move_id', 'in', source.account_move_id.line_ids.ids),
            ('credit_move_id', 'in', bank_settlement.account_move_id.line_ids.ids),
        ], limit=1))

    def test_billing_adjustment_after_partial_payment_preserves_payment_audit(self):
        customer, order, invoice = self._create_invoice('ADJ-UAT', 1000.0)
        payment = self._create_payment(order, invoice, 600.0, 'W7-ADJ-PAY')
        adjustment = self.env['utility.billing.adjustment'].create({
            'customer_id': customer.id,
            'billing_period_id': self.reading_period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'تصحيح بعد تحصيل جزئي - UAT Wave 7',
            'corrected_amount': 900.0,
        })
        adjustment.action_submit()
        adjustment.action_approve()
        adjustment.action_apply_correction()
        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.credit_note_id.state, 'posted')
        self.assertAlmostEqual(adjustment.credit_note_id.amount_total, 100.0, places=2)
        self.assertEqual(payment.state, 'posted')
        self.assertTrue(payment.allocation_ids.partial_reconcile_ids)
        with self.assertRaises(ValidationError):
            adjustment.action_apply_correction()

    def test_full_rebilling_after_partial_payment_preserves_traceability(self):
        customer, order, invoice = self._create_invoice('REBILL-UAT', 1000.0)
        payment = self._create_payment(order, invoice, 400.0, 'W7-REBILL-PAY')
        adjustment = self.env['utility.billing.adjustment'].create({
            'customer_id': customer.id,
            'billing_period_id': self.reading_period.id,
            'sale_order_id': order.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'consumption_correction',
            'reason': 'إعادة فوترة بعد تحصيل جزئي - UAT Wave 7',
            'rebill': True,
            'corrected_consumption': 900.0,
            'corrected_amount': 900.0,
        })
        adjustment.action_submit()
        adjustment.action_approve()
        adjustment.action_apply_correction()
        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.credit_note_id.reversed_entry_id, invoice)
        self.assertEqual(adjustment.credit_note_id.state, 'posted')
        self.assertEqual(adjustment.replacement_sale_order_id.replacement_of_id, order)
        self.assertEqual(adjustment.replacement_sale_order_id.consumption, 900.0)
        self.assertEqual(adjustment.replacement_invoice_id.state, 'posted')
        self.assertEqual(payment.state, 'posted')

        # Final exposure is intentionally measured as a signed portfolio
        # balance.  The payment stays allocated to the original invoice;
        # the full credit note and replacement invoice remain auditable
        # outstanding documents until an explicit reconciliation is made.
        credit_note = adjustment.credit_note_id
        replacement_invoice = adjustment.replacement_invoice_id
        self.assertAlmostEqual(invoice.amount_residual, 600.0, places=2)
        self.assertAlmostEqual(credit_note.amount_residual, 1000.0, places=2)
        self.assertAlmostEqual(replacement_invoice.amount_residual, 900.0, places=2)
        signed_exposure = (
            invoice.amount_residual
            - credit_note.amount_residual
            + replacement_invoice.amount_residual
        )
        self.assertAlmostEqual(signed_exposure, 500.0, places=2)
