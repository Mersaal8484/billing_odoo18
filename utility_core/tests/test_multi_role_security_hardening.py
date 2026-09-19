"""
Comprehensive Unit and Security Tests for Multi-Role, Route Scope, and Role Lifecycle Hardening
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, AccessError


class TestMultiRoleSecurityHardening(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Company = cls.env['res.company']
        cls.company_1 = cls.env.company
        cls.company_2 = cls.Company.create({'name': 'Test Power Company 2'})

        cls.Region = cls.env['utility.region']
        cls.region_a = cls.Region.create({'name': 'MR Region A', 'type': 'region', 'code': 'MR-RA', 'company_id': cls.company_1.id})
        cls.region_b = cls.Region.create({'name': 'MR Region B', 'type': 'region', 'code': 'MR-RB', 'company_id': cls.company_1.id})
        cls.branch_a = cls.Region.create({'name': 'MR Branch A', 'type': 'area', 'code': 'MR-BA', 'parent_id': cls.region_a.id, 'company_id': cls.company_1.id})
        cls.branch_b = cls.Region.create({'name': 'MR Branch B', 'type': 'area', 'code': 'MR-BB', 'parent_id': cls.region_b.id, 'company_id': cls.company_1.id})

        cls.Partner = cls.env['res.partner']
        cls.partner_a = cls.Partner.create({'name': 'MR Partner A', 'company_id': cls.company_1.id, 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id})
        cls.partner_b = cls.Partner.create({'name': 'MR Partner B', 'company_id': cls.company_1.id, 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id})

        cls.Route = cls.env['utility.route']
        cls.route_a1 = cls.Route.create({'name': 'MR Route A1', 'code': 'MR-RA1', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id, 'company_id': cls.company_1.id})
        cls.route_a2 = cls.Route.create({'name': 'MR Route A2', 'code': 'MR-RA2', 'region_id': cls.region_a.id, 'area_id': cls.branch_a.id, 'company_id': cls.company_1.id})
        cls.route_b1 = cls.Route.create({'name': 'MR Route B1', 'code': 'MR-RB1', 'region_id': cls.region_b.id, 'area_id': cls.branch_b.id, 'company_id': cls.company_1.id})

        cls.category = cls.env['utility.subscriber.category'].create({'name': 'MR Cat', 'company_id': cls.company_1.id})
        cls.subscriber_a = cls.env['utility.subscriber'].create({'name': 'MR Sub A', 'category_id': cls.category.id, 'company_id': cls.company_1.id})
        cls.subscriber_b = cls.env['utility.subscriber'].create({'name': 'MR Sub B', 'category_id': cls.category.id, 'company_id': cls.company_1.id})

        cls.customer_a1 = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_a.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber_a.id,
            'route_id': cls.route_a1.id, 'company_id': cls.company_1.id,
        })
        cls.customer_a2 = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_a.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber_a.id,
            'route_id': cls.route_a2.id, 'company_id': cls.company_1.id,
        })
        cls.customer_b1 = cls.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': cls.partner_b.id, 'category_id': cls.category.id, 'subscriber_id': cls.subscriber_b.id,
            'route_id': cls.route_b1.id, 'company_id': cls.company_1.id,
        })

        # Roles
        cls.role_collector = cls.env.ref('utility_core.role_collector')
        cls.role_meter_reader = cls.env.ref('utility_core.role_meter_reader')
        cls.role_technician = cls.env.ref('utility_core.role_technician')
        cls.role_supervisor = cls.env.ref('utility_core.role_supervisor')

        # Base test users
        cls.user_multi = cls.env['res.users'].create({
            'name': 'MR User Multi-Role',
            'login': 'mr_user_multi@test.local',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, cls.region_a.id)],
            'assigned_route_ids': [(4, cls.route_a1.id)],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('utility_core.group_utility_collector').id,
                cls.env.ref('utility_core.group_utility_meter_reader').id,
            ])],
        })

        cls.user_secondary = cls.env['res.users'].create({
            'name': 'MR User Secondary',
            'login': 'mr_user_sec@test.local',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, cls.region_a.id)],
            'assigned_route_ids': [(4, cls.route_a1.id)],
        })

    def test_01_user_groups_are_the_operational_role_source(self):
        """Staff metadata must not be needed to authorize a user's role."""
        staff = self.env['utility.staff'].create({
            'name': 'Staff Dual Role',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_collector.id, self.role_meter_reader.id])],
        })

        self.assertTrue(self.user_multi.has_group('utility_core.group_utility_collector'))
        self.assertTrue(self.user_multi.has_group('utility_core.group_utility_meter_reader'))
        self.assertTrue(staff.user_id)

    def test_01b_requested_operational_roles_are_seeded(self):
        """Requested role labels exist and reuse the canonical security groups."""
        role_group_map = {
            'role_reading_reviewer': 'group_utility_auditor',
            'role_commercial_manager': 'group_utility_revenue_manager',
            'role_area_accountant': 'group_utility_auditor',
        }
        for role_xmlid, group_xmlid in role_group_map.items():
            role = self.env.ref('utility_core.%s' % role_xmlid)
            group = self.env.ref('utility_core.%s' % group_xmlid)
            self.assertIn(group, role.group_ids)

        commercial_manager = self.env.ref('utility_core.role_commercial_manager')
        self.assertIn('المنطقة أو الفرع', commercial_manager.description)

    def test_02_staff_roles_do_not_mutate_user_groups(self):
        """Changing legacy staff roles cannot grant or revoke Odoo access groups."""
        custom_group = self.env.ref('base.group_partner_manager')
        self.user_multi.write({'groups_id': [(4, custom_group.id)]})

        staff = self.env['utility.staff'].create({
            'name': 'Staff Group Sync',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_collector.id, self.role_meter_reader.id])],
        })

        group_collector = self.env.ref('utility_core.group_utility_collector')
        group_reader = self.env.ref('utility_core.group_utility_meter_reader')

        self.assertIn(group_collector, self.user_multi.groups_id)
        self.assertIn(group_reader, self.user_multi.groups_id)
        self.assertIn(custom_group, self.user_multi.groups_id)

    def test_03_staff_user_reassignment_does_not_transfer_permissions(self):
        """Reassigning a custody profile must not transfer user permissions."""
        staff = self.env['utility.staff'].create({
            'name': 'Staff Reassign',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_meter_reader.id])],
        })

        group_reader = self.env.ref('utility_core.group_utility_meter_reader')
        self.assertIn(group_reader, self.user_multi.groups_id)
        self.assertNotIn(group_reader, self.user_secondary.groups_id)

        # Reassign to secondary user
        staff.write({'user_id': self.user_secondary.id})

        self.assertIn(group_reader, self.user_multi.groups_id)
        self.assertNotIn(group_reader, self.user_secondary.groups_id)

    def test_04_legacy_staff_role_edits_do_not_change_user_authorization(self):
        """Custody records do not turn legacy staff roles into permissions."""
        staff = self.env['utility.staff'].create({
            'name': 'Staff Custody Guard',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_collector.id, self.role_meter_reader.id])],
        })

        if 'utility.collection' in self.env:
            # Create open collection
            self.env['utility.collection'].create({
                'collector_id': staff.id,
                'state': 'confirmed',
                'amount': 500.0,
            })

            staff.write({'role_ids': [(6, 0, [self.role_meter_reader.id])]})
            self.assertTrue(self.user_multi.has_group('utility_core.group_utility_collector'))

    def test_05_route_scoped_orm_search_isolation(self):
        """Multi-role user assigned only to Route A1 must NOT see Route A2 or Route B1 in direct ORM search."""
        self.env['utility.staff'].create({
            'name': 'Staff Route Scoped',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_collector.id, self.role_meter_reader.id])],
        })

        # ORM search as user_multi
        visible_customers = self.env['utility.customer'].with_user(self.user_multi).search([])
        self.assertIn(self.customer_a1, visible_customers)
        self.assertNotIn(self.customer_a2, visible_customers)
        self.assertNotIn(self.customer_b1, visible_customers)

    def test_05a_route_keeps_readers_and_collectors_in_separate_lists(self):
        """Route form role lists share one scope relation without mixing roles."""
        reader = self.env['res.users'].create({
            'name': 'MR Reader Only',
            'login': 'mr_reader_only@test.local',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_meter_reader').id,
            ])],
        })
        collector = self.env['res.users'].create({
            'name': 'MR Collector Only',
            'login': 'mr_collector_only@test.local',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_collector').id,
            ])],
        })
        route = self.route_a1
        route.write({'meter_reader_user_ids': [(6, 0, [reader.id])]})
        self.assertEqual(route.meter_reader_user_ids, reader)
        self.assertFalse(route.collector_user_ids)
        self.assertIn(route, reader.assigned_route_ids)

        route.write({'collector_user_ids': [(6, 0, [collector.id])]})
        self.assertEqual(route.meter_reader_user_ids, reader)
        self.assertEqual(route.collector_user_ids, collector)
        self.assertIn(route, collector.assigned_route_ids)

        with self.assertRaises(ValidationError):
            route.write({'meter_reader_user_ids': [(6, 0, [collector.id])]})

    def test_06_organizational_scoped_roles_access_whole_region(self):
        """Billing Manager restricted to Region A can see both Route A1 and Route A2 without explicit route assignment."""
        user_mgr = self.env['res.users'].create({
            'name': 'MR Billing Manager A',
            'login': 'mr_bm_a@test.local',
            'company_id': self.company_1.id,
            'company_ids': [(6, 0, [self.company_1.id])],
            'groups_id': [(4, self.env.ref('utility_core.group_utility_billing_manager').id)],
            'scope_mode': 'restricted',
            'assigned_region_ids': [(4, self.region_a.id)],
        })

        visible_customers = self.env['utility.customer'].with_user(user_mgr).search([])
        self.assertIn(self.customer_a1, visible_customers)
        self.assertIn(self.customer_a2, visible_customers)
        self.assertNotIn(self.customer_b1, visible_customers)

    def test_07_company_isolation(self):
        """Users in Company 1 cannot see Company 2 customers regardless of role capabilities."""
        partner_c2 = self.Partner.create({'name': 'MR Partner C2', 'company_id': cls.company_2.id if hasattr(self, 'cls') else self.company_2.id})
        cust_c2 = self.env['utility.customer'].with_context(utility_scope_bypass=True).create({
            'partner_id': partner_c2.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_a.id,
            'company_id': self.company_2.id,
        })

        visible = self.env['utility.customer'].with_user(self.user_multi).search([])
        self.assertNotIn(cust_c2, visible)

    def test_08_legacy_role_commands_do_not_change_user_permissions(self):
        """All legacy M2M commands leave the user's Odoo groups unchanged."""
        staff = self.env['utility.staff'].create({
            'name': 'Staff M2M Custody Test',
            'user_id': self.user_multi.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_collector.id, self.role_meter_reader.id])],
        })

        if 'utility.collection' in self.env:
            self.env['utility.collection'].create({
                'collector_id': staff.id,
                'state': 'confirmed',
                'amount': 250.0,
            })

            staff.write({'role_ids': [(3, self.role_collector.id)]})
            staff.write({'role_ids': [(5,)]})
            self.assertTrue(self.user_multi.has_group('utility_core.group_utility_collector'))

    def test_09_implied_group_hierarchy_is_managed_on_users(self):
        """The Odoo group hierarchy, not staff records, supplies implied roles."""
        user_sup = self.env['res.users'].create({
            'name': 'MR User Supervisor',
            'login': 'mr_user_sup@test.local',
            'company_id': self.company_1.id,
            'company_ids': [(6, 0, [self.company_1.id])],
        })

        user_sup.write({'groups_id': [(4, self.env.ref('utility_core.group_utility_supervisor').id)]})
        self.env['utility.staff'].create({
            'name': 'Staff Supervisor',
            'user_id': user_sup.id,
            'company_id': self.company_1.id,
            'role_ids': [(6, 0, [self.role_supervisor.id])],
        })

        group_supervisor = self.env.ref('utility_core.group_utility_supervisor')
        group_collector = self.env.ref('utility_core.group_utility_collector')

        self.assertIn(group_supervisor, user_sup.groups_id)
        # Because supervisor implies collector, collector must remain on the user
        self.assertIn(group_collector, user_sup.groups_id)
