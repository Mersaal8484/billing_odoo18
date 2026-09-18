from odoo.tests.common import TransactionCase


class TestOrganizationalScopeAPI(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.region_sanaa = self.env['utility.region'].create({
            'name': 'منطقة صنعاء API',
            'code': 'REG_SANAA_API',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_sanaa1 = self.env['utility.region'].create({
            'name': 'فرع التحرير API',
            'code': 'AREA_TAHREER_API',
            'type': 'area',
            'parent_id': self.region_sanaa.id,
            'company_id': self.company.id,
        })
        self.region_aden = self.env['utility.region'].create({
            'name': 'منطقة عدن API',
            'code': 'REG_ADEN_API',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_aden1 = self.env['utility.region'].create({
            'name': 'فرع كريتر API',
            'code': 'AREA_CRATER_API',
            'type': 'area',
            'parent_id': self.region_aden.id,
            'company_id': self.company.id,
        })

        self.partner_sanaa = self.env['res.partner'].create({
            'name': 'مشترك صنعاء API',
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'company_id': self.company.id,
        })
        self.partner_aden = self.env['res.partner'].create({
            'name': 'مشترك عدن API',
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'company_id': self.company.id,
        })

        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة API',
            'code': 'CAT-API-01',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك API',
            'code': 'SUB-API-01',
            'category_id': self.category.id,
        })
        self.customer_sanaa = self.env['utility.customer'].create({
            'partner_id': self.partner_sanaa.id,
            'customer_number': 'CUST_SANAA_API_01',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })
        self.customer_aden = self.env['utility.customer'].create({
            'partner_id': self.partner_aden.id,
            'customer_number': 'CUST_ADEN_API_01',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })

        self.meter_sanaa = self.env['utility.meter'].create({
            'meter_number': 'MTR_SANAA_API_01',
            'customer_id': self.customer_sanaa.id,
            'company_id': self.company.id,
        })
        self.meter_aden = self.env['utility.meter'].create({
            'meter_number': 'MTR_ADEN_API_01',
            'customer_id': self.customer_aden.id,
            'company_id': self.company.id,
        })

        self.user_reader_sanaa = self.env['res.users'].create({
            'name': 'قارئ صنعاء',
            'login': 'reader_sanaa_api',
            'email': 'reader_sanaa@api.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_sanaa.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_collector').id])],
        })

    def test_01_meter_resolution_scope_rejection(self):
        """Restricted reader in Sanaa resolves Sanaa meter, but Aden meter returns not found."""
        Meter = self.env['utility.meter'].with_user(self.user_reader_sanaa)
        meter_sanaa_res = Meter.search([('meter_number', '=', 'MTR_SANAA_API_01')])
        meter_aden_res = Meter.search([('meter_number', '=', 'MTR_ADEN_API_01')])

        self.assertTrue(meter_sanaa_res)
        self.assertFalse(meter_aden_res)

    def test_02_read_group_and_search_count_isolation(self):
        """Dashboard aggregates (read_group and search_count) exclude out-of-scope data."""
        Customer = self.env['utility.customer'].with_user(self.user_reader_sanaa)
        count = Customer.search_count([])
        self.assertEqual(count, 1)

        groups = Customer.read_group([], fields=['region_id'], groupby=['region_id'], lazy=False)
        region_ids = [g['region_id'][0] for g in groups if g.get('region_id')]
        self.assertIn(self.region_sanaa.id, region_ids)
        self.assertNotIn(self.region_aden.id, region_ids)
