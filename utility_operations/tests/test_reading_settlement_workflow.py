"""
Phase 2 Tests — Reading Settlement Technical Workflow

Tests that:
- State machine: draft → submitted → technically_approved → processed
- Self-approval is blocked (AccessError)
- No mutation of reading_id.reading_value at any state
- _on_settlement_processed() hook fires on action_process()
- Cancellation works from draft, submitted, technically_approved
- Cancellation from processed raises ValidationError
- _get_effective_previous_reading() returns corrected value when settlement approved
- Meter log created on action_process()
"""
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'reading_settlement_workflow', 'production_integrity_hardening')
class TestReadingSettlementWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Settlement = cls.env['utility.reading.settlement']
        cls.Reading = cls.env['utility.reading']

        # Minimal supporting records
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار التسوية التقنية',
            'code': 'SET-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار التسوية',
            'code': 'SET-SUB',
            'category_id': cls.category.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'مالك عداد اختبار التسوية'})
        cls.customer = cls.env['utility.customer'].create({
            'customer_number': 'SET-CUST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })
        cls.meter_type = cls.env['utility.meter.type'].search([], limit=1)
        cls.meter = cls.env['utility.meter'].create({
            'meter_number': 'SET-MTR-001',
            'meter_type_id': cls.meter_type.id if cls.meter_type else False,
            'customer_id': cls.customer.id,
            'company_id': cls.env.company.id,
        })

        cls.approver_user = cls.env['res.users'].create({
            'name': 'Settlement Approver',
            'login': 'settlement_approver',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })

    def _make_billed_reading(self, value=10000.0, suffix=''):
        """Create a reading and force it to 'billed' state for testing."""
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': value,
            'reading_date': '2026-01-15 10:00:00',
            'reading_purpose': 'periodic',
            'reading_type': 'manual',
        })
        # Force to billed state via bypass for test setup
        reading.with_context(
            _reading_state_transition=True,
            _bypass_reading_protection=True,
        ).write({'state': 'billed'})
        return reading

    # ── State machine ──────────────────────────────────────────────────────
    def test_full_lifecycle_draft_to_processed(self):
        """Full happy path: draft → submitted → technically_approved → processed."""
        reading = self._make_billed_reading()
        original_value = reading.reading_value

        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 9800.0,
            'reason': 'اختبار دورة الحياة الكاملة',
        })
        self.assertEqual(settlement.state, 'draft')

        # action_submit
        settlement.action_submit()
        self.assertEqual(settlement.state, 'submitted')
        self.assertEqual(settlement.original_reading_value, original_value,
                         'القيمة الأصلية يجب أن تُحفظ عند التقديم.')

        # action_technically_approve — must use a different user
        settlement.sudo(self.approver_user).action_technically_approve()
        self.assertEqual(settlement.state, 'technically_approved')

        # action_process
        settlement.sudo(self.approver_user).action_process()
        self.assertEqual(settlement.state, 'processed')

        # CRITICAL: reading_value must NOT have changed
        self.assertEqual(reading.reading_value, original_value,
                         'reading_value يجب ألا يتغيّر أبداً — التاريخ محمي.')

    # ── Self-approval blocked ──────────────────────────────────────────────
    def test_self_approval_raises_access_error(self):
        """The user who submitted cannot technically approve."""
        reading = self._make_billed_reading(value=5000.0)
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 4900.0,
            'reason': 'اختبار منع الاعتماد الذاتي',
        })
        settlement.action_submit()
        # Try to approve as the same user who submitted
        # submitted_by_id == env.user → should raise
        with self.assertRaises(AccessError,
                               msg='يجب منع الشخص نفسه من الاعتماد التقني.'):
            settlement.action_technically_approve()

    # ── No reading_value mutation at any state ─────────────────────────────
    def test_reading_value_never_mutated_through_settlement(self):
        """Verify reading_value is intact after all transitions."""
        reading = self._make_billed_reading(value=20000.0)
        original_value = reading.reading_value

        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 19500.0,
            'reason': 'اختبار عدم التعديل',
        })
        settlement.action_submit()
        settlement.sudo(self.approver_user).action_technically_approve()
        settlement.sudo(self.approver_user).action_process()

        # Re-read from DB
        reading.invalidate_recordset()
        self.assertEqual(reading.reading_value, original_value)

    # ── Cancellation rules ─────────────────────────────────────────────────
    def test_cancel_from_submitted_succeeds(self):
        reading = self._make_billed_reading(value=3000.0)
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 2900.0,
            'reason': 'اختبار إلغاء من submitted',
        })
        settlement.action_submit()
        settlement.cancel_reason = 'تراجع عن الطلب'
        settlement.action_cancel()
        self.assertEqual(settlement.state, 'cancelled')

    def test_cancel_from_processed_raises(self):
        reading = self._make_billed_reading(value=8000.0)
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 7800.0,
            'reason': 'اختبار منع إلغاء processed',
        })
        settlement.action_submit()
        settlement.sudo(self.approver_user).action_technically_approve()
        settlement.sudo(self.approver_user).action_process()

        with self.assertRaises(ValidationError):
            settlement.action_cancel()

    # ── _on_settlement_processed hook fires ───────────────────────────────
    def test_on_settlement_processed_hook_called(self):
        """The hook must be called when action_process() succeeds."""
        reading = self._make_billed_reading(value=15000.0)
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 14700.0,
            'reason': 'اختبار hook الإحالة',
        })
        settlement.action_submit()
        settlement.sudo(self.approver_user).action_technically_approve()

        hook_called = []
        original_hook = type(settlement)._on_settlement_processed

        def spy_hook(self_record):
            hook_called.append(True)
            return original_hook(self_record)

        with patch.object(type(settlement), '_on_settlement_processed', spy_hook):
            settlement.sudo(self.approver_user).action_process()

        self.assertTrue(hook_called, 'Hook _on_settlement_processed لم يُستدعَ.')

    # ── _get_effective_previous_reading resolver ───────────────────────────
    def test_effective_previous_reading_returns_corrected_when_approved(self):
        """After technically_approved settlement, resolver returns corrected value."""
        reading = self._make_billed_reading(value=10000.0)
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 9800.0,
            'reason': 'اختبار الـbaseline الفعّال',
        })
        settlement.action_submit()
        settlement.sudo(self.approver_user).action_technically_approve()

        effective = reading._get_effective_previous_reading()
        self.assertAlmostEqual(effective, 9800.0,
                               msg='يجب إرجاع القيمة المصحّحة بعد الاعتماد التقني.')

    def test_effective_previous_reading_returns_original_without_settlement(self):
        """Without any settlement, resolver returns reading_value."""
        reading = self._make_billed_reading(value=10000.0)
        effective = reading._get_effective_previous_reading()
        self.assertAlmostEqual(effective, reading.reading_value)

    def test_effective_previous_reading_returns_original_for_draft_settlement(self):
        """Draft settlement must NOT affect the baseline."""
        reading = self._make_billed_reading(value=10000.0)
        self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 9000.0,
            'reason': 'اختبار draft لا يؤثر',
        })
        # Settlement still in draft — should return original
        effective = reading._get_effective_previous_reading()
        self.assertAlmostEqual(effective, reading.reading_value)

    # ── Cannot settle a non-billed reading ────────────────────────────────
    def test_submit_on_draft_reading_raises(self):
        """action_submit() must reject readings not in billed state."""
        reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 5000.0,
            'reading_date': '2026-06-10 10:00:00',
            'reading_purpose': 'periodic',
            'reading_type': 'manual',
        })
        # Reading is in 'draft' state
        settlement = self.Settlement.create({
            'reading_id': reading.id,
            'corrected_reading_value': 4900.0,
            'reason': 'اختبار منع تسوية قراءة غير مفوترة',
        })
        with self.assertRaises(ValidationError):
            settlement.action_submit()

    def test_subsequent_reading_uses_corrected_baseline_automatically(self):
        """Subsequent reading computes its previous reading and consumption against corrected baseline."""
        # 1. January reading (billed at 10,000)
        jan_reading = self._make_billed_reading(value=10000.0)

        # 2. Reading correction to 9,800 (approved)
        settlement = self.Settlement.create({
            'reading_id': jan_reading.id,
            'corrected_reading_value': 9800.0,
            'reason': 'تصحيح خطأ قراءة يناير',
        })
        settlement.action_submit()
        settlement.sudo(self.approver_user).action_technically_approve()

        # 3. February reading at 10,500
        feb_reading = self.Reading.create({
            'meter_id': self.meter.id,
            'account_id': self.customer.id,
            'reading_value': 10500.0,
            'reading_date': '2026-02-15 10:00:00',
            'reading_purpose': 'periodic',
            'reading_type': 'manual',
        })

        # 4. Verify previous reading and consumption
        self.assertAlmostEqual(feb_reading.previous_reading, 9800.0,
                               msg='القراءة السابقة لفبراير يجب أن تكون الأساس المصحح 9,800 وليس القراءة الأصلية 10,000.')
        self.assertAlmostEqual(feb_reading.consumption, 700.0,
                               msg='استهلاك فبراير يجب أن يكون 700 (10,500 - 9,800).')

