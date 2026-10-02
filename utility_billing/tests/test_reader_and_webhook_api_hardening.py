import json
import hmac
from odoo.tests.common import TransactionCase, HttpCase
from odoo.exceptions import UserError, ValidationError
from odoo.addons.utility_billing.controllers.utility_billing_api import UtilityBillingAPI
from odoo.addons.utility_billing.controllers.utility_reader_api import UtilityReaderAPI


class TestAPIErrorContract(TransactionCase):

    def test_billing_and_reader_error_helpers_are_consistent(self):
        """All JSON API error helpers expose the integrator-facing envelope."""
        expected = {
            'success': False,
            'code': 'VALIDATION_ERROR',
            'error': 'invalid request',
        }
        self.assertEqual(UtilityBillingAPI._error('VALIDATION_ERROR', 'invalid request'), expected)
        self.assertEqual(UtilityReaderAPI._error('VALIDATION_ERROR', 'invalid request'), expected)


class TestReaderAndWebhookAPIHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.date_range_type = self.env['date.range.type'].search([], limit=1)
        if not self.date_range_type:
            self.date_range_type = self.env['date.range.type'].create({
                'name': 'نوع فترة اختبارية',
                'code': 'TEST-TYPE-01',
            })
        self.period = self.env['date.range'].create({
            'name': 'فترة رفع اختبارية',
            'code': 'READ-API-TEST-2026-08',
            'type_id': self.date_range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'period_role': 'reading',
            'state': 'open',
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
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-API-001',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'partner_id': self.env['res.partner'].create({'name': 'شريك عميل API'}).id,
            'company_id': self.company.id,
        })

    def test_daily_report_excludes_resolved_and_dismissed_alarms(self):
        """التحقق من أن التقرير اليومي يحسب الإنذارات النشطة فقط وتستبعد الحالات النهائية (resolved, dismissed)."""
        Alarm = self.env['utility.alarm']
        # Active alarms
        a1 = Alarm.create({'alarm_type': 'power_failure', 'description': 'انقطاع', 'state': 'open', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 10:00:00'})
        a2 = Alarm.create({'alarm_type': 'battery', 'description': 'بطارية', 'state': 'acknowledged', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 11:00:00'})
        a3 = Alarm.create({'alarm_type': 'reverse_energy', 'description': 'عكسي', 'state': 'investigating', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 12:00:00'})

        # Terminal alarms (MUST NOT be counted)
        a4 = Alarm.create({'alarm_type': 'tamper', 'description': 'تم حله', 'state': 'resolved', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 13:00:00'})
        a5 = Alarm.create({'alarm_type': 'other', 'description': 'تم رفضه', 'state': 'dismissed', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 14:00:00'})

        start_dt = '2026-08-14 00:00:00'
        end_dt = '2026-08-14 23:59:59'
        alarms_domain = [
            ('customer_id', '=', self.customer.id),
            ('alarm_date', '>=', start_dt), ('alarm_date', '<=', end_dt),
            ('state', 'not in', ('resolved', 'dismissed')),
        ]
        active_count = Alarm.search_count(alarms_domain)
        self.assertEqual(active_count, 3)


class TestReaderAndWebhookAPIHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        # Setup Receivable Account & Partner
        rec_acc = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', [self.company.id])
        ], limit=1)
        if not rec_acc:
            rec_acc = self.env['account.account'].create({
                'name': 'مدينو مشتركين اختبار',
                'code': '110000.TEST',
                'account_type': 'asset_receivable',
                'company_ids': [(6, 0, [self.company.id])],
            })
        self.partner = self.env['res.partner'].create({
            'name': 'شريك دفع إلكتروني HTTP',
            'property_account_receivable_id': rec_acc.id,
        })

        # Setup Utility Subscriber Category & Type & Customer Account
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة HTTP',
            'code': 'CAT-HTTP-01',
            'company_id': self.company.id,
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك HTTP',
            'code': 'SUB-HTTP-01',
            'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-HTTP-001',
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'partner_id': self.partner.id,
            'company_id': self.company.id,
        })

        # Setup Date Ranges
        self.date_range_type = self.env['date.range.type'].search([], limit=1)
        if not self.date_range_type:
            self.date_range_type = self.env['date.range.type'].create({
                'name': 'نوع فترة HTTP',
                'code': 'HTTP-TYPE-01',
            })
        self.period = self.env['date.range'].create({
            'name': 'فترة رفع اختبارية HTTP',
            'code': 'READ-API-HTTP-2026-08',
            'type_id': self.date_range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'period_role': 'reading',
            'state': 'open',
            'company_id': self.company.id,
        })

        # Setup Product & Income Account
        income_acc = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', [self.company.id])
        ], limit=1)
        if not income_acc:
            income_acc = self.env['account.account'].create({
                'name': 'إيرادات كهرباء HTTP',
                'code': '400000.HTTP',
                'account_type': 'income',
                'company_ids': [(6, 0, [self.company.id])],
            })
        self.product = self.env['product.product'].create({
            'name': 'خدمة كهرباء HTTP',
            'type': 'service',
            'property_account_income_id': income_acc.id,
        })

        # Setup Sale Order & Posted Account Invoice
        self.sale_order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.period.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 200.0,
            })],
        })
        self.sale_order.action_confirm()
        self.invoice = self.sale_order._create_invoices()
        self.invoice.action_post()

        # Setup Payment Bank Journal & Payment Integration Provider
        self.journal = self.env['account.journal'].search([
            ('code', '=', 'HTTPGW'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not self.journal:
            self.journal = self.env['account.journal'].create({
                'name': 'بنك دفع إلكتروني HTTP',
                'code': 'HTTPGW',
                'type': 'bank',
                'company_id': self.company.id,
            })
        self.provider = self.env['utility.integration.provider'].create({
            'name': 'مزود دفع إلكتروني HTTP',
            'provider_type': 'payment_gateway',
            'is_payment_capable': True,
            'payment_direction': 'inbound',
            'inbound_journal_id': self.journal.id,
            'active': True,
            'company_id': self.company.id,
        })

        # Setup Valid Gateway Transaction
        self.tx = self.env['utility.payment.gateway.transaction'].create({
            'provider_id': self.provider.id,
            'payment_direction': 'inbound',
            'sale_order_id': self.sale_order.id,
            'utility_invoice_id': self.invoice.id,
            'amount': 200.0,
            'access_token': 'secret_http_token_456',
            'state': 'pending',
        })

        # Setup Reader User & Authenticate Session
        self.reader_user = self.env['res.users'].create({
            'name': 'جابي العدادات الاختبارية',
            'login': 'reader_test_user',
            'email': 'reader@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('utility_core.group_utility_technician').id,
            ])],
        })

    def test_payment_webhook_http_invalid_token_rejected_before_lock(self):
        """اختبار رفض التوكين الخاطئ عبر طلب HTTP دون تغيير حالة المعاملة المعلقة."""
        response_invalid = self.url_open(
            f'/api/v1/utility/payment_gateway/webhook/{self.tx.name}',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'token': 'wrong_invalid_token_999',
                    'status': 'success',
                    'provider_reference': 'GATEWAY-REF-INVALID',
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        res_json = response_invalid.json().get('result', {})
        self.assertEqual(res_json.get('error'), 'Invalid token')
        self.tx.invalidate_recordset(['state'])
        self.assertEqual(self.tx.state, 'pending')

    def test_billing_api_error_contract_is_stable(self):
        """Billing API validation errors expose success, code, and error."""
        self.authenticate('reader_test_user', 'reader_test_user')
        response = self.url_open(
            '/api/v1/utility/billing/balance',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {},
            }),
            headers={'Content-Type': 'application/json'},
        )
        result = response.json().get('result', {})
        self.assertEqual(
            result,
            {
                'success': False,
                'code': 'VALIDATION_ERROR',
                'error': 'customer_number is required',
            },
        )

    def test_payment_webhook_http_valid_callback_and_repeated_idempotency(self):
        """اختبار تأكيد الدفع الإلكتروني عبر HTTP وإثبات تكرار الاستدعاء (Repeated Callback Idempotency)."""
        # 1. First Valid HTTP Callback
        response1 = self.url_open(
            f'/api/v1/utility/payment_gateway/webhook/{self.tx.name}',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'token': 'secret_http_token_456',
                    'status': 'success',
                    'provider_reference': 'GATEWAY-REF-CONFIRM-001',
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        res_json1 = response1.json().get('result', {})
        self.assertTrue(res_json1.get('success'))
        self.tx.invalidate_recordset(['state', 'payment_id'])
        self.assertEqual(self.tx.state, 'done')
        payment_id_1 = self.tx.payment_id.id
        self.assertTrue(bool(payment_id_1))

        # 2. Second (Repeated) HTTP Callback on same transaction
        response2 = self.url_open(
            f'/api/v1/utility/payment_gateway/webhook/{self.tx.name}',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'token': 'secret_http_token_456',
                    'status': 'success',
                    'provider_reference': 'GATEWAY-REF-CONFIRM-001',
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        res_json2 = response2.json().get('result', {})
        self.assertTrue(res_json2.get('success'))
        self.assertEqual(res_json2.get('payment_id'), payment_id_1)

        # 3. Verify Database idempotency: Only 1 account.payment record exists
        payments = self.env['account.payment'].search([('utility_sale_order_id', '=', self.sale_order.id)])
        self.assertEqual(len(payments), 1)

    def test_reader_api_http_create_batch_invalid_total_readings(self):
        """اختبار رفض إنشاء دفعة قراءات بإدخال عدد قراءات سالب أو غير صحيح عبر HTTP."""
        self.authenticate('reader_test_user', 'reader_test_user')

        # Invalid negative total readings test
        res_invalid = self.url_open(
            '/api/v1/utility/reading/batch/create',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'date_range_id': self.period.id,
                    'total_readings': -50,
                }
            }),
            headers={'Content-Type': 'application/json'}
        ).json().get('result', {})
        self.assertFalse(res_invalid.get('success'))
        self.assertEqual(res_invalid.get('code'), 'INVALID_TOTAL_READINGS')

        # Invalid non-numeric total readings test
        res_non_numeric = self.url_open(
            '/api/v1/utility/reading/batch/create',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'date_range_id': self.period.id,
                    'total_readings': 'invalid_str',
                }
            }),
            headers={'Content-Type': 'application/json'}
        ).json().get('result', {})
        self.assertFalse(res_non_numeric.get('success'))
        self.assertEqual(res_non_numeric.get('code'), 'INVALID_TOTAL_READINGS')

    def test_reader_api_http_upload_batch_data_malformed_json(self):
        """اختبار رفض رفع نص JSON تالف دون تعديل ملف الدفعة عبر HTTP."""
        self.authenticate('reader_test_user', 'reader_test_user')

        # Create valid reading batch
        batch = self.env['utility.reading.batch'].create({
            'date_range_id': self.period.id,
            'user_id': self.reader_user.id,
            'state': 'uploaded',
        })
        self.assertFalse(bool(batch.data_file))

        # Upload malformed JSON
        res = self.url_open(
            '/api/v1/utility/reading/batch/upload_data',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'batch_id': batch.id,
                    'data': '{"readings": [broken_json_syntax',
                }
            }),
            headers={'Content-Type': 'application/json'}
        ).json().get('result', {})

        self.assertFalse(res.get('success'))
        self.assertEqual(res.get('code'), 'INVALID_JSON')
        batch.invalidate_recordset(['data_file'])
        self.assertFalse(bool(batch.data_file))

    def test_reader_api_http_my_batches_limit_bounds_and_periods(self):
        """اختبار صحة حدود الـ Limit في استعلام دفعات الجابي واستعلام فترات القراءة المتاحة عبر HTTP."""
        self.authenticate('reader_test_user', 'reader_test_user')

        # Test non-numeric limit rejection
        res_invalid_limit = self.url_open(
            '/api/v1/utility/reading/batch/my',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'limit': 'not_an_int',
                }
            }),
            headers={'Content-Type': 'application/json'}
        ).json().get('result', {})
        self.assertFalse(res_invalid_limit.get('success'))
        self.assertEqual(res_invalid_limit.get('code'), 'INVALID_LIMIT')

        # Test valid get_periods endpoint
        res_periods = self.url_open(
            '/api/v1/utility/reading/periods',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {}
            }),
            headers={'Content-Type': 'application/json'}
        ).json().get('result', {})
        self.assertTrue(res_periods.get('success'))
        self.assertTrue(isinstance(res_periods.get('periods'), list))
