from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.utility_billing.controllers import utility_billing_api
from odoo.addons.utility_billing.controllers import utility_reader_api


class TestMeterOperationalBillingAPI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار API الرقم التشغيلي',
            'code': 'OPS-API-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار API الرقم التشغيلي',
            'code': 'OPS-API-SUBSCRIBER',
            'category_id': cls.category.id,
        })
        cls.income = cls.env['account.account'].search([
            ('company_ids', 'in', [cls.env.company.id]),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        range_type = cls.env['date.range.type'].create({
            'name': 'نوع فترة اختبار API الرقم التشغيلي',
            'default_billing_period': 'monthly',
            'allow_overlap': True,
        })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار API الرقم التشغيلي',
            'period_code': 'OPS-API-2026-08',
            'cycle_key': 'OPS-API-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _meter_and_customer(self, suffix='001', external_qr_reference=False, route_id=False):
        route = self.env['utility.route'].browse(route_id.id if hasattr(route_id, 'id') else route_id) if route_id else False
        partner = self.env['res.partner'].create({
            'name': 'عميل API بدون جوال %s' % suffix,
            'mobile': False,
            'region_id': route.region_id.id if route and route.region_id else False,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPS-API-METER-%s' % suffix,
            'operational_number': 'OPS-API-NUMBER-%s' % suffix,
            'payment_type': 'postpaid',
        })
        customer = self.env['utility.customer'].create({
            'customer_number': 'OPS-API-CUSTOMER-%s' % suffix,
            'external_qr_reference': external_qr_reference,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': meter.id,
            'route_id': route_id,
        })
        meter.write({
            'customer_id': customer.id,
            'connection_type': 'subscriber',
        })
        return meter, customer

    def _request(self, params, user=None):
        env = self.env if user is None else self.env(user=user)
        return SimpleNamespace(env=env, jsonrequest=params)

    def test_billing_invoice_works_without_mobile(self):
        if not self.income or not self.journal:
            self.skipTest('Accounting demo accounts are not available.')
        meter, customer = self._meter_and_customer('BILL')
        order = self.env['sale.order'].create({
            'partner_id': customer.partner_id.id,
            'customer_id': customer.id,
            'meter_id': meter.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.journal.id,
            'partner_id': customer.partner_id.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'فاتورة اختبار بدون جوال',
                'quantity': 1.0,
                'price_unit': 100.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertFalse(customer.mobile)

    def test_collector_account_uses_partner_receivable_for_opening_arrears(self):
        """Opening-balance move lines must be collectible, not hidden by sync."""
        if not self.income or not self.journal:
            self.skipTest('Accounting demo accounts are not available.')
        meter, customer = self._meter_and_customer('COLLECTOR-ARREARS')
        receivable = self.env['account.account'].search([
            ('company_ids', 'in', [self.env.company.id]),
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        general_journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not receivable or not general_journal:
            self.skipTest('Required accounting journals are not available.')

        order = self.env['sale.order'].create({
            'partner_id': customer.partner_id.id,
            'customer_id': customer.id,
            'meter_id': meter.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.journal.id,
            'partner_id': customer.partner_id.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Current collector bill',
                'quantity': 1.0,
                'price_unit': 500.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        opening = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': general_journal.id,
            'date': date(2026, 7, 1),
            'line_ids': [
                (0, 0, {
                    'name': 'Migrated arrears',
                    'account_id': receivable.id,
                    'partner_id': customer.partner_id.id,
                    'debit': 300.0,
                }),
                (0, 0, {
                    'name': 'Migrated arrears offset',
                    'account_id': self.income.id,
                    'credit': 300.0,
                }),
            ],
        })
        opening.action_post()

        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({})):
            result = controller._collector_account_payload(customer)

        account = result['account']
        self.assertAlmostEqual(account['current_bill'], 500.0, places=2)
        self.assertAlmostEqual(account['debt_amount'], 300.0, places=2)
        self.assertAlmostEqual(account['due_amount'], 800.0, places=2)

    def test_reader_lookup_by_operational_number_returns_it(self):
        meter, _customer = self._meter_and_customer('LOOKUP')
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'operational_number': meter.operational_number})):
            result = controller.meter_lookup(operational_number=meter.operational_number)
        self.assertTrue(result['success'])
        self.assertEqual(result['meter']['id'], meter.id)
        self.assertEqual(result['meter']['operational_number'], meter.operational_number)

    def test_reader_lookup_uses_migrated_meter_baseline_without_history(self):
        meter, customer = self._meter_and_customer('MIGRATED-BASELINE')
        meter.write({
            'last_reading_value': 91859.0,
            'last_read_date': '2026-09-15 00:00:00',
        })
        customer.write({
            'last_reading_value': 91859.0,
            'last_reading_date': '2026-09-15 00:00:00',
        })

        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_number': meter.meter_number})):
            result = controller.meter_lookup(meter_number=meter.meter_number)

        self.assertTrue(result['success'])
        self.assertEqual(result['last_reading_value'], 91859.0)
        self.assertEqual(result['last_reading_date'], '2026-09-15T00:00:00')
        self.assertEqual(len(result['reading_history']), 1)
        self.assertEqual(result['reading_history'][0]['source'], 'migration_baseline')
        self.assertEqual(
            result['reading_history'][0]['reading_date'],
            '2026-09-15T00:00:00',
        )

    def test_reader_lookup_conflicting_identifiers_is_rejected(self):
        first, _customer = self._meter_and_customer('MISMATCH-A')
        second, _customer = self._meter_and_customer('MISMATCH-B')
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_id': first.id,
                'operational_number': second.operational_number})):
            result = controller.meter_lookup(
                meter_id=first.id,
                operational_number=second.operational_number,
            )
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'METER_IDENTIFIER_MISMATCH')

    def test_customer_lookup_by_external_qr_reference(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-LOOKUP', 'QR-CUSTOMER-LOOKUP')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'external_qr_reference': 'QR-CUSTOMER-LOOKUP'})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['customer']['customer_id'], customer.id)
        self.assertEqual(result['customer']['external_qr_reference'], 'QR-CUSTOMER-LOOKUP')

    def test_customer_lookup_by_meter_number_accepts_mobile_search_value(self):
        meter, customer = self._meter_and_customer('COLLECTOR-METER-LOOKUP')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'lookup_value': meter.meter_number})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['customer']['customer_id'], customer.id)

    def test_customer_lookup_reads_jsonrpc_params_envelope(self):
        """Live Odoo JSON routes receive identifiers below ``params``."""
        meter, customer = self._meter_and_customer('JSONRPC-LOOKUP')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {'lookup_value': meter.meter_number},
            })):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['customer']['customer_id'], customer.id)

    def test_customer_lookup_by_operational_number_accepts_mobile_search_value(self):
        meter, customer = self._meter_and_customer('COLLECTOR-OPER-LOOKUP')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'lookup_value': meter.operational_number})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['customer']['customer_id'], customer.id)

    def test_customer_lookup_matching_identifiers_succeeds(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-MATCH', 'QR-CUSTOMER-MATCH')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': customer.customer_number,
                'external_qr_reference': customer.external_qr_reference})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])

    def test_customer_lookup_conflicting_identifiers_is_rejected(self):
        _meter, first = self._meter_and_customer('CUSTOMER-MISMATCH-A', 'QR-CUSTOMER-A')
        _meter, _second = self._meter_and_customer('CUSTOMER-MISMATCH-B', 'QR-CUSTOMER-B')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': first.customer_number,
                'external_qr_reference': 'QR-CUSTOMER-B'})):
            result = controller.customer_lookup()
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'CUSTOMER_IDENTIFIER_MISMATCH')

    def test_customer_qr_update_is_idempotent_and_editable(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-UPDATE', 'QR-UPDATE-OLD')
        controller = utility_billing_api.UtilityBillingAPI()
        for reference in ('QR-UPDATE-OLD', 'QR-UPDATE-NEW'):
            with patch.object(utility_billing_api, 'request', self._request({
                    'customer_number': customer.customer_number,
                    'new_external_qr_reference': reference})):
                result = controller.update_customer_qr_reference()
            self.assertTrue(result['success'])
            self.assertEqual(result['customer']['external_qr_reference'], reference)

    def test_customer_qr_update_rejects_another_customers_qr(self):
        _meter, first = self._meter_and_customer('CUSTOMER-OWNER-A', 'QR-OWNER-A')
        _meter, second = self._meter_and_customer('CUSTOMER-OWNER-B', 'QR-OWNER-B')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': second.customer_number,
                'new_external_qr_reference': first.external_qr_reference})):
            result = controller.update_customer_qr_reference()
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'QR_REFERENCE_ALREADY_ASSIGNED')

    def test_reader_lookup_in_assigned_route_succeeds(self):
        region = self.env['utility.region'].create({
            'name': 'منطقة API مسار',
            'code': 'OPS-REG-RT-01',
            'type': 'region',
        })
        area = self.env['utility.region'].create({
            'name': 'فرع API مسار',
            'code': 'OPS-AREA-RT-01',
            'type': 'area',
            'parent_id': region.id,
        })
        route_a = self.env['utility.route'].create({
            'name': 'مسار قارئ أ',
            'code': 'OPS-RT-A',
            'area_id': area.id,
        })
        reader_user = self.env['res.users'].create({
            'name': 'قارئ اختبار API',
            'login': 'ops_reader_test_user',
            'email': 'ops_reader@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_meter_reader').id])],
            'assigned_region_ids': [(6, 0, [region.id])],
            'assigned_route_ids': [(6, 0, [route_a.id])],
        })
        meter_a, _ = self._meter_and_customer('ROUTE-A', route_id=route_a.id)
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_number': meter_a.meter_number}, user=reader_user)):
            result = controller.meter_lookup(meter_number=meter_a.meter_number)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['meter']['id'], meter_a.id)

    def test_reader_lookup_outside_assigned_route_rejected(self):
        region = self.env['utility.region'].create({
            'name': 'منطقة API مسار 2',
            'code': 'OPS-REG-RT-02',
            'type': 'region',
        })
        area = self.env['utility.region'].create({
            'name': 'فرع API مسار 2',
            'code': 'OPS-AREA-RT-02',
            'type': 'area',
            'parent_id': region.id,
        })
        route_a = self.env['utility.route'].create({
            'name': 'مسار قارئ أ 2',
            'code': 'OPS-RT-A2',
            'area_id': area.id,
        })
        route_b = self.env['utility.route'].create({
            'name': 'مسار قارئ ب 2',
            'code': 'OPS-RT-B2',
            'area_id': area.id,
        })
        reader_user = self.env['res.users'].create({
            'name': 'قارئ اختبار API 2',
            'login': 'ops_reader_test_user_2',
            'email': 'ops_reader2@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_meter_reader').id])],
            'assigned_region_ids': [(6, 0, [region.id])],
            'assigned_route_ids': [(6, 0, [route_a.id])],
        })
        meter_b, _ = self._meter_and_customer('ROUTE-B', route_id=route_b.id)
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_number': meter_b.meter_number}, user=reader_user)):
            result = controller.meter_lookup(meter_number=meter_b.meter_number)
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'OUT_OF_SCOPE')

    def test_check_period_reading_outside_assigned_route_rejected(self):
        region = self.env['utility.region'].create({
            'name': 'منطقة API مسار 3',
            'code': 'OPS-REG-RT-03',
            'type': 'region',
        })
        area = self.env['utility.region'].create({
            'name': 'فرع API مسار 3',
            'code': 'OPS-AREA-RT-03',
            'type': 'area',
            'parent_id': region.id,
        })
        route_a = self.env['utility.route'].create({
            'name': 'مسار قارئ أ 3',
            'code': 'OPS-RT-A3',
            'area_id': area.id,
        })
        route_b = self.env['utility.route'].create({
            'name': 'مسار قارئ ب 3',
            'code': 'OPS-RT-B3',
            'area_id': area.id,
        })
        reader_user = self.env['res.users'].create({
            'name': 'قارئ اختبار API 3',
            'login': 'ops_reader_test_user_3',
            'email': 'ops_reader3@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('utility_core.group_utility_meter_reader').id])],
            'assigned_region_ids': [(6, 0, [region.id])],
            'assigned_route_ids': [(6, 0, [route_a.id])],
        })
        meter_b, _ = self._meter_and_customer('ROUTE-B3', route_id=route_b.id)
        patch_controller = utility_reader_api.UtilityReaderApiPatch()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_code': meter_b.meter_number, 'period_id': self.period.id}, user=reader_user)):
            result = patch_controller.check_period_reading(meter_code=meter_b.meter_number, period_id=self.period.id)
        self.assertFalse(result['has_reading'])
        self.assertEqual(result.get('code'), 'OUT_OF_SCOPE')

    def test_reader_lookup_unauthorized_role_rejected(self):
        meter, _ = self._meter_and_customer('UNAUTH-METER')
        unprivileged_user = self.env['res.users'].create({
            'name': 'مستخدم بدون أدوار عمليات',
            'login': 'ops_unauth_test_user',
            'email': 'ops_unauth@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_number': meter.meter_number}, user=unprivileged_user)):
            result = controller.meter_lookup(meter_number=meter.meter_number)
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'FORBIDDEN')

    def test_route_only_supervisor_scope_on_both_meter_endpoints(self):
        """Route-only non-readers cannot fall through to unrestricted lookup."""
        region = self.env['utility.region'].create({
            'name': 'منطقة المشرف المقيد بالمسار',
            'code': 'OPS-SUP-REG',
            'type': 'region',
        })
        area = self.env['utility.region'].create({
            'name': 'فرع المشرف المقيد بالمسار',
            'code': 'OPS-SUP-AREA',
            'type': 'area',
            'parent_id': region.id,
        })
        route_a, route_b = self.env['utility.route'].create([
            {'name': 'مسار المشرف أ', 'code': 'OPS-SUP-A', 'area_id': area.id},
            {'name': 'مسار المشرف ب', 'code': 'OPS-SUP-B', 'area_id': area.id},
        ])
        supervisor = self.env['res.users'].create({
            'name': 'مشرف مقيد بمسار فقط',
            'login': 'ops_route_only_supervisor',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_supervisor').id,
            ])],
            'scope_mode': 'restricted',
            'assigned_route_ids': [(6, 0, route_a.ids)],
        })
        self.assertFalse(supervisor.has_group('utility_core.group_utility_meter_reader'))
        self.assertFalse(supervisor._get_effective_region_ids())
        self.assertFalse(supervisor._get_effective_branch_ids())
        meter_a, _ = self._meter_and_customer('SUP-A', route_id=route_a.id)
        meter_b, _ = self._meter_and_customer('SUP-B', route_id=route_b.id)
        unassigned_meter, _ = self._meter_and_customer('SUP-NONE')
        controller = utility_reader_api.UtilityReaderAPI()
        period_controller = utility_reader_api.UtilityReaderApiPatch()

        with patch.object(utility_reader_api, 'request', self._request({}, user=supervisor)):
            self.assertTrue(controller.meter_lookup(meter_id=meter_a.id)['success'])
            allowed = period_controller.check_period_reading(
                meter_code=meter_a.meter_number, period_id=self.period.id)
            self.assertNotIn('error', allowed)
            for meter in (meter_b, unassigned_meter):
                with self.subTest(meter=meter.meter_number):
                    rejected = controller.meter_lookup(meter_id=meter.id)
                    self.assertFalse(rejected['success'])
                    self.assertEqual(rejected['code'], 'OUT_OF_SCOPE')
                    rejected_period = period_controller.check_period_reading(
                        meter_code=meter.meter_number, period_id=self.period.id)
                    self.assertEqual(rejected_period['code'], 'OUT_OF_SCOPE')

        supervisor.write({'assigned_route_ids': [(5, 0, 0)]})
        with patch.object(utility_reader_api, 'request', self._request({}, user=supervisor)):
            self.assertEqual(controller.meter_lookup(meter_id=meter_a.id)['code'], 'OUT_OF_SCOPE')
            self.assertEqual(period_controller.check_period_reading(
                meter_code=meter_a.meter_number, period_id=self.period.id)['code'], 'OUT_OF_SCOPE')

    def test_reader_lookup_global_scope_without_operational_role_rejected(self):
        """P0: A user having is_global scope (e.g. auditor/general user) without an operational role is rejected."""
        meter, _ = self._meter_and_customer('GLOBAL-NON-OPERATIONAL')
        global_non_op_user = self.env['res.users'].create({
            'name': 'مستخدم بنطاق شامل بدون دور عمليات',
            'login': 'ops_global_non_op_user',
            'email': 'ops_global_non_op@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_auditor').id,
            ])],
            'scope_mode': 'global',
        })
        self.assertTrue(global_non_op_user._is_global_utility_scope())
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_number': meter.meter_number}, user=global_non_op_user)):
            result = controller.meter_lookup(meter_number=meter.meter_number)
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'FORBIDDEN')
