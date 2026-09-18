# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from odoo import fields


@tagged('post_install', '-at_install', 'utility_release', 'utility_billing')
class TestBillingProgressiveAndReplacementBusinessLogic(TransactionCase):
    """
    اختبارات منطق الأعمال المتقدمة لدورة الفوترة والتسعير وقراءات العدادات:
    - سيناريو استبدال العداد في نفس الدورة وفاتورة موحدة بشرائح تصاعدية
    - حالات الحافة والحدود لاحتساب الشرائح (Boundary Conditions & Zero Consumption)
    - تطبيق معامل ضرب العداد (Meter Multiplier)
    - عدم تكرار إصدار الفواتير (Idempotency)
    - الفصل الصارم بين القراءات الفنية للشبكة والقراءات التجارية المفوترة
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # تصنيف ومشترك
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة الأعمال التجارية لاختبار الفوترة',
            'code': 'CAT-BIZ-TEST',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'مشترك تجاري للاختبار',
            'code': 'SUB-BIZ-TEST',
            'category_id': cls.category.id,
        })

        # قالب عقد بشرائح تصاعدية (Progressive Blocks)
        # Block 1: 0 - 100 kWh @ 10.0 YER
        # Block 2: 100 - 300 kWh @ 20.0 YER
        # Block 3: 300+ kWh @ 30.0 YER
        cls.template_progressive = cls.env['utility.contract.template'].create({
            'name': 'تعرفة تصاعدية تجارية 3 شرائح',
            'code': 'TPL-PROG-3B',
            'pricing_mode': 'block',
            'service_charge': 500.0,
            'local_fee_cleaning': 200.0,
            'subscriber_category_ids': [(6, 0, cls.category.ids)],
            'subscriber_ids': [(6, 0, cls.subscriber.ids)],
            'scope': 'global',
        })
        cls.env['utility.contract.template.block'].create([
            {'template_id': cls.template_progressive.id, 'sequence': 10, 'name': 'الشريحة الأولى', 'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 10.0},
            {'template_id': cls.template_progressive.id, 'sequence': 20, 'name': 'الشريحة الثانية', 'from_kwh': 100, 'to_kwh': 300, 'price_per_kwh': 20.0},
            {'template_id': cls.template_progressive.id, 'sequence': 30, 'name': 'الشريحة الثالثة', 'from_kwh': 300, 'to_kwh': 0, 'price_per_kwh': 30.0},
        ])

        # شريك وحساب مشترك
        cls.partner = cls.env['res.partner'].create({
            'name': 'العميل التجاري لاختبار منطق الأعمال',
        })
        cls.customer = cls.env['utility.customer'].create({
            'customer_number': 'CUST-BIZ-LOGIC-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
            'contract_template_id': cls.template_progressive.id,
        })

        # دورة شهرية
        range_type = cls.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'دورة شهرية للتجارب',
                'work_type': 'readings',
            })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار الفوترة 2026-09',
            'type_id': range_type.id,
            'date_start': '2026-09-01',
            'date_end': '2026-09-30',
            'state': 'open',
            'period_role': 'reading',
            'company_id': cls.company.id,
        })

    def test_01_multi_meter_replacement_single_bill_progressive_tariffs(self):
        """
        سيناريو استبدال العداد في نفس الدورة:
        - العداد M1 يسجل قراءة إغلاقية (استهلاك 120 kWh).
        - العداد M2 يسجل قراءة دورية (استهلاك 280 kWh).
        - إجمالي استهلاك الحساب للفترة = 400 kWh.
        - التحقق من إصدار فاتورة موحدة واحدة فقط (sale.order) واحتساب الشرائح التصاعدية:
          * الشريحة 1 (100 kWh @ 10) = 1,000
          * الشريحة 2 (200 kWh @ 20) = 4,000
          * الشريحة 3 (100 kWh @ 30) = 3,000
          * إجمالي الطاقة = 8,000
        - التحقق من وجود مكوني قراءة (components) منفصلين في الفاتورة.
        - التحقق من توليد وترحيل فاتورة الحسابات (account.move).
        """
        # عداد قديم M1
        meter_old = self.env['utility.meter'].create({
            'meter_number': 'MTR-OLD-901',
            'customer_id': self.customer.id,
            'multiplier': 1.0,
            'state': 'replaced',
        })
        # عداد جديد M2
        meter_new = self.env['utility.meter'].create({
            'meter_number': 'MTR-NEW-902',
            'customer_id': self.customer.id,
            'multiplier': 1.0,
            'state': 'active',
        })

        # قراءة إغلاقية للعداد القديم M1 (استهلاك 120)
        reading_closing = self.env['utility.reading'].create({
            'account_id': self.customer.id,
            'customer_id': self.customer.id,
            'meter_id': meter_old.id,
            'reading_purpose': 'replacement_closing',
            'date_range_id': self.period.id,
            'previous_reading': 1000.0,
            'reading_value': 1120.0,
            'consumption': 120.0,
            'image_state': 'clear',
            'is_billable': True,
            'reading_category': 'customer',
            'reading_date': fields.Datetime.now(),
        })
        reading_closing.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'approved'
        })

        # قراءة دورية للعداد الجديد M2 (استهلاك 280)
        reading_periodic = self.env['utility.reading'].create({
            'account_id': self.customer.id,
            'customer_id': self.customer.id,
            'meter_id': meter_new.id,
            'reading_purpose': 'periodic',
            'date_range_id': self.period.id,
            'previous_reading': 0.0,
            'reading_value': 280.0,
            'consumption': 280.0,
            'image_state': 'clear',
            'is_billable': True,
            'reading_category': 'customer',
            'reading_date': fields.Datetime.now(),
        })
        reading_periodic.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'approved'
        })

        # إصدار الفاتورة من القراءة الدورية (Anchor)
        res = reading_periodic.action_generate_bill()
        order_id = res['res_id']
        order = self.env['sale.order'].browse(order_id)

        # 1. التحقق من ربط الفاتورة
        self.assertTrue(order.exists())
        self.assertEqual(order.reading_id.id, reading_periodic.id)
        self.assertEqual(order.state, 'sale')

        # 2. التحقق من إجمالي الاستهلاك المجمّع
        self.assertEqual(order.consumption, 400.0)

        # 3. التحقق من احتساب الطاقة حسب الشرائح التصاعدية الثلاث:
        # 100*10 + 200*20 + 100*30 = 1000 + 4000 + 3000 = 8000
        self.assertEqual(order.amount_energy, 8000.0)

        # 4. التحقق من مكونات القراءة (Reading Components): يجب أن تكون 2
        components = self.env['utility.bill.reading.component'].search([('sale_order_id', '=', order.id)])
        self.assertEqual(len(components), 2)
        comp_old = components.filtered(lambda c: c.meter_id == meter_old)
        comp_new = components.filtered(lambda c: c.meter_id == meter_new)
        self.assertTrue(comp_old)
        self.assertTrue(comp_new)
        self.assertEqual(comp_old.consumption, 120.0)
        self.assertEqual(comp_old.reading_purpose, 'replacement_closing')
        self.assertEqual(comp_new.consumption, 280.0)
        self.assertEqual(comp_new.reading_purpose, 'periodic')

        # 5. التحقق من حالة القراءة الإغلاقية: تم ربطها وتحديث حالتها إلى billed
        self.assertEqual(reading_closing.state, 'billed')
        self.assertEqual(reading_closing.billing_anchor_id.id, reading_periodic.id)
        self.assertEqual(reading_closing.included_sale_order_id.id, order.id)

        # 6. التحقق من لقطة التسعير الثابتة (Pricing Snapshot)
        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(snapshot.amount_energy, 8000.0)
        self.assertEqual(len(snapshot.block_ids), 3)

        # 7. التحقق من ترحيل فاتورة الحسابات account.move
        self.assertEqual(len(order.invoice_ids), 1)
        self.assertEqual(order.invoice_ids[0].state, 'posted')

    def test_02_zero_consumption_charges_and_no_zero_division(self):
        """
        التحقق من صحة احتساب الرسوم عند استهلاك صفري (0 kWh):
        - amount_energy = 0
        - رسوم الخدمة ورسوم النظافة تطبق بدقة
        - لا توجد أي أخطاء قسمة على صفر أو فشل في بناء لقطة التسعير
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 0.0,
            'contract_template_id': self.template_progressive.id,
        })
        order._calculate_amounts()

        self.assertEqual(order.amount_energy, 0.0)
        self.assertEqual(order.amount_service, 500.0)
        self.assertEqual(order.amount_local_fee, 200.0)
        self.assertEqual(order.amount_total, 700.0)

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(snapshot.billing_consumption, 0.0)
        self.assertEqual(snapshot.amount_energy, 0.0)
        self.assertEqual(snapshot.service_charge, 500.0)
        self.assertEqual(snapshot.local_fee_cleaning, 200.0)

    def test_03_exact_boundary_block_pricing(self):
        """
        التحقق الدقيق من حدود الشرائح (Boundary Conditions):
        - الشريحة 1 من 0 إلى 100 @ 10.0
        - الشريحة 2 من 100 إلى 300 @ 20.0
        حالة أ: استهلاك 100 kWh بالضبط -> يقع 100% في الشريحة 1 (المبلغ = 1,000)
        حالة ب: استهلاك 101 kWh -> (100 * 10) + (1 * 20) = 1,020
        """
        # حالة أ: 100 kWh بالضبط
        order_100 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 100.0,
            'contract_template_id': self.template_progressive.id,
        })
        order_100._calculate_amounts()
        self.assertEqual(order_100.amount_energy, 1000.0)
        snapshot_100 = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order_100.id)], limit=1)
        self.assertEqual(len(snapshot_100.block_ids), 1)
        self.assertEqual(snapshot_100.block_ids[0].quantity, 100.0)

        # حالة ب: 101 kWh
        order_101 = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 101.0,
            'contract_template_id': self.template_progressive.id,
        })
        order_101._calculate_amounts()
        self.assertEqual(order_101.amount_energy, 1020.0)
        snapshot_101 = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order_101.id)], limit=1)
        self.assertEqual(len(snapshot_101.block_ids), 2)
        b1 = snapshot_101.block_ids.filtered(lambda b: b.block_name == 'الشريحة الأولى')
        b2 = snapshot_101.block_ids.filtered(lambda b: b.block_name == 'الشريحة الثانية')
        self.assertEqual(b1.quantity, 100.0)
        self.assertEqual(b2.quantity, 1.0)

    def test_04_meter_multiplier_progressive_billing(self):
        """
        التحقق من تطبيق معامل ضرب العداد (Multiplier = 5):
        - قراءة سابقة = 10, قراءة حالية = 30 -> الفرق = 20.
        - الاستهلاك الفعلي = 20 * 5 = 100 kWh.
        - احتساب الطاقة والشرائح ومكون القراءة بناءً على الاستهلاك الفعلي 100 kWh.
        """
        meter_x5 = self.env['utility.meter'].create({
            'meter_number': 'MTR-X5-001',
            'customer_id': self.customer.id,
            'multiplier': 5.0,
            'state': 'active',
        })

        reading = self.env['utility.reading'].create({
            'account_id': self.customer.id,
            'customer_id': self.customer.id,
            'meter_id': meter_x5.id,
            'reading_purpose': 'periodic',
            'date_range_id': self.period.id,
            'previous_reading': 10.0,
            'reading_value': 30.0,
            'image_state': 'clear',
            'is_billable': True,
            'reading_category': 'customer',
            'reading_date': fields.Datetime.now(),
        })

        # الاستهلاك المحسوب تلقائياً في القراءة يجب أن يكون 100
        self.assertEqual(reading.consumption, 100.0)

        reading.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'approved'
        })
        res = reading.action_generate_bill()
        order = self.env['sale.order'].browse(res['res_id'])

        self.assertEqual(order.consumption, 100.0)
        self.assertEqual(order.amount_energy, 1000.0)

        component = self.env['utility.bill.reading.component'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertEqual(component.meter_multiplier, 5.0)
        self.assertEqual(component.consumption, 100.0)

    def test_05_idempotent_bill_generation_and_double_approval_prevention(self):
        """
        التحقق من عدم تكرار الفواتير عند إعادة استدعاء action_generate_bill:
        - عند استدعائه لقراءة مفوترة، يعيد نافذة الفاتورة القائمة دون إنشاء سجل جديد.
        """
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-IDEMP-001',
            'customer_id': self.customer.id,
            'multiplier': 1.0,
        })
        reading = self.env['utility.reading'].create({
            'account_id': self.customer.id,
            'customer_id': self.customer.id,
            'meter_id': meter.id,
            'reading_purpose': 'periodic',
            'date_range_id': self.period.id,
            'previous_reading': 0.0,
            'reading_value': 50.0,
            'consumption': 50.0,
            'image_state': 'clear',
            'is_billable': True,
            'reading_category': 'customer',
            'reading_date': fields.Datetime.now(),
        })
        reading.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'approved'
        })

        # أول استدعاء
        res1 = reading.action_generate_bill()
        order1 = self.env['sale.order'].browse(res1['res_id'])
        self.assertEqual(reading.state, 'billed')

        # ثاني استدعاء: يجب أن يعيد نفس الفاتورة دون إنشاء فاتورة مكررة
        res2 = reading.action_generate_bill()
        self.assertEqual(res2['res_id'], order1.id)

        all_orders = self.env['sale.order'].search([('reading_id', '=', reading.id)])
        self.assertEqual(len(all_orders), 1)

    def test_06_network_reading_technical_approval_zero_financial_impact(self):
        """
        التحقق من أن قراءات الشبكة (محول عام غير خاص):
        - تكون is_billable = False.
        - عند اعتمادها تنتقل إلى approved وتبقى كقراءة فنية.
        - لا تنتقل إلى queued أو billed ولا تولد أي sale.order أو أثر مالي.
        """
        region = self.env['utility.region'].create({
            'name': 'منطقة شبكة تجريبية',
            'code': 'NET-REG-01',
            'type': 'region',
        })
        substation = self.env['utility.substation'].create({
            'name': 'محطة تحويل تجريبية',
            'code': 'SUB-01',
            'region_id': region.id,
        })
        feeder = self.env['utility.feeder'].create({
            'name': 'مغذي تجريبي',
            'code': 'FDR-01',
            'substation_id': substation.id,
        })
        transformer = self.env['utility.transformer'].create({
            'name': 'محول شبكة عام للاختبار',
            'code': 'TRF-PUB-01',
            'feeder_id': feeder.id,
            'is_private': False,
        })

        reading_net = self.env['utility.reading'].create({
            'reading_category': 'transformer',
            'transformer_id': transformer.id,
            'reading_purpose': 'periodic',
            'date_range_id': self.period.id,
            'previous_reading': 10000.0,
            'reading_value': 15000.0,
            'consumption': 5000.0,
            'image_state': 'clear',
            'reading_date': fields.Datetime.now(),
        })

        # القراءة الفنية ليست قابلة للفوترة
        self.assertFalse(reading_net.is_billable)

        # الاعتماد الفني
        reading_net.action_approve()
        self.assertEqual(reading_net.state, 'approved')
        self.assertFalse(reading_net.included_sale_order_id)

        # محاولة إنشاء فاتورة يجب أن ترفض بقيد التحقق
        with self.assertRaises(ValidationError):
            reading_net.action_generate_bill()
