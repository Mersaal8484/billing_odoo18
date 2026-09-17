from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory', 'utility_security')
class TestUtilityInventorySecurity(TransactionCase):
    """Test ACL and record rules for utility_inventory module."""

    def setUp(self):
        super().setUp()
        self.Admin = self.env.ref('utility_core.group_utility_admin')
        self.Supervisor = self.env.ref('utility_core.group_utility_supervisor')
        self.Technician = self.env.ref('utility_core.group_utility_technician')
        self.Readonly = self.env.ref('utility_core.group_utility_readonly')

        self.admin_user = self.env['res.users'].create({
            'name': 'Inventory Admin',
            'login': 'inv_admin_test',
            'groups_id': [(6, 0, [self.Admin.id])],
        })
        self.supervisor_user = self.env['res.users'].create({
            'name': 'Inventory Supervisor',
            'login': 'inv_supervisor_test',
            'groups_id': [(6, 0, [self.Supervisor.id])],
        })
        self.technician_user = self.env['res.users'].create({
            'name': 'Inventory Technician',
            'login': 'inv_technician_test',
            'groups_id': [(6, 0, [self.Technician.id])],
        })
        self.readonly_user = self.env['res.users'].create({
            'name': 'Inventory Readonly',
            'login': 'inv_readonly_test',
            'groups_id': [(6, 0, [self.Readonly.id])],
        })

        self.category = self.env['product.category'].create({'name': 'Security Test Category'})
        self.product = self.env['product.product'].create({
            'name': 'Security Test Meter Product',
            'type': 'product',
            'tracking': 'serial',
            'categ_id': self.category.id,
        })
        self.lot = self.env['stock.lot'].create({
            'name': 'SN-SEC-001',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })

    def test_01_admin_full_access_integrity_issue(self):
        """Admin can create, read, write, and unlink integrity issues."""
        issue = self.env['utility.meter.integrity.issue'].sudo(self.admin_user).create({
            'meter_id': self.env['utility.meter'].create({
                'meter_number': 'MTR-SEC-001',
                'product_id': self.product.id,
                'lot_id': self.lot.id,
            }).id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test integrity issue for admin',
        })
        self.assertTrue(issue.sudo(self.admin_user).read(['name']))
        issue.sudo(self.admin_user).write({'severity': 'critical'})
        issue.sudo(self.admin_user).unlink()

    def test_02_readonly_user_cannot_create_integrity_issue(self):
        """Readonly user cannot create integrity issues."""
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-SEC-002',
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        with self.assertRaises(AccessError):
            self.env['utility.meter.integrity.issue'].sudo(self.readonly_user).create({
                'meter_id': meter.id,
                'issue_type': 'lot_missing',
                'severity': 'warning',
                'message': 'Should fail for readonly user',
            })

    def test_03_technician_can_read_but_not_create_integrity_issue(self):
        """Technician can read but cannot create integrity issues."""
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-SEC-003',
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].sudo(self.admin_user).create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test for technician read access',
        })
        self.assertTrue(issue.sudo(self.technician_user).read(['name']))
        with self.assertRaises(AccessError):
            issue.sudo(self.technician_user).write({'severity': 'critical'})

    def test_04_supervisor_can_write_integrity_issue(self):
        """Supervisor can write integrity issues but cannot unlink."""
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-SEC-004',
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].sudo(self.admin_user).create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test for supervisor write access',
        })
        issue.sudo(self.supervisor_user).write({'severity': 'critical'})
        self.assertEqual(issue.sudo(self.supervisor_user).severity, 'critical')
        with self.assertRaises(AccessError):
            issue.sudo(self.supervisor_user).unlink()

    def test_05_physical_state_computation(self):
        """Test physical state is computed correctly based on stock location."""
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-SEC-005',
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        self.assertEqual(meter.physical_state, 'unresolved')
