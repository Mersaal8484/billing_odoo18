import base64
import io
import json
from odoo.tests.common import HttpCase, tagged

@tagged('post_install', '-at_install')
class TestUtilityReaderAPI(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # إعداد مستخدم وعداد وفترة للاختبار
        cls.user = cls.env['res.users'].create({
            'name': 'Test Reader',
            'login': 'test_reader',
            'password': 'password',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('utility_core.group_utility_meter_reader').id])]
        })
        
        # إنشاء Regions (مناطق رئيسية)
        cls.region_1 = cls.env['utility.region'].create({'name': 'Region 1', 'code': 'RT-REG1', 'type': 'region', 'active': True})
        cls.region_2 = cls.env['utility.region'].create({'name': 'Region 2', 'code': 'RT-REG2', 'type': 'region', 'active': True})
        
        # إنشاء Area (منطقة فرعية) تابعة للمنطقة الأولى
        cls.area_1 = cls.env['utility.region'].create({
            'name': 'Area 1', 
            'code': 'RT-AREA1',
            'type': 'area', 
            'active': True,
            'parent_id': cls.region_1.id
        })
        
        # إنشاء المسار وربطه بالمنطقة الفرعية (مما سيقوم بحساب region_id تلقائياً)
        cls.route = cls.env['utility.route'].create({
            'name': 'Route 1',
            'code': 'R1TEST',
            'area_id': cls.area_1.id,
        })
        
        # إنشاء سجل كاشف للمستخدم وربطه بالمسار
        cls.meter_reader = cls.env['utility.meter.reader'].create({
            'name': 'Test Meter Reader',
            'user_id': cls.user.id,
            'route_ids': [(6, 0, [cls.route.id])],
        })

        cls.meter = cls.env['utility.meter'].create({
            'meter_number': 'TEST-1001',
            'active': True
        })

        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'Residential',
            'code': 'RES'
        })
        
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'Normal',
            'code': 'SUB_NORM',
            'category_id': cls.category.id
        })

        cls.customer = cls.env['utility.customer'].create({
            'customer_number': 'CUST-1001',
            'meter_id': cls.meter.id,
            'route_id': cls.route.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        cls.meter.customer_id = cls.customer.id
        
        cls.period_type = cls.env['date.range.type'].create({
            'name': 'Monthly Reading',
            'allow_overlap': True
        })
        
        # إنشاء فترة مغلقة
        cls.closed_period = cls.env['date.range'].create({
            'name': 'Closed Period',
            'period_role': 'reading',
            'state': 'closed',
            'type_id': cls.period_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
        })
        
        # إنشاء فترة مفتوحة لمنطقة أخرى
        cls.other_region_period = cls.env['date.range'].create({
            'name': 'Other Region Period',
            'period_role': 'reading',
            'state': 'open',
            'region_ids': [(6, 0, [cls.region_2.id])],
            'type_id': cls.period_type.id,
            'date_start': '2026-02-01',
            'date_end': '2026-02-28',
        })

        cls.route_period = cls.env['date.range'].create({
            'name': 'Route Region Period',
            'period_role': 'reading',
            'state': 'open',
            'region_ids': [(6, 0, [cls.region_1.id])],
            'type_id': cls.period_type.id,
            'date_start': '2026-03-01',
            'date_end': '2026-03-31',
        })

    def test_get_periods_geographic_filter(self):
        """ (أ) اختبار أن get_periods لا يرجع فترات لمنطقة أخرى غير منطقة الكاشف """
        self.authenticate('test_reader', 'password')
        response = self.url_open(
            '/api/v1/utility/reading/periods',
            data=json.dumps({'params': {}}),
            headers={'Content-Type': 'application/json'}
        )
        result = response.json().get('result', {})
        self.assertTrue(result.get('success', False))
        
        periods = result.get('periods', [])
        period_ids = [p['id'] for p in periods]
        # يجب ألا تظهر الفترة المخصصة لمنطقة أخرى (Other Region Period)
        self.assertNotIn(self.other_region_period.id, period_ids)

    def test_submit_reading_closed_period(self):
        """ (ب) اختبار رفض القراءة برمز PERIOD_CLOSED عند إرسال فترة مغلقة """
        self.authenticate('test_reader', 'password')
        response = self.url_open(
            '/api/v1/utility/reader/reading/submit',
            data=json.dumps({
                'params': {
                    'meter_id': self.meter.id,
                    'period_id': self.closed_period.id,
                    'reading_value': 100.0
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        result = response.json().get('result', {})
        self.assertFalse(result.get('success', True))
        self.assertEqual(result.get('code'), 'PERIOD_CLOSED')

    def test_submit_reading_saves_image_and_links_media_asset(self):
        """(ب2) رفع صورة مع القراءة الفردية يجب أن يربط أصل الوسائط بالقراءة فعلياً."""
        from PIL import Image

        buf = io.BytesIO()
        Image.new('RGB', (60, 60), (30, 140, 80)).save(buf, 'JPEG')

        self.authenticate('test_reader', 'password')
        response = self.url_open(
            '/api/v1/utility/reader/reading/submit',
            data=json.dumps({
                'params': {
                    'meter_id': self.meter.id,
                    'period_id': self.route_period.id,
                    'reading_value': 120.0,
                    'image_b64': base64.b64encode(buf.getvalue()).decode('utf-8'),
                }
            }),
            headers={'Content-Type': 'application/json'},
        )
        result = response.json().get('result', {})
        self.assertTrue(result.get('success'), result)

        reading = self.env['utility.reading'].browse(result['reading_id'])
        self.assertTrue(reading.image_asset_id, 'يجب ربط أصل الوسائط بالقراءة عند رفع الصورة')
        self.assertEqual(reading.image_asset_id.state, 'ready')
        self.assertEqual(reading.image_asset_id.reading_id, reading)
        self.assertEqual(reading.image_state, 'pending', 'الصورة المرفوعة تنتظر مراجعة المشرف')
        self.assertTrue(reading.meter_image_url, 'يجب توليد رابط معاينة للصورة المخزنة')

    def test_create_batch_from_assigned_route_without_region_assignment(self):
        """A route-assigned reader can create only their own reading batch."""
        self.assertFalse(self.user.assigned_region_ids)
        self.assertIn(self.route, self.user.assigned_route_ids)

        self.authenticate('test_reader', 'password')
        response = self.url_open(
            '/api/v1/utility/reading/batch/create',
            data=json.dumps({
                'params': {
                    'date_range_id': self.route_period.id,
                    'total_readings': 1,
                }
            }),
            headers={'Content-Type': 'application/json'},
        )
        result = response.json().get('result', {})
        self.assertTrue(result.get('success'), result)

        batch = self.env['utility.reading.batch'].browse(result['batch_id'])
        self.assertEqual(batch.user_id, self.user)
        self.assertEqual(batch.region_id, self.region_1)

    def test_multipart_image_endpoint_returns_plain_json_validation_error(self):
        """The mobile multipart endpoint is registered and does not use JSON-RPC."""
        self.authenticate('test_reader', 'password')
        response = self.url_open(
            '/api/v1/utility/reading/batch/upload_image_multipart',
            data={'batch_id': '1'},
        )
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertFalse(result.get('success'))
        self.assertEqual(result.get('code'), 'VALIDATION_ERROR')
