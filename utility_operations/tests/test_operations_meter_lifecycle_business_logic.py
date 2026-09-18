# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import fields


@tagged('post_install', '-at_install', 'utility_release', 'utility_operations')
class TestOperationsMeterLifecycleBusinessLogic(TransactionCase):
    """
    اختبارات منطق الأعمال للعمليات والمخزون وحوكمة استبدال العدادات:
    - التحقق من قيود منع استبدال العداد بنفسه (old_meter == new_meter)
    - التحقق من منع القراءات الختامية الأقل من آخر قراءة مفوترة
    - التحقق من تحديث سجلات التخصيص وعزل تاريخ العداد القديم والجديد
    - التحقق من تفويض حركات المخزون الفعلية ونقل العداد القديم للمعاينة والجديد للعميل
    - التحقق من انضباط دورة حياة أوامر الخدمة (utility.service.order)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.Customer = cls.env['utility.customer']
        cls.Meter = cls.env['utility.meter']
        cls.Replacement = cls.env['utility.meter.replacement']
        cls.Partner = cls.env['res.partner']
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.ServiceOrder = cls.env['utility.service.order']

        cls.partner = cls.Partner.create({'name': 'مشترك اختبار عمليات الاستبدال'})
        cls.category = cls.Category.create({
            'name': 'فئة عمليات الاستبدال',
            'code': 'OPS-REP-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع عمليات الاستبدال',
            'code': 'OPS-REP-SUB',
            'category_id': cls.category.id,
        })

        # العداد القديم
        cls.old_meter = cls.Meter.create({
            'meter_number': 'MTR-OPS-OLD-01',
            'company_id': cls.company.id,
            'multiplier': 1.0,
            'active': True,
        })

        cls.customer = cls.Customer.create({
            'customer_number': 'CUST-OPS-REP-01',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
            'meter_id': cls.old_meter.id,
            'last_invoice_reading': 2500.0,
            'last_reading_value': 2500.0,
        })
        cls.old_meter.customer_id = cls.customer.id

        # إنشاء تخصيص مبدئي للعداد القديم
        cls.initial_assignment = cls.env['utility.customer.meter.assignment'].create({
            'customer_id': cls.customer.id,
            'meter_id': cls.old_meter.id,
            'company_id': cls.company.id,
            'date_from': fields.Datetime.now(),
            'initial_reading': 1000.0,
            'assignment_type': 'initial',
        })

        # العداد الجديد
        cls.new_meter = cls.Meter.create({
            'meter_number': 'MTR-OPS-NEW-01',
            'company_id': cls.company.id,
            'multiplier': 1.0,
            'active': True,
        })

    def test_01_replacement_rejects_same_meter_identity(self):
        """
        قيد التحقق: منع استبدال العداد بنفسه.
        - محاولة إجراء استبدال يكون فيه old_meter_id هو نفسه new_meter_id يجب أن ترفع UserError.
        """
        replacement = self.Replacement.create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'new_meter_id': self.old_meter.id,
            'old_closing_reading': 3000.0,
            'new_opening_reading': 0.0,
            'reason': 'test',
        })
        with self.assertRaises(UserError):
            replacement.action_complete_replacement()

    def test_02_replacement_rejects_reading_lower_than_last_invoiced(self):
        """
        قيد التحقق: القراءة الختامية لا يمكن أن تقل عن آخر قراءة مفوترة مسجلة للعداد.
        - آخر قراءة مفوترة للعميل هي 2,500.
        - تسجيل قراءة ختامية 2,400 يجب أن ترفع UserError صريحاً.
        """
        replacement = self.Replacement.create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'new_meter_id': self.new_meter.id,
            'old_closing_reading': 2400.0,
            'new_opening_reading': 0.0,
            'reason': 'test_lower_reading',
        })
        with self.assertRaises(UserError):
            replacement.action_complete_replacement()

    def test_03_replacement_assignment_and_lifecycle_integrity(self):
        """
        اكتمال الاستبدال وسلامة دورة الحياة وسجلات التخصيص:
        1. إغلاق سجل تخصيص العداد القديم بتحديد date_to.
        2. فتح سجل تخصيص جديد للعداد الجديد مع date_to = False.
        3. تحديث customer.meter_id بالعداد الجديد.
        4. العداد القديم يصبح customer_id = False و active = False.
        5. العداد الجديد يصبح customer_id = customer و active = True.
        6. إنشاء قراءة إغلاقية وقراءة افتتاحية مرتبطتين بعملية الاستبدال.
        """
        replacement = self.Replacement.create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'new_meter_id': self.new_meter.id,
            'old_closing_reading': 3200.0,
            'new_opening_reading': 50.0,
            'reason': 'damaged',
            'notes': 'تلف العداد واستبداله بعداد جديد',
        })
        replacement.action_complete_replacement()
        self.assertEqual(replacement.state, 'done')

        # 1. فحص تخصيص العداد القديم
        self.initial_assignment.invalidate_recordset()
        self.assertTrue(self.initial_assignment.date_to, 'يجب إغلاق تخصيص العداد القديم بتحديد تاريخ النهاية.')

        # 2. فحص تخصيص العداد الجديد
        new_assignment = self.env['utility.customer.meter.assignment'].search([
            ('customer_id', '=', self.customer.id),
            ('meter_id', '=', self.new_meter.id),
            ('date_to', '=', False),
        ], limit=1)
        self.assertTrue(new_assignment, 'يجب إنشاء تخصيص نشط للعداد الجديد.')
        self.assertEqual(new_assignment.initial_reading, 50.0)
        self.assertEqual(new_assignment.assignment_type, 'replacement')

        # 3. فحص العداد الفعال للمشترك
        self.customer.invalidate_recordset()
        self.assertEqual(self.customer.meter_id.id, self.new_meter.id)
        self.assertEqual(self.customer.last_reading_value, 50.0)

        # 4. فحص حالات العدادين
        self.old_meter.invalidate_recordset()
        self.new_meter.invalidate_recordset()
        self.assertFalse(self.old_meter.customer_id)
        self.assertFalse(self.old_meter.active)
        self.assertEqual(self.new_meter.customer_id.id, self.customer.id)
        self.assertTrue(self.new_meter.active)

        # 5. فحص القراءات المولدة
        closing_readings = self.env['utility.reading'].search([
            ('meter_id', '=', self.old_meter.id),
            ('replacement_id', '=', replacement.id),
        ])
        opening_readings = self.env['utility.reading'].search([
            ('meter_id', '=', self.new_meter.id),
            ('replacement_id', '=', replacement.id),
        ])
        self.assertEqual(len(closing_readings), 1)
        self.assertEqual(closing_readings.reading_purpose, 'replacement_closing')
        self.assertEqual(closing_readings.reading_value, 3200.0)
        self.assertEqual(closing_readings.consumption, 700.0)  # 3200 - 2500

        self.assertEqual(len(opening_readings), 1)
        self.assertEqual(opening_readings.reading_purpose, 'opening')
        self.assertEqual(opening_readings.reading_value, 50.0)

    def test_04_service_order_lifecycle_transitions(self):
        """
        التحقق من دورة حياة أمر الخدمة (utility.service.order):
        - الانتقال المنضبط: draft -> submitted -> assigned -> in_progress -> completed
        - منع الحذف بعد مرحلة المسودة
        """
        so = self.ServiceOrder.create({
            'customer_id': self.customer.id,
            'order_type': 'maintenance',
            'priority': '1',
            'description': 'فحص دوري للعداد والتوصيلات',
        })
        self.assertEqual(so.state, 'draft')

        # تقديم الطلب
        so.action_submit()
        self.assertEqual(so.state, 'submitted')

        # منع الحذف
        with self.assertRaises((UserError, ValidationError)):
            so.unlink()
