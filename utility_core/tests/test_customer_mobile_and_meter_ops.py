from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestCustomerMobileAndMeterOperationalNumber(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار الجوال الاختياري',
            'code': 'OPTIONAL-MOBILE-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار الجوال الاختياري',
            'code': 'OPTIONAL-MOBILE-SUBSCRIBER',
            'category_id': cls.category.id,
        })
        cls.region = cls.env['utility.region'].create({
            'name': 'منطقة اختبار الجوال الاختياري',
            'code': 'OPTIONAL-MOBILE-REGION',
            'type': 'region',
        })

    def _customer_without_mobile(self, suffix):
        partner = self.env['res.partner'].create({
            'name': 'عميل بدون جوال %s' % suffix,
            'region_id': self.region.id,
            'mobile': False,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPTIONAL-MOBILE-METER-%s' % suffix,
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
        })
        customer = self.env['utility.customer'].create({
            'customer_number': 'OPTIONAL-MOBILE-%s' % suffix,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': meter.id,
        })
        return customer, meter

    def test_customer_can_be_created_without_mobile(self):
        customer, _meter = self._customer_without_mobile('CREATE')
        self.assertFalse(customer.mobile)
        self.assertEqual(customer.state, 'draft')

    def test_customer_without_mobile_can_be_activated(self):
        customer, meter = self._customer_without_mobile('ACTIVATE')
        customer.action_activate()
        self.assertEqual(customer.state, 'active')
        self.assertEqual(customer.current_meter_assignment_id.meter_id, meter)
        self.assertFalse(customer.mobile)

    def test_meter_can_be_assigned_without_customer_mobile(self):
        customer, meter = self._customer_without_mobile('ASSIGN')
        self.assertEqual(customer.meter_id, meter)
        self.assertFalse(customer.mobile)

    def test_operational_number_is_normalized_and_searchable(self):
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPS-METER-001',
            'operational_number': '  OP-001  ',
        })
        self.assertEqual(meter.operational_number, 'OP-001')
        self.assertIn('[OP-001] OPS-METER-001', meter.display_name)
        matches = self.env['utility.meter'].name_search('OP-001')
        self.assertIn(meter.id, [record_id for record_id, _name in matches])
        meter.write({'operational_number': '   '})
        self.assertFalse(meter.operational_number)

    def test_operational_number_is_unique_per_company(self):
        self.env['utility.meter'].create({
            'meter_number': 'OPS-METER-002',
            'operational_number': 'OP-002',
        })
        with self.cr.savepoint(), self.assertRaises(IntegrityError):
            self.env['utility.meter'].create({
                'meter_number': 'OPS-METER-003',
                'operational_number': 'OP-002',
            })

    def test_sms_without_mobile_fails_with_explicit_code(self):
        notification = self.env['utility.notification.log'].create({
            'name': 'اختبار SMS',
            'channel': 'sms',
            'event_type': 'invoice_created',
            'body': 'رسالة اختبار',
        })
        notification.action_dispatch()
        self.assertEqual(notification.state, 'failed')
        self.assertIn('CUSTOMER_MOBILE_REQUIRED', notification.error_message)
