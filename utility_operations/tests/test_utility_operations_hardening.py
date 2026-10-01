from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestUtilityOperationsHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة اختباري',
            'code': 'CAT-OPS-TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك اختباري',
            'code': 'SUB-OPS-TEST',
            'category_id': self.category.id,
        })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-OPS-001',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'partner_id': self.env['res.partner'].create({'name': 'شريك اختبار العمليات'}).id,
            'company_id': self.company.id,
        })
        self.meter_model = self.env['utility.meter.model'].create({
            'name': 'نموذج عداد العمليات',
            'code': 'MDL-OPS-001',
            'phase': 'single',
        })
        self.product = self.env['product.product'].create({
            'name': 'منتج عداد العمليات',
            'type': 'consu',
            'tracking': 'serial',
        })
        self.lot = self.env['stock.lot'].create({
            'name': 'SN-OPS-001',
            'product_id': self.product.id,
            'company_id': self.company.id,
        })
        self.meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-OPS-001',
            'model_id': self.meter_model.id,
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'company_id': self.company.id,
            'customer_id': self.customer.id,
        })

    def test_installation_lifecycle_transitions(self):
        """اختبار دورة حياة التركيبة (draft -> installed -> verified) وتأكيد الحظر على الانتقالات الباطلة."""
        inst = self.env['utility.installation'].create({
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
        })
        self.assertEqual(inst.state, 'draft')

        # Invalid transition: draft -> verified MUST fail
        with self.assertRaises(UserError):
            inst.action_verify()

        # Valid install: draft -> installed
        inst.action_install()
        self.assertEqual(inst.state, 'installed')
        self.assertTrue(bool(inst.meter_serial_snapshot))

        # Valid verify: installed -> verified
        inst.action_verify()
        self.assertEqual(inst.state, 'verified')

        # Invalid fail from verified MUST fail
        with self.assertRaises(UserError):
            inst.action_fail()

    def test_work_order_lifecycle_and_date_constraints(self):
        """اختبار دورة حياة أمر العمل والتحقق من قيد التواريخ."""
        wo = self.env['utility.work.order'].create({
            'work_type': 'maintenance',
            'description': 'صيانة دورية للعداد',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
        })
        self.assertEqual(wo.state, 'draft')

        # Assign without technician/team MUST fail
        with self.assertRaises(ValidationError):
            wo.action_assign()

        wo.assigned_technician_id = self.env.user.id
        wo.action_assign()
        self.assertEqual(wo.state, 'assigned')

        wo.action_start()
        self.assertEqual(wo.state, 'in_progress')
        self.assertTrue(bool(wo.date_started))

        # Invalid dates constraint test: date_started > date_completed MUST fail
        with self.assertRaises(ValidationError):
            wo.write({
                'date_started': '2026-08-14 12:00:00',
                'date_completed': '2026-08-14 10:00:00',
            })

        wo.write({'date_started': '2026-08-14 10:00:00', 'date_completed': '2026-08-14 14:00:00'})
        wo.action_complete()
        self.assertEqual(wo.state, 'completed')

        wo.action_verify()
        self.assertEqual(wo.state, 'verified')

        # Cancel on verified MUST fail
        with self.assertRaises(UserError):
            wo.action_cancel()

    def test_inspection_rating_constraint_and_completion(self):
        """اختبار قيد تقييم الحالة الاختياري (1-5) واكتفاء أدلة المعاينة عند الإكمال."""
        insp = self.env['utility.inspection'].create({
            'inspection_type': 'routine',
            'inspector_id': self.env.user.id,
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
        })
        self.assertEqual(insp.state, 'scheduled')

        # Invalid rating range (e.g. 6) MUST fail
        with self.assertRaises(ValidationError):
            insp.write({'condition_rating': 6})

        # Valid rating (e.g. 4)
        insp.condition_rating = 4
        insp.action_complete()
        self.assertEqual(insp.state, 'completed')

        # Re-completion MUST fail
        with self.assertRaises(UserError):
            inst_complete = insp.action_complete()

    def test_alarm_lifecycle_and_service_order_idempotency(self):
        """اختبار حراسة حالات الإنذار وعدم تكرار إنشاء أمر الخدمة (Idempotency + Lock)."""
        alarm = self.env['utility.alarm'].create({
            'alarm_type': 'tamper',
            'severity': 'critical',
            'description': 'إنذار تلاعب بالعداد',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
        })
        self.assertEqual(alarm.state, 'open')

        # State transition: open -> acknowledged -> investigating -> resolved
        alarm.action_acknowledge()
        self.assertEqual(alarm.state, 'acknowledged')

        alarm.action_start()
        self.assertEqual(alarm.state, 'investigating')

        # Create Service Order (First Call)
        res1 = alarm.action_create_service_order()
        self.assertTrue(bool(alarm.service_order_id))
        self.assertTrue(bool(alarm.tamper_case_id))
        so_id = alarm.service_order_id.id
        tc_id = alarm.tamper_case_id.id

        # Second Call: MUST return existing Service Order without creating new ones
        res2 = alarm.action_create_service_order()
        self.assertEqual(alarm.service_order_id.id, so_id)
        self.assertEqual(alarm.tamper_case_id.id, tc_id)

        alarm.action_resolve()
        self.assertEqual(alarm.state, 'resolved')

        # Dismiss on resolved MUST fail
        with self.assertRaises(UserError):
            alarm.action_close()

    def test_tamper_case_audit_log_once_on_proven(self):
        """اختبار إنشاء سجل التدقيق لمرة واحدة فقط عند الانتقال الصريح لـ proven."""
        case = self.env['utility.tamper.case'].create({
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'tamper_type': 'meter_bypass',
            'description': 'تجاوز العداد',
            'state': 'investigating',
        })

        initial_log_count = self.env['utility.meter.log'].search_count([('meter_id', '=', self.meter.id)])

        # Transition investigating -> proven MUST create 1 meter log
        case.write({'state': 'proven'})
        log_count_after_proven = self.env['utility.meter.log'].search_count([('meter_id', '=', self.meter.id)])
        self.assertEqual(log_count_after_proven, initial_log_count + 1)

        # Unrelated write on proven case MUST NOT create duplicate log
        case.write({'evidence_notes': 'ملاحظات إضافية على حالة مثبتة'})
        log_count_after_unrelated = self.env['utility.meter.log'].search_count([('meter_id', '=', self.meter.id)])
        self.assertEqual(log_count_after_unrelated, log_count_after_proven)
