from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory', 'utility_security')
class TestUtilityInventorySecurity(TransactionCase):
    """Test ACL and physical_state computation for utility_inventory module."""

    def setUp(self):
        super().setUp()
        self.category = self.env['product.category'].create({'name': 'Security Test Category'})
        self.product = self.env['product.product'].create({
            'name': 'Security Test Meter Product',
            'type': 'consu',
            'tracking': 'serial',
            'categ_id': self.category.id,
        })
        self.lot = self.env['stock.lot'].create({
            'name': 'SN-SEC-001',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        self.internal_user = self.env['res.users'].create({
            'name': 'Inventory Internal User',
            'login': 'inv_internal_test',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_01_internal_user_can_create_integrity_issue(self):
        """Any internal user with base.group_user can create integrity issues."""
        meter = self.env['utility.meter'].create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].with_user(self.internal_user).create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test create for internal user',
        })
        self.assertTrue(issue.exists())

    def test_02_internal_user_can_read_integrity_issue(self):
        """Any internal user with base.group_user can read integrity issues."""
        meter = self.env['utility.meter'].create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test read for internal user',
        })
        result = issue.with_user(self.internal_user).read(['issue_type', 'severity', 'message'])
        self.assertTrue(result)

    def test_03_internal_user_can_write_integrity_issue(self):
        """Any internal user with base.group_user can write integrity issues."""
        meter = self.env['utility.meter'].create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test write for internal user',
        })
        issue.with_user(self.internal_user).write({'severity': 'critical'})
        self.assertEqual(issue.with_user(self.internal_user).severity, 'critical')

    def test_04_internal_user_can_unlink_integrity_issue(self):
        """Any internal user with base.group_user can delete integrity issues."""
        meter = self.env['utility.meter'].create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        issue = self.env['utility.meter.integrity.issue'].create({
            'meter_id': meter.id,
            'issue_type': 'lot_missing',
            'severity': 'warning',
            'message': 'Test unlink for internal user',
        })
        issue_id = issue.id
        issue.with_user(self.internal_user).unlink()
        self.assertFalse(self.env['utility.meter.integrity.issue'].browse(issue_id).exists())

    def test_05_model_has_access_rule_for_base_group_user(self):
        """The ACL grants full CRUD to base.group_user (all internal users)."""
        access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'utility.meter.integrity.issue'),
            ('group_id', '=', self.env.ref('base.group_user').id),
        ], limit=1)
        self.assertTrue(access, 'ACL for base.group_user must exist')
        self.assertTrue(access.perm_read)
        self.assertTrue(access.perm_write)
        self.assertTrue(access.perm_create)
        self.assertTrue(access.perm_unlink)

    def test_06_physical_state_unresolved_without_lot_or_product(self):
        """Meter without lot_id or product_id has physical_state='unresolved'."""
        meter = self.env['utility.meter'].create({})
        self.assertEqual(meter.physical_state, 'unresolved')

    def test_07_physical_state_unresolved_without_product(self):
        """Meter with lot but no product_id has physical_state='unresolved'."""
        meter = self.env['utility.meter'].create({
            'lot_id': self.lot.id,
        })
        self.assertEqual(meter.physical_state, 'unresolved')

    def test_08_physical_state_available_in_stock(self):
        """Meter with lot in stock location has physical_state='available'."""
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
            'location_id': warehouse.lot_stock_id.id,
            'inventory_quantity': 1,
        }).action_apply_inventory()
        meter = self.env['utility.meter'].create({
            'product_id': self.product.id,
            'lot_id': self.lot.id,
        })
        self.assertEqual(meter.physical_state, 'available')
