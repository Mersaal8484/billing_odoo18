from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestOrganizationalScopeOperations(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.region_sanaa = self.env['utility.region'].create({
            'name': 'منطقة صنعاء Operations',
            'code': 'REG_SANAA_OPS',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_sanaa1 = self.env['utility.region'].create({
            'name': 'فرع السبعين',
            'code': 'AREA_SABEEN',
            'type': 'area',
            'parent_id': self.region_sanaa.id,
            'company_id': self.company.id,
        })
        self.region_aden = self.env['utility.region'].create({
            'name': 'منطقة عدن Operations',
            'code': 'REG_ADEN_OPS',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_aden1 = self.env['utility.region'].create({
            'name': 'فرع المنصورة',
            'code': 'AREA_MANSOURA',
            'type': 'area',
            'parent_id': self.region_aden.id,
            'company_id': self.company.id,
        })

        self.partner_sanaa = self.env['res.partner'].create({
            'name': 'مشترك السبعين',
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'company_id': self.company.id,
        })
        self.partner_aden = self.env['res.partner'].create({
            'name': 'مشترك المنصورة',
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'company_id': self.company.id,
        })

        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار العمليات',
            'code': 'OPS-CAT-01',
        })
        self.subscriber = self.env['utility.subscriber'].create({
            'name': 'نوع اختبار العمليات',
            'code': 'OPS-SUB-01',
            'category_id': self.category.id,
        })

        self.customer_sanaa = self.env['utility.customer'].create({
            'partner_id': self.partner_sanaa.id,
            'customer_number': 'CUST_SABEEN_01',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'company_id': self.company.id,
        })
        self.customer_aden = self.env['utility.customer'].create({
            'partner_id': self.partner_aden.id,
            'customer_number': 'CUST_MANSOURA_01',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'company_id': self.company.id,
        })

        self.service_order_sanaa = self.env['utility.service.order'].create({
            'customer_id': self.customer_sanaa.id,
            'service_type': 'new_connection',
            'description': 'توصيل صنعاء',
            'order_number': 'SO-SANAA-TEST-001',
            'company_id': self.company.id,
        })
        self.service_order_aden = self.env['utility.service.order'].create({
            'customer_id': self.customer_aden.id,
            'service_type': 'new_connection',
            'description': 'توصيل عدن',
            'order_number': 'SO-ADEN-TEST-001',
            'company_id': self.company.id,
        })

        self.user_sanaa = self.env['res.users'].create({
            'name': 'فني صنعاء',
            'login': 'tech_sanaa_ops',
            'email': 'tech_sanaa@ops.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_sanaa.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_technician').id])],
        })

    def test_01_service_order_isolation(self):
        """Restricted user in Sanaa sees only Sanaa Service Order, not Aden."""
        orders = self.env['utility.service.order'].with_user(self.user_sanaa).search([])
        self.assertIn(self.service_order_sanaa, orders)
        self.assertNotIn(self.service_order_aden, orders)

    def test_02_service_order_action_scope_rejection(self):
        """Executing action on out-of-scope service order raises AccessError."""
        with self.assertRaises(AccessError):
            self.service_order_aden.with_user(self.user_sanaa).action_approve()

    def test_03_work_order_action_scope_rejection(self):
        """Executing action on out-of-scope work order raises AccessError."""
        wo_aden = self.env['utility.work.order'].create({
            'customer_id': self.customer_aden.id,
            'work_type': 'installation',
            'description': 'تركيب عدن',
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            wo_aden.with_user(self.user_sanaa).action_assign()

    def test_04_installation_action_scope_rejection(self):
        """Executing action on out-of-scope installation raises AccessError."""
        meter_aden = self.env['utility.meter'].create({
            'meter_number': 'MTR_ADEN_INST_01',
            'customer_id': self.customer_aden.id,
            'company_id': self.company.id,
        })
        inst_aden = self.env['utility.installation'].create({
            'customer_id': self.customer_aden.id,
            'meter_id': meter_aden.id,
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            inst_aden.with_user(self.user_sanaa).action_install()

    def test_05_inspection_action_scope_rejection(self):
        """Executing action on out-of-scope inspection raises AccessError."""
        insp_aden = self.env['utility.inspection'].create({
            'customer_id': self.customer_aden.id,
            'inspection_type': 'routine',
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            insp_aden.with_user(self.user_sanaa).action_complete()

    def test_06_alarm_scope_isolation(self):
        """Restricted user in Sanaa sees Sanaa alarm, not Aden alarm."""
        alarm_sanaa = self.env['utility.alarm'].create({
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'alarm_type': 'tamper',
            'severity': 'critical',
            'description': 'إنذار تلاعب صنعاء',
            'company_id': self.company.id,
        })
        alarm_aden = self.env['utility.alarm'].create({
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'alarm_type': 'tamper',
            'severity': 'critical',
            'description': 'إنذار تلاعب عدن',
            'company_id': self.company.id,
        })
        alarms = self.env['utility.alarm'].with_user(self.user_sanaa).search([])
        self.assertIn(alarm_sanaa, alarms)
        self.assertNotIn(alarm_aden, alarms)
