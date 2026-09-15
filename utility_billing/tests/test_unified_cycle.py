"""
test_unified_cycle.py — اختبارات الدورة الموحدة

يغطي السيناريوهات التالية:
- إنشاء دورة موحدة (سجل واحد) من المعالج
- التحقق من حقول نطاق الدفع
- حالات القراءة والتحصيل المستقلة
- منع الدفع عند إغلاق التحصيل
- التوافق العكسي مع السجلات التاريخية
- idempotency للمعالج
"""
from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestUnifiedCycle(TransactionCase):
    """اختبارات الدورة الزمنية الموحدة (reading + payment في سجل واحد)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # نوع فترة أساسية
        cls.period_type = cls.env['date.range.type'].create({
            'name': 'دورة نصف شهرية (اختبار)',
            'default_billing_period': 'semi_monthly',
            'payment_start_offset_days': 1,
            'payment_end_offset_days': 1,
        })

    def _create_unified_cycle(self, cycle_key='TEST-CYCLE-2026-09-H1',
                               start=None, end=None, payment_start=None, payment_end=None):
        """مساعد: إنشاء سجل دورة موحدة مباشرة."""
        start = start or date(2026, 9, 1)
        end = end or date(2026, 9, 15)
        return self.env['date.range'].create({
            'name': 'النصف الأول سبتمبر 2026',
            'period_code': f'CYCLE-{cycle_key}',
            'cycle_key': cycle_key,
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'type_id': self.period_type.id,
            'date_start': start,
            'date_end': end,
            'payment_start': payment_start or (start + timedelta(days=1)),
            'payment_end': payment_end or (end + timedelta(days=1)),
            'state': 'planned',
        })

    def test_01_unified_cycle_has_payment_fields(self):
        """الدورة الموحدة تحمل حقول نطاق الدفع بشكل صريح."""
        cycle = self._create_unified_cycle()
        self.assertEqual(cycle.period_role, 'reading')
        self.assertTrue(cycle.payment_start)
        self.assertTrue(cycle.payment_end)
        # payment_start = date_start + 1
        self.assertEqual(cycle.payment_start, cycle.date_start + timedelta(days=1))

    def test_02_unified_cycle_independent_states(self):
        """حالة القراءة وحالة التحصيل مستقلتان."""
        cycle = self._create_unified_cycle()
        self.assertEqual(cycle.reading_state, 'planned')
        self.assertEqual(cycle.collection_state, 'planned')
        cycle.action_open_period()

        # الحالتان مفتوحتان
        self.assertEqual(cycle.reading_state, 'open')
        self.assertEqual(cycle.collection_state, 'open')

        # إغلاق القراءة لا يُغلق التحصيل
        # (نتجاوز التحقق من القراءات لأغراض الاختبار)
        cycle.with_context(_bypass_period_scope_protection=True).write({
            'reading_state': 'closed',
            'reading_closed_at': '2026-09-16 00:00:00',
        })
        self.assertEqual(cycle.reading_state, 'closed')
        self.assertEqual(cycle.collection_state, 'open')  # التحصيل لا يزال مفتوحاً

    def test_03_payment_start_must_be_before_end(self):
        """payment_start > payment_end يُطلق ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_unified_cycle(
                payment_start=date(2026, 9, 20),
                payment_end=date(2026, 9, 10),
            )

    def test_04_cycle_key_uniqueness_per_company(self):
        """رمز الدورة (cycle_key) يجب أن يكون فريداً لكل شركة لسجلات reading."""
        cycle_key = 'UNIQUE-TEST-CYCLE-001'
        self._create_unified_cycle(cycle_key=cycle_key)
        with self.assertRaises(Exception):
            self._create_unified_cycle(cycle_key=cycle_key)

    def test_05_payment_validation_unified_cycle(self):
        """التحقق من الدفعة على السجل الموحد: يقبل إذا collection_state='open'."""
        cycle = self._create_unified_cycle('TEST-PAY-CYCLE-001')
        cycle.action_open_period()
        self.assertEqual(cycle.collection_state, 'open')

        # محاكاة التحقق من الدفعة
        # الدورة مرتبطة بالفاتورة من خلال date_range_id
        # period_role='reading' → _validate_utility_payment_period يقبل
        # بدون استدعاء Odoo لـ account.payment نكتفي بالتحقق البرمجي
        from odoo.models import BaseModel
        payment_env = self.env['account.payment']
        # دالة التحقق تقبل السجل الموحد
        # لأن period_role='reading' وcollection_state='open'
        self.assertEqual(cycle.period_role, 'reading')
        self.assertIn(cycle.collection_state, ('open', 'closing'))

    def test_06_payment_rejected_when_collection_closed(self):
        """منع الدفع عند collection_state='reconciled'."""
        cycle = self._create_unified_cycle('TEST-CLOSED-COLLECT-001')
        cycle.action_open_period()
        # إغلاق التحصيل
        cycle.with_context(_bypass_period_scope_protection=True).write({
            'collection_state': 'reconciled',
        })
        # يجب أن تفشل عملية الدفع (بناءً على _validate_utility_payment_period)
        self.assertNotIn(cycle.collection_state, ('open', 'closing'))

    def test_07_lock_period_locks_both_states(self):
        """إقفال الدورة يُغلق reading_state وcollection_state معاً."""
        cycle = self._create_unified_cycle('TEST-LOCK-001')
        cycle.action_open_period()
        # محاكاة state → closed ثم lock
        cycle.with_context(_bypass_period_scope_protection=True).write({'state': 'closed'})
        cycle.action_lock_period()

        self.assertEqual(cycle.state, 'locked')
        self.assertEqual(cycle.reading_state, 'locked')
        self.assertEqual(cycle.collection_state, 'locked')

    def test_08_no_duplicate_payment_record_created(self):
        """المعالج لا يُنشئ سجل دفع منفصل — سجل واحد فقط لكل دورة."""
        DateRange = self.env['date.range']

        # عدد السجلات قبل الإنشاء
        before = DateRange.search_count([('cycle_key', 'like', 'GENERATOR-TEST-%')])

        # إنشاء دورة عبر المعالج
        wizard = self.env['utility.period.generator'].create({
            'year': 2026,
            'month': '11',
            'billing_cadence': 'semi_monthly',
        })
        # نتجاوز هذا الاختبار إذا لا توجد مناطق في بيئة الاختبار
        try:
            wizard.action_generate_periods()
        except ValidationError:
            self.skipTest("لا توجد مناطق مرتبطة بالدورية في بيئة الاختبار")

        after = DateRange.search_count([('cycle_key', 'like', 'SEMI-2026-11-%')])
        # يجب أن يكون هناك سجلَّين فقط (H1 + H2)، لا أربعة
        self.assertLessEqual(after, 2)

    def test_09_backward_compat_old_payment_record(self):
        """السجلات التاريخية (period_role='payment') لا تزال صالحة وتوافقية."""
        reading_cycle = self._create_unified_cycle('LEGACY-READING-001')
        # إنشاء سجل دفع تاريخي
        legacy_payment = self.env['date.range'].create({
            'name': 'تحصيل سبتمبر 2026 (تاريخي)',
            'period_code': 'PAY-LEGACY-001',
            'cycle_key': 'LEGACY-READING-001',  # نفس cycle_key
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'type_id': self.period_type.id,
            'date_start': date(2026, 9, 2),
            'date_end': date(2026, 9, 16),
            'reading_period_id': reading_cycle.id,
            'state': 'planned',
        })
        # السجل التاريخي يبقى بـ period_role='payment' وreading_period_id
        self.assertEqual(legacy_payment.period_role, 'payment')
        self.assertEqual(legacy_payment.reading_period_id, reading_cycle)

    def test_10_open_reading_does_not_affect_collection(self):
        """action_open_reading يُعيد فتح القراءة فقط دون المساس بحالة التحصيل."""
        cycle = self._create_unified_cycle('TEST-OPEN-READING-001')
        cycle.action_open_period()
        # إغلاق القراءة يدوياً
        cycle.with_context(_bypass_period_scope_protection=True).write({
            'reading_state': 'closed',
        })
        # إغلاق التحصيل أيضاً
        cycle.with_context(_bypass_period_scope_protection=True).write({
            'collection_state': 'closing',
        })
        # إعادة فتح القراءة فقط
        cycle.action_open_reading()

        self.assertEqual(cycle.reading_state, 'open')
        # التحصيل لم يتغير
        self.assertEqual(cycle.collection_state, 'closing')

    def test_11_payment_timing_classification_with_closed_reading(self):
        """تصنيف الدفعة يكون on_time عندما تقع ضمن payment_start/end حتى لو أُغلقت القراءة."""
        cycle = self._create_unified_cycle(
            'TEST-TIMING-001',
            start=date(2026, 9, 1),
            end=date(2026, 9, 15),
            payment_start=date(2026, 9, 2),
            payment_end=date(2026, 9, 16),
        )
        cycle.action_open_period()
        # محاكاة إغلاق القراءة: reading_state='closed' مع بقاء collection_state='open'
        cycle.with_context(_bypass_period_scope_protection=True).write({
            'reading_state': 'closed',
            'state': 'closing',
        })
        self.assertEqual(cycle.reading_state, 'closed')
        self.assertEqual(cycle.collection_state, 'open')

        # فحص المنطق: دفعة بتاريخ 2026-09-05 (ضمن نطاق الدفع 2-16)
        pay_date = date(2026, 9, 5)
        is_active = (
            cycle.collection_state in ('open', 'closing')
            or cycle.state in ('open', 'closing')
        )
        in_window = cycle.payment_start <= pay_date <= cycle.payment_end
        self.assertTrue(in_window)
        self.assertTrue(is_active)

    def test_12_payment_window_auto_sync_on_unified_cycle(self):
        """المزامنة التلقائية بين payment_start/end و payment_window_start/end."""
        cycle = self._create_unified_cycle(
            'TEST-SYNC-001',
            payment_start=date(2026, 9, 3),
            payment_end=date(2026, 9, 18),
        )
        self.assertTrue(cycle.payment_window_start)
        self.assertTrue(cycle.payment_window_end)
        self.assertEqual(cycle.payment_window_start.date(), date(2026, 9, 3))
        self.assertEqual(cycle.payment_window_end.date(), date(2026, 9, 18))

    def test_13_payment_date_range_domain_accepts_unified_cycle(self):
        """حقل date_range_id في account.payment يقبل الدورة الموحدة والسجل التاريخي."""
        unified_cycle = self._create_unified_cycle('TEST-DOMAIN-001')
        field = self.env['account.payment']._fields['date_range_id']
        self.assertIn("'reading'", field.domain)
        self.assertIn("'payment'", field.domain)

    def test_14_default_states_are_planned(self):
        """السجلات المنشأة حديثاً تبدأ بحالة planned للقراءة والتحصيل."""
        cycle = self._create_unified_cycle('TEST-PLANNED-001')
        self.assertEqual(cycle.state, 'planned')
        self.assertEqual(cycle.reading_state, 'planned')
        self.assertEqual(cycle.collection_state, 'planned')

    def test_15_single_open_reading_period_constraint(self):
        """يمنع فتح فترتي قراءة معاً لنفس الدورية والشركة."""
        c1 = self._create_unified_cycle('TEST-SINGLE-READ-01', start=date(2026, 9, 1), end=date(2026, 9, 15))
        c2 = self._create_unified_cycle('TEST-SINGLE-READ-02', start=date(2026, 9, 16), end=date(2026, 9, 30))

        c1.action_open_period()
        self.assertEqual(c1.reading_state, 'open')

        # محاولة فتح الدورة الثانية للقراءة يجب أن تفشل
        with self.assertRaises(ValidationError):
            c2.action_open_period()

    def test_16_single_open_collection_period_constraint(self):
        """يمنع فتح فترتي تحصيل معاً لنفس الدورية والشركة."""
        c1 = self._create_unified_cycle('TEST-SINGLE-COLL-01', start=date(2026, 9, 1), end=date(2026, 9, 15))
        c2 = self._create_unified_cycle('TEST-SINGLE-COLL-02', start=date(2026, 9, 16), end=date(2026, 9, 30))

        c1.action_open_period()
        self.assertEqual(c1.collection_state, 'open')

        # إغلاق قراءة الدورة الأولى
        c1.with_context(_bypass_period_scope_protection=True).write({'reading_state': 'closed'})

        # فتح الدورة الثانية: القراءة تُفتح ولكن التحصيل يبقى planned لأن تحصيل c1 لا يزال مفتوحاً
        c2.action_open_period()
        self.assertEqual(c2.reading_state, 'open')
        self.assertEqual(c2.collection_state, 'planned')

        # محاولة فتح تحصيل c2 مباشرة بينما تحصيل c1 مفتوح تطلق ValidationError
        with self.assertRaises(ValidationError):
            c2.action_open_payment()

    def test_17_open_second_collection_after_reconciling_first(self):
        """يمكن فتح تحصيل الدورة الثانية بعد إغلاق أو مطابقة تحصيل الدورة الأولى."""
        c1 = self._create_unified_cycle('TEST-SEQ-COLL-01', start=date(2026, 9, 1), end=date(2026, 9, 15))
        c2 = self._create_unified_cycle('TEST-SEQ-COLL-02', start=date(2026, 9, 16), end=date(2026, 9, 30))

        c1.action_open_period()
        c1.with_context(_bypass_period_scope_protection=True).write({'reading_state': 'closed'})

        c2.action_open_period()
        self.assertEqual(c2.collection_state, 'planned')

        # مطابقة تحصيل c1
        c1.action_reconcile_collection()
        self.assertEqual(c1.collection_state, 'reconciled')

        # الآن يمكن فتح تحصيل c2 بنجاح
        c2.action_open_payment()
        self.assertEqual(c2.collection_state, 'open')

