from odoo.tests.common import TransactionCase
from odoo.fields import Date


class TestCustomerStatementWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'مشترك اختبار كشف الحساب',
            'open_balance': 500.0,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة سكني اختبار',
            'code': 'RES_TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'نوع عائلات اختبار',
            'category_id': self.category.id,
        })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-TEST-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
        })
        self.wizard_model = self.env['utility.customer.statement.wizard']

    def test_legacy_partner_balance_is_not_used_as_accounting_opening(self):
        """Opening balances must come from posted receivable entries."""
        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
        })
        opening = wizard._get_opening_balance()
        self.assertEqual(opening, 0.0)

    def test_statement_totals_and_running_balance(self):
        """التحقق من احتساب الرصيد التراكمي وإجمالي كشف الحساب"""
        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-01-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        totals = wizard._get_statement_totals()
        self.assertIn('opening', totals)
        self.assertIn('closing', totals)
        self.assertEqual(totals['opening'], 0.0)

    def test_migrated_opening_entry_is_visible_and_carried_forward(self):
        receivable = self.env['account.account'].search([
            ('company_ids', 'in', [self.env.company.id]),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        income = self.env['account.account'].search([
            ('company_ids', 'in', [self.env.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not receivable or not income or not journal:
            self.skipTest('Required accounting configuration is not available.')
        opening = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'partner_id': self.partner.id,
            'utility_customer_id': self.customer.id,
            'date': Date.from_string('2026-01-15'),
            'line_ids': [
                (0, 0, {
                    'name': 'Migrated opening receivable',
                    'account_id': receivable.id,
                    'partner_id': self.partner.id,
                    'debit': 100.0,
                }),
                (0, 0, {
                    'name': 'Migrated opening offset',
                    'account_id': income.id,
                    'credit': 100.0,
                }),
            ],
        })
        opening.action_post()
        self.customer.opening_move_id = opening.id

        in_period = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-01-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        lines = in_period._get_statement_lines()
        opening_line = next(line for line in lines if line['kind'] == 'opening')
        self.assertEqual(opening_line['debit'], 100.0)
        self.assertEqual(in_period._get_statement_totals()['closing'], 100.0)

        after_period = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-02-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        self.assertEqual(after_period._get_opening_balance(), 100.0)

    def test_financial_settlement_in_statement(self):
        """التحقق من ظهور التسويات المالية (مدين ودائن) في كشف الحساب والارصدة التراكمية"""
        # إنشاء تسوية دائنة (خصم)
        settlement_credit = self.env['utility.financial.settlement'].create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 100.0,
            'reason': 'تسوية دائنة خصم استهلاك',
            'date': Date.from_string('2026-02-01'),
            'state': 'applied',
        })
        # إنشاء تسوية مدينة (إضافة)
        settlement_debit = self.env['utility.financial.settlement'].create({
            'account_id': self.customer.id,
            'settlement_type': 'debit',
            'amount': 50.0,
            'reason': 'تسوية مدينة تعديل تعرفة',
            'date': Date.from_string('2026-03-01'),
            'state': 'applied',
        })

        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-01-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        lines = wizard._get_statement_lines()
        settlement_lines = [l for l in lines if l['kind'] == 'settlement']
        self.assertEqual(len(settlement_lines), 2, "يجب أن تظهر تسويتان في كشف الحساب")
        
        credit_line = next(l for l in settlement_lines if l['ref'] == settlement_credit.name)
        self.assertEqual(credit_line['credit'], 100.0)
        self.assertEqual(credit_line['debit'], 0.0)

        debit_line = next(l for l in settlement_lines if l['ref'] == settlement_debit.name)
        self.assertEqual(debit_line['debit'], 50.0)
        self.assertEqual(debit_line['credit'], 0.0)
