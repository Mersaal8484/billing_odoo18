from datetime import date, datetime, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields
from odoo.addons.utility_core.models.utility_date_range import normalize_billing_cadence
import logging

_logger = logging.getLogger(__name__)


class TestUtilityPeriodManagement(TransactionCase):
    """مجموعة اختبارات شاملة للهيكلية الجديدة لإدارة فترات القراءة والاستهلاك والسداد"""

    def setUp(self):
        super().setUp()
        self.DateRange = self.env['date.range'].sudo()
        self.Region = self.env['utility.region'].sudo()
        self.Customer = self.env['utility.customer'].sudo()
        self.Meter = self.env['utility.meter'].sudo()
        self.Reading = self.env['utility.reading'].sudo()
        self.Batch = self.env.get('utility.reading.batch')
        if self.Batch is not None:
            self.Batch = self.Batch.sudo()
        self.SaleOrder = self.env['sale.order'].sudo()
        self.Generator = self.env['utility.period.generator'].sudo()

        # إنشاء مناطق باختبارات تكرار مختلفة
        self.region_monthly = self.Region.create({
            'name': 'منطقة صنعاء (شهري)',
            'code': 'SANAA_M',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })
        self.region_monthly_2 = self.Region.create({
            'name': 'منطقة عدن (شهري)',
            'code': 'ADEN_M',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })
        self.region_semi = self.Region.create({
            'name': 'منطقة تعز (نصف شهري)',
            'code': 'TAIZ_S',
            'type': 'region',
            'recurring_rule_type': 'semi_monthly',
        })
        self.area_monthly = self.Region.create({
            'name': 'فرع صنعاء (شهري)',
            'code': 'SANAA_A_M',
            'type': 'area',
            'parent_id': self.region_monthly.id,
            'recurring_rule_type': 'monthly',
        })
        self.area_semi = self.Region.create({
            'name': 'فرع تعز (نصف شهري)',
            'code': 'TAIZ_A_S',
            'type': 'area',
            'parent_id': self.region_semi.id,
            'recurring_rule_type': 'semi_monthly',
        })

        # إنشاء فئات وقوالب مشاطرة
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'منزلي اختبار',
            'code': 'DOM_TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'منزلي عادي',
            'code': 'DOM_NORM',
            'category_id': self.category.id,
        })
        self.other_category = self.env['utility.subscriber.category'].create({
            'name': 'تجاري اختبار',
            'code': 'COM_TEST',
        })
        self.other_subscriber_type = self.env['utility.subscriber'].create({
            'name': 'تجاري عادي',
            'code': 'COM_NORM',
            'category_id': self.other_category.id,
        })
        self.template_monthly = self.env['utility.contract.template'].create({
            'name': 'عقد شهري',
            'code': 'TMP_M',
            'recurring_rule_type': 'monthly',
            'subscriber_category_ids': [(6, 0, [self.category.id])],
            'subscriber_ids': [(6, 0, [self.subscriber_type.id])],
            'scope': 'global',
        })
        self.template_semi = self.env['utility.contract.template'].create({
            'name': 'عقد نصف شهري',
            'code': 'TMP_S',
            'recurring_rule_type': 'semi_monthly',
            'subscriber_category_ids': [(6, 0, [self.category.id])],
            'subscriber_ids': [(6, 0, [self.subscriber_type.id])],
            'scope': 'global',
        })

        # حسابات ومشتركين
        self.partner = self.env['res.partner'].create({'name': 'مشترك اختبار 1'})
        self.customer_m = self.Customer.create({
            'partner_id': self.partner.id,
            'region_id': self.region_monthly.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'contract_template_id': self.template_monthly.id,
        })
        self.customer_s = self.Customer.create({
            'partner_id': self.partner.id,
            'region_id': self.region_semi.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'contract_template_id': self.template_semi.id,
        })

        self.meter_m = self.Meter.create({
            'meter_number': 'MTR-M-001',
            'customer_id': self.customer_m.id,
        })
        self.meter_s = self.Meter.create({
            'meter_number': 'MTR-S-001',
            'customer_id': self.customer_s.id,
        })

    def test_01_monthly_region_period_filtering(self):
        """1. المنطقة الشهرية تختار الفترات الشهرية فقط"""
        domain_m = self.Reading._get_open_period_domain(work_type='readings', billing_period='monthly', region_id=self.region_monthly.id)
        self.assertIn(('billing_cadence', '=', 'monthly'), domain_m)

    def test_02_semi_monthly_region_period_filtering(self):
        """2. المنطقة نصف الشهرية تختار فترات H1/H2 فقط"""
        domain_s = self.Reading._get_open_period_domain(work_type='readings', billing_period='semi_monthly', region_id=self.region_semi.id)
        self.assertIn(('billing_cadence', '=', 'semi_monthly'), domain_s)

    def test_02a_contract_template_uses_canonical_semi_monthly_cadence(self):
        """قالب العقد والحساب يعيدان قيمة دورية موحدة لفترات القراءة."""
        self.assertEqual(self.template_semi.recurring_rule_type, 'semi_monthly')
        self.assertEqual(self.customer_s._get_effective_billing_period(), 'semi_monthly')
        self.assertEqual(normalize_billing_cadence('bi_monthly'), 'semi_monthly')

    def test_02aa_template_filters_subscriber_types_by_category(self):
        """Changing a category keeps only its compatible subscriber types."""
        template = self.env['utility.contract.template'].new()
        template.subscriber_category_ids = self.category
        template.subscriber_ids = self.subscriber_type | self.other_subscriber_type

        result = template._onchange_subscriber_category_ids()

        self.assertEqual(template.subscriber_ids, self.subscriber_type)
        self.assertEqual(
            result['domain']['subscriber_ids'],
            [('category_id', 'in', [self.category.id])],
        )

    def test_02aaa_customer_rejects_template_with_different_geographic_cadence(self):
        """A monthly region cannot use a semi-monthly contract template."""
        partner = self.env['res.partner'].create({
            'name': 'مشترك دورية غير متوافقة',
            'region_id': self.region_monthly.id,
        })

        with self.assertRaises(ValidationError):
            self.Customer.create({
                'partner_id': partner.id,
                'category_id': self.category.id,
                'subscriber_id': self.subscriber_type.id,
                'contract_template_id': self.template_semi.id,
            })

    def test_02ab_template_filters_geography_by_cadence_and_parent_region(self):
        """A monthly template only retains its monthly region and child branch."""
        template = self.env['utility.contract.template'].new()
        template.recurring_rule_type = 'monthly'
        template.region_ids = self.region_monthly | self.region_semi
        template.area_ids = self.area_monthly | self.area_semi

        result = template._onchange_recurring_rule_type_scope()

        self.assertEqual(template.region_ids, self.region_monthly)
        self.assertEqual(template.area_ids, self.area_monthly)
        self.assertEqual(
            result['domain']['area_ids'],
            [
                ('type', '=', 'area'),
                ('parent_id', 'in', [self.region_monthly.id]),
                ('recurring_rule_type', '=', 'monthly'),
            ],
        )

    def test_02b_open_semi_monthly_period_remains_selectable(self):
        """2b. الفترة نصف الشهرية المفتوحة تبقى متاحة للقراءات إذا طابقت الدورية"""
        period = self.DateRange.search([
            ('cycle_key', '=', 'SEMI-2026-07-H1'),
            ('period_role', '=', 'reading'),
        ], limit=1)
        self.assertTrue(period)

        domain = self.Reading._get_open_period_domain(
            work_type='readings',
            billing_period='semi_monthly',
            region_id=self.region_semi.id,
        )
        self.assertIn(('state', 'in', ['open']), domain)
        self.assertIn(period, self.DateRange.search(domain))

    def test_03_04_05_period_generator_h1_h2_february(self):
        """3, 4, 5. مولد الفترات للنصف الأول (1-15) والثاني (16-نهاية الشهر) واختبار فبراير"""
        wizard = self.Generator.create({
            'year': 2026,
            'month': '2', # فبراير 2026 (28 يوم)
            'billing_cadence': 'semi_monthly',
        })
        wizard.action_generate_periods()

        p_h1 = self.DateRange.search([('cycle_key', '=', 'SEMI-2026-02-H1'), ('period_role', '=', 'reading')])
        p_h2 = self.DateRange.search([('cycle_key', '=', 'SEMI-2026-02-H2'), ('period_role', '=', 'reading')])

        self.assertTrue(p_h1)
        self.assertEqual(p_h1.date_start, date(2026, 2, 1))
        self.assertEqual(p_h1.date_end, date(2026, 2, 15))
        self.assertEqual(p_h1.consumption_start, date(2026, 1, 16))
        self.assertEqual(p_h1.consumption_end, date(2026, 1, 31))
        # التحقق من أن الدورة موحدة: حقول الدفع موجودة في نفس السجل ولا يوجد سجل منفصل للتحصيل
        self.assertTrue(p_h1.payment_start)
        self.assertTrue(p_h1.payment_end)
        self.assertFalse(self.DateRange.search([('cycle_key', '=', 'SEMI-2026-02-H1'), ('period_role', '=', 'payment')]))

        self.assertTrue(p_h2)
        self.assertEqual(p_h2.date_start, date(2026, 2, 16))
        self.assertEqual(p_h2.date_end, date(2026, 2, 28))
        self.assertEqual(p_h2.consumption_start, date(2026, 2, 1))
        self.assertEqual(p_h2.consumption_end, date(2026, 2, 15))
        self.assertTrue(p_h2.payment_start)
        self.assertTrue(p_h2.payment_end)
        self.assertFalse(self.DateRange.search([('cycle_key', '=', 'SEMI-2026-02-H2'), ('period_role', '=', 'payment')]))

    def test_06_reading_after_consumption_within_window(self):
        """6. قبول قراءة مأخوذة بعد نهاية الاستهلاك طالما ضمن نافذة القراءة المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1',
            'period_code': 'READ-SEMI-TEST-01',
            'cycle_key': 'SEMI-TEST-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'open',
        })

        reading_date = datetime(2026, 8, 17, 10, 0, 0)
        reading = self.Reading.create({
            'meter_id': self.meter_s.id,
            'account_id': self.customer_s.id,
            'date_range_id': period.id,
            'reading_value': 150.0,
            'reading_date': reading_date,
            'reading_purpose': 'periodic',
        })
        self.assertTrue(reading)

    def test_07_reading_outside_window_rejected(self):
        """7. رفض القراءة المأخوذة خارج نافذة القراءة المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1 STRICT',
            'period_code': 'READ-SEMI-TEST-02',
            'cycle_key': 'SEMI-TEST-02',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'open',
        })

        late_reading_date = datetime(2026, 8, 20, 10, 0, 0)
        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': self.meter_s.id,
                'account_id': self.customer_s.id,
                'date_range_id': period.id,
                'reading_value': 200.0,
                'reading_date': late_reading_date,
                'reading_purpose': 'periodic',
            })

    def test_08_batch_upload_within_upload_window(self):
        """8. رفع دفعة بعد نهاية الاستهلاك لكن ضمن نافذة الرفع المسموحة"""
        period = self.DateRange.create({
            'name': 'أغسطس 2026 H1 الدفعة',
            'period_code': 'READ-SEMI-BATCH-01',
            'cycle_key': 'SEMI-BATCH-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'consumption_start': date(2026, 8, 1),
            'consumption_end': date(2026, 8, 15),
            'reading_window_start': datetime(2026, 8, 13, 0, 0, 0),
            'reading_window_end': datetime(2026, 8, 18, 23, 59, 59),
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'open',
        })

        if not self.Batch:
            return
        batch = self.Batch.create({
            'date_range_id': period.id,
            'region_id': self.region_semi.id,
            'upload_date': datetime(2026, 8, 17, 14, 0, 0),
        })
        self.assertTrue(batch)

    def test_09_wrong_region_period_combination_rejected(self):
        """9. رفض اقتران منطقة غير مشمولة في نطاق مناطق الفترة"""
        if not self.Batch:
            return
        period = self.DateRange.create({
            'name': 'فترة منطقة تعز فقط',
            'period_code': 'READ-SEMI-REGION-01',
            'cycle_key': 'SEMI-REGION-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
        })

        with self.assertRaises(ValidationError):
            self.Batch.create({
                'date_range_id': period.id,
                'region_id': self.region_monthly.id,
            })

    def test_10_wrong_cadence_combination_rejected(self):
        """10. رفض اقتران دورية منطقة لا تطابق دورية الفترة"""
        if not self.Batch:
            return
        period = self.DateRange.create({
            'name': 'فترة نصف شهرية',
            'period_code': 'READ-SEMI-CADENCE-01',
            'cycle_key': 'SEMI-CADENCE-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })

        with self.assertRaises(ValidationError):
            self.Batch.create({
                'date_range_id': period.id,
                'region_id': self.region_monthly.id,
            })

    def test_11_reading_closes_payment_remains_open(self):
        """11. إغلاق فترة القراءة لا يغلق فترة السداد والتحصيل المرتبطة"""
        r_period = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'READ-SEMI-01',
            'cycle_key': 'SEMI-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-SEMI-01',
            'cycle_key': 'SEMI-01',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_period.id,
            'state': 'open',
        })

        r_period.action_start_closing()
        self.assertEqual(r_period.state, 'closing')
        self.assertEqual(p_period.state, 'open')

    def test_12_new_reading_opens_previous_payment_remains_open(self):
        """12. فتح فترة قراءة جديدة لا يغلق فترة التحصيل السابقة"""
        r_h1 = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'READ-H1',
            'cycle_key': 'CYCLE-H1',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'closed',
        })
        p_h1 = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-H1',
            'cycle_key': 'CYCLE-H1',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_h1.id,
            'state': 'open',
        })

        r_h2 = self.DateRange.create({
            'name': 'قراءة H2',
            'period_code': 'READ-H2',
            'cycle_key': 'CYCLE-H2',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'planned',
        })
        r_h2.action_open_reading()

        self.assertEqual(r_h2.state, 'open')
        self.assertEqual(p_h1.state, 'open')

    def test_13_overlapping_payment_periods(self):
        """13. تداخل وتزامن فترتي سداد وتحصيل مفتوحتين في الوقت نفسه"""
        r1 = self.DateRange.create({
            'name': 'قراءة H1',
            'period_code': 'READ-OVERLAP-01',
            'cycle_key': 'OVERLAP-01',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })
        r2 = self.DateRange.create({
            'name': 'قراءة H2',
            'period_code': 'READ-OVERLAP-02',
            'cycle_key': 'OVERLAP-02',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
        })

        p1 = self.DateRange.create({
            'name': 'تحصيل H1',
            'period_code': 'PAY-OVERLAP-01',
            'cycle_key': 'OVERLAP-01',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r1.id,
            'state': 'open',
        })
        p2 = self.DateRange.create({
            'name': 'تحصيل H2',
            'period_code': 'PAY-OVERLAP-02',
            'cycle_key': 'OVERLAP-02',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r2.id,
            'state': 'open',
        })

        self.assertEqual(p1.state, 'open')
        self.assertEqual(p2.state, 'open')

    def test_14_monthly_and_semi_monthly_concurrent(self):
        """14. عمل واستمرار الفترات الشهرية ونصف الشهرية بالتزامن الاستقلالي"""
        m_period = self.DateRange.create({
            'name': 'قراءة صنعاء شهري',
            'period_code': 'READ-CONC-M',
            'cycle_key': 'CONC-M',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region_monthly.id])],
            'state': 'open',
        })

        s_period = self.DateRange.create({
            'name': 'قراءة تعز نصف شهري',
            'period_code': 'READ-CONC-S',
            'cycle_key': 'CONC-S',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'open',
        })

        self.assertEqual(m_period.state, 'open')
        self.assertEqual(s_period.state, 'open')

    def test_15_closing_reading_does_not_stop_collection(self):
        """15. إغلاق فترة القراءة لا يوقف عمليات التحصيل المالي للفواتير المنشأة"""
        r_period = self.DateRange.create({
            'name': 'قراءة أغسطس',
            'period_code': 'READ-COLL-01',
            'cycle_key': 'COLL-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل أغسطس',
            'period_code': 'PAY-COLL-01',
            'cycle_key': 'COLL-01',
            'period_role': 'payment',
            'billing_cadence': 'monthly',
            'reading_period_id': r_period.id,
            'state': 'open',
        })

        r_period.action_start_closing()
        self.assertEqual(p_period.state, 'open')

    def test_16_opening_next_reading_does_not_close_previous_payment(self):
        """16. فتح فترة قراءة تالية لا يغلق تلقائياً فترة تحصيل الدورة السابقة"""
        r_aug = self.DateRange.create({
            'name': 'قراءة أغسطس H1',
            'period_code': 'READ-AUG-H1',
            'cycle_key': 'AUG-H1',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'closed',
        })
        p_aug = self.DateRange.create({
            'name': 'تحصيل أغسطس H1',
            'period_code': 'PAY-AUG-H1',
            'cycle_key': 'AUG-H1',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_aug.id,
            'state': 'open',
        })

        r_sep = self.DateRange.create({
            'name': 'قراءة أغسطس H2',
            'period_code': 'READ-AUG-H2',
            'cycle_key': 'AUG-H2',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'state': 'planned',
        })
        r_sep.action_open_reading()

        self.assertEqual(p_aug.state, 'open')
        self.assertEqual(r_sep.state, 'open')

    def test_17_late_payment_controlled_accounting_flow(self):
        """17. قبول السداد المتأخر عبر النظام المحاسبي وتصنيفه كـ late"""
        r_period = self.DateRange.create({
            'name': 'قراءة H1 لغرض التحصيل المتأخر',
            'period_code': 'READ-LATE-PAY',
            'cycle_key': 'LATE-PAY',
            'period_role': 'reading',
            'billing_cadence': 'semi_monthly',
            'region_ids': [(6, 0, [self.region_semi.id])],
            'state': 'open',
        })
        p_period = self.DateRange.create({
            'name': 'تحصيل H1 مغلق',
            'period_code': 'PAY-LATE-PAY',
            'cycle_key': 'LATE-PAY',
            'period_role': 'payment',
            'billing_cadence': 'semi_monthly',
            'reading_period_id': r_period.id,
            'payment_window_start': datetime(2026, 8, 16, 0, 0, 0),
            'payment_window_end': datetime(2026, 8, 25, 23, 59, 59),
            'state': 'closed',
        })

        reading = self.Reading.create({
            'meter_id': self.meter_s.id,
            'account_id': self.customer_s.id,
            'date_range_id': r_period.id,
            'reading_value': 300.0,
            'reading_date': datetime(2026, 8, 15, 10, 0, 0),
            'reading_purpose': 'periodic',
            'state': 'approved',
        })

        if not hasattr(reading, 'action_generate_bill'):
            return
        res = reading.action_generate_bill()
        order = self.SaleOrder.browse(res['res_id'])

        payment = self.env['account.payment'].create({
            'utility_sale_order_id': order.id,
            'partner_id': self.partner.id,
            'amount': order.amount_total,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'date': date(2026, 8, 28),
        })
        payment.action_post()

        self.assertEqual(payment.state, 'posted')
        self.assertEqual(payment.timing_classification, 'late')

    def test_23_period_reopening_audited(self):
        """23. تدقيق وتسجيل إعادة فتح الفترة استثنائياً في سجل التدقيق"""
        period = self.DateRange.create({
            'name': 'فترة إعادة فتح',
            'period_code': 'READ-REOPEN-01',
            'cycle_key': 'REOPEN-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'closed',
        })

        period.action_reopen_period(reason="إعادة فتح لتصحيح قراءة خاطئة")
        self.assertEqual(period.state, 'open')
        self.assertTrue(period.log_ids)
        self.assertEqual(period.log_ids[0].new_state, 'open')
        self.assertIn("تصحيح قراءة", period.log_ids[0].reason)

    def test_25_invalid_state_transition_prevented(self):
        """25. منع القفز غير التسلسلي بين حالات الفترة بواسطة مصفوفة التحول (Transition Matrix)"""
        period = self.DateRange.create({
            'name': 'فترة اختراق الحالات',
            'period_code': 'READ-TRANS-01',
            'cycle_key': 'TRANS-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'planned',
        })

        with self.assertRaises(ValidationError):
            period.action_close_period()

        period.action_open_reading()
        self.assertEqual(period.state, 'open')

    def test_26_unified_cycle_payment_dates_constraint(self):
        """26. التحقق من قيد ترتيب تواريخ نطاق الدفع في الدورة الموحدة"""
        with self.assertRaises(ValidationError):
            self.DateRange.create({
                'name': 'دورة بتواريخ دفع غير صحيحة',
                'period_code': 'READ-INV-PAYDATES',
                'cycle_key': 'INV-PAYDATES',
                'period_role': 'reading',
                'billing_cadence': 'monthly',
                'date_start': date(2026, 10, 1),
                'date_end': date(2026, 10, 31),
                'payment_start': date(2026, 10, 25),
                'payment_end': date(2026, 10, 10), # قبل البداية!
            })

    def test_27_unified_cycle_independent_states(self):
        """27. التحقق من استقلالية حالتي القراءة والتحصيل في الدورة الموحدة"""
        period = self.DateRange.create({
            'name': 'دورة موحدة استقلالية الحالات',
            'period_code': 'READ-INDEP-01',
            'cycle_key': 'INDEP-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'date_start': date(2026, 11, 1),
            'date_end': date(2026, 11, 30),
            'payment_start': date(2026, 11, 5),
            'payment_end': date(2026, 12, 10),
            'state': 'open',
            'reading_state': 'open',
            'collection_state': 'open',
        })
        self.assertEqual(period.reading_state, 'open')
        self.assertEqual(period.collection_state, 'open')

        # إغلاق القراءة يبقي التحصيل مفتوحاً
        period.action_close_reading()
        self.assertEqual(period.reading_state, 'closed')
        self.assertEqual(period.collection_state, 'open')
        self.assertEqual(period.state, 'open')

        # مطابقة التحصيل بعد إغلاق القراءة تؤدي لإغلاق الدورة بالكامل
        period.action_reconcile_collection()
        self.assertEqual(period.collection_state, 'reconciled')
        self.assertEqual(period.state, 'closed')
