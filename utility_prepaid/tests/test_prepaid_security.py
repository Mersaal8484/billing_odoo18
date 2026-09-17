from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'utility_release', 'utility_prepaid', 'utility_security')
class TestUtilityPrepaidSecurity(TransactionCase):
    """Test ACL for utility_prepaid module after base.group_user restriction."""

    def setUp(self):
        super().setUp()
        self.PrepaidAdmin = self.env.ref('utility_prepaid.group_utility_prepaid_admin')
        self.PrepaidUser = self.env.ref('utility_prepaid.group_utility_prepaid_user')
        self.PrepaidCashier = self.env.ref('utility_prepaid.group_utility_prepaid_cashier')
        self.PrepaidSupervisor = self.env.ref('utility_prepaid.group_utility_prepaid_supervisor')

        self.prepaid_admin = self.env['res.users'].create({
            'name': 'Prepaid Admin',
            'login': 'prepaid_admin_test',
            'groups_id': [(6, 0, [self.PrepaidAdmin.id])],
        })
        self.prepaid_user = self.env['res.users'].create({
            'name': 'Prepaid User',
            'login': 'prepaid_user_test',
            'groups_id': [(6, 0, [self.PrepaidUser.id])],
        })
        self.prepaid_cashier = self.env['res.users'].create({
            'name': 'Prepaid Cashier',
            'login': 'prepaid_cashier_test',
            'groups_id': [(6, 0, [self.PrepaidCashier.id])],
        })
        self.prepaid_supervisor = self.env['res.users'].create({
            'name': 'Prepaid Supervisor',
            'login': 'prepaid_supervisor_test',
            'groups_id': [(6, 0, [self.PrepaidSupervisor.id])],
        })

    def test_01_prepaid_user_can_read_vending_request(self):
        """Prepaid user can read vending requests."""
        vending = self.env['utility.vending.request'].sudo(self.prepaid_admin).create({
            'customer_id': self.env['utility.customer'].create({
                'customer_number': 'PREPAID-SEC-001',
                'partner_id': self.env['res.partner'].create({'name': 'Prepaid Test Partner'}).id,
            }).id,
            'amount': 100.0,
        })
        self.assertTrue(vending.sudo(self.prepaid_user).read(['state']))

    def test_02_prepaid_user_can_create_vending_request(self):
        """Prepaid user can create vending requests."""
        customer = self.env['utility.customer'].sudo(self.prepaid_admin).create({
            'customer_number': 'PREPAID-SEC-002',
            'partner_id': self.env['res.partner'].create({'name': 'Prepaid Test Partner 2'}).id,
        })
        vending = self.env['utility.vending.request'].sudo(self.prepaid_user).create({
            'customer_id': customer.id,
            'amount': 50.0,
        })
        self.assertTrue(vending)

    def test_03_prepaid_user_cannot_unlink_vending_request(self):
        """Prepaid user cannot delete vending requests."""
        customer = self.env['utility.customer'].sudo(self.prepaid_admin).create({
            'customer_number': 'PREPAID-SEC-003',
            'partner_id': self.env['res.partner'].create({'name': 'Prepaid Test Partner 3'}).id,
        })
        vending = self.env['utility.vending.request'].sudo(self.prepaid_admin).create({
            'customer_id': customer.id,
            'amount': 75.0,
        })
        with self.assertRaises(AccessError):
            vending.sudo(self.prepaid_user).unlink()

    def test_04_prepaid_cashier_can_read_token(self):
        """Prepaid cashier can read tokens."""
        token = self.env['utility.token'].sudo(self.prepaid_admin).create({
            'token_number': 'TOKEN-SEC-001',
            'amount': 200.0,
        })
        self.assertTrue(token.sudo(self.prepaid_cashier).read(['token_number']))

    def test_05_prepaid_user_cannot_read_token(self):
        """Basic prepaid user cannot read tokens (cashier required)."""
        token = self.env['utility.token'].sudo(self.prepaid_admin).create({
            'token_number': 'TOKEN-SEC-002',
            'amount': 150.0,
        })
        with self.assertRaises(AccessError):
            token.sudo(self.prepaid_user).read(['token_number'])

    def test_06_prepaid_supervisor_can_write_reversal(self):
        """Prepaid supervisor can write vending reversals."""
        reversal = self.env['utility.vending.reversal'].sudo(self.prepaid_admin).create({
            'reason': 'Test reversal for security',
        })
        reversal.sudo(self.prepaid_supervisor).write({'reason': 'Updated reason'})
        self.assertEqual(reversal.sudo(self.prepaid_supervisor).reason, 'Updated reason')

    def test_07_prepaid_user_cannot_create_reversal(self):
        """Basic prepaid user cannot create reversals (supervisor required)."""
        with self.assertRaises(AccessError):
            self.env['utility.vending.reversal'].sudo(self.prepaid_user).create({
                'reason': 'Should fail for basic user',
            })

    def test_08_prepaid_officer_can_read_dashboard(self):
        """Prepaid officer can read dashboard."""
        dashboard = self.env['utility.prepaid.dashboard'].sudo(self.prepaid_admin).create({})
        self.assertTrue(dashboard.sudo(self.prepaid_user).read(['id']))
