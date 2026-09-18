from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestOrganizationalScopeBilling(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.region_sanaa = self.env['utility.region'].create({
            'name': 'منطقة صنعاء Billing',
            'code': 'REG_SANAA_BILL',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_sanaa1 = self.env['utility.region'].create({
            'name': 'فرع التحرير Billing',
            'code': 'AREA_TAHREER_BILL',
            'type': 'area',
            'parent_id': self.region_sanaa.id,
            'company_id': self.company.id,
        })
        self.region_aden = self.env['utility.region'].create({
            'name': 'منطقة عدن Billing',
            'code': 'REG_ADEN_BILL',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.branch_aden1 = self.env['utility.region'].create({
            'name': 'فرع كريتر Billing',
            'code': 'AREA_CRATER_BILL',
            'type': 'area',
            'parent_id': self.region_aden.id,
            'company_id': self.company.id,
        })

        self.partner_sanaa = self.env['res.partner'].create({
            'name': 'مشترك صنعاء Billing',
            'region_id': self.region_sanaa.id,
            'area_id': self.branch_sanaa1.id,
            'company_id': self.company.id,
        })
        self.partner_aden = self.env['res.partner'].create({
            'name': 'مشترك عدن Billing',
            'region_id': self.region_aden.id,
            'area_id': self.branch_aden1.id,
            'company_id': self.company.id,
        })

        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة الفوترة',
            'code': 'CAT-BILL-01',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك الفوترة',
            'code': 'SUB-BILL-01',
            'category_id': self.category.id,
        })
        self.customer_sanaa = self.env['utility.customer'].create({
            'partner_id': self.partner_sanaa.id,
            'customer_number': 'CUST_SANAA_BILL_02',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })
        self.customer_aden = self.env['utility.customer'].create({
            'partner_id': self.partner_aden.id,
            'customer_number': 'CUST_ADEN_BILL_02',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })

        # Utility Bill (Sale Order with account_id)
        self.bill_sanaa = self.env['sale.order'].create({
            'partner_id': self.partner_sanaa.id,
            'account_id': self.customer_sanaa.id,
            'company_id': self.company.id,
        })
        self.bill_aden = self.env['sale.order'].create({
            'partner_id': self.partner_aden.id,
            'account_id': self.customer_aden.id,
            'company_id': self.company.id,
        })

        self.user_billing_sanaa = self.env['res.users'].create({
            'name': 'فوترة صنعاء',
            'login': 'bill_sanaa_user',
            'email': 'bill_sanaa@billing.local',
            'scope_mode': 'restricted',
            'assigned_region_ids': [(6, 0, [self.region_sanaa.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_billing_manager').id])],
        })

    def test_01_utility_bill_isolation(self):
        """Restricted Billing user in Sanaa sees Sanaa Utility Bill, not Aden Utility Bill."""
        bills = self.env['sale.order'].with_user(self.user_billing_sanaa).search([('account_id', '!=', False)])
        self.assertIn(self.bill_sanaa, bills)
        self.assertNotIn(self.bill_aden, bills)

    def test_02_non_utility_sale_order_unrestricted(self):
        """Non-utility sale order (account_id is False) remains visible to restricted users."""
        standard_sale = self.env['sale.order'].create({
            'partner_id': self.partner_aden.id,
            'account_id': False,
            'company_id': self.company.id,
        })
        bills = self.env['sale.order'].with_user(self.user_billing_sanaa).search([('id', '=', standard_sale.id)])
        self.assertIn(standard_sale, bills)

    def test_03_writeoff_action_scope_rejection(self):
        """Executing action_approve on out-of-scope write-off raises AccessError."""
        writeoff_aden = self.env['utility.writeoff'].create({
            'customer_id': self.customer_aden.id,
            'sale_order_id': self.bill_aden.id,
            'amount': 500.0,
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            writeoff_aden.with_user(self.user_billing_sanaa).action_approve()

    def test_04_billing_adjustment_action_scope_rejection(self):
        """Executing action_submit on out-of-scope billing adjustment raises AccessError."""
        date_range = self.env['date.range'].create({
            'name': 'يناير 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'company_id': self.company.id,
        })
        inv_aden = self.env['account.move'].create({
            'partner_id': self.partner_aden.id,
            'move_type': 'out_invoice',
            'company_id': self.company.id,
        })
        adj_aden = self.env['utility.billing.adjustment'].create({
            'customer_id': self.customer_aden.id,
            'billing_period_id': date_range.id,
            'sale_order_id': self.bill_aden.id,
            'invoice_id': inv_aden.id,
            'reason': 'تعديل استهلاك',
            'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            adj_aden.with_user(self.user_billing_sanaa).action_submit()
