import base64

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo import fields
from datetime import timedelta


class TestUtilityReadingReview(TransactionCase):

    def setUp(self):
        super().setUp()
        self._reading_counter = 0
        self.ReadingReviewService = self.env['utility.reading.review.service']
        self.Reading = self.env['utility.reading']
        self.Customer = self.env['utility.customer']
        self.Partner = self.env['res.partner']
        self.Category = self.env['utility.subscriber.category']
        self.Subscriber = self.env['utility.subscriber']
        self.Meter = self.env['utility.meter']
        self.Region = self.env['utility.region']
        self.DateRange = self.env['date.range']
        self.Replacement = self.env['utility.meter.replacement']

        self.test_region = self.Region.create({
            'name': 'منطقة اختبار المراجعة',
            'code': 'REV-REG-01',
            'type': 'region',
        })
        self.test_area = self.Region.create({
            'name': 'فرع اختبار المراجعة',
            'code': 'REV-AREA-01',
            'type': 'area',
            'parent_id': self.test_region.id,
        })

        self.test_category = self.Category.create({
            'name': 'فئة اختبار المراجعة',
            'code': 'REV-CAT-01',
        })
        self.test_subscriber = self.Subscriber.create({
            'name': 'نوع اختبار المراجعة',
            'code': 'REV-SUB-01',
            'category_id': self.test_category.id,
        })
        self.test_partner = self.Partner.create({
            'name': 'مالك حساب اختبار المراجعة',
            'region_id': self.test_region.id,
        })
        self.test_customer = self.Customer.create({
            'customer_number': 'CUST-REV-100',
            'partner_id': self.test_partner.id,
            'category_id': self.test_category.id,
            'subscriber_id': self.test_subscriber.id,
        })

        self.test_meter = self.Meter.create({
            'meter_number': 'MTR-REV-500',
            'customer_id': self.test_customer.id,
            'multiplier': 1.0,
        })

        range_type = self.env['date.range.type'].search([], limit=1)
        if not range_type:
            range_type = self.env['date.range.type'].create({'name': 'شهري', 'work_type': 'readings'})

        self.test_period = self.DateRange.create({
            'name': 'فترة مراجعة القراءات 2099-08',
            'type_id': range_type.id,
            'date_start': '2099-08-01',
            'date_end': '2099-08-31',
            'state': 'open',
            'period_role': 'reading',
        })

    def _reading_now(self):
        self._reading_counter += 1
        return fields.Datetime.now() + timedelta(seconds=self._reading_counter)

    def _create_unique_customer_meter(self, suffix):
        """Create a unique customer + meter pair for constraint-free periodic readings."""
        customer = self.Customer.create({
            'customer_number': f'CUST-REV-{suffix}',
            'partner_id': self.Partner.create({
                'name': f'مالك اختبار {suffix}',
                'region_id': self.test_region.id,
            }).id,
            'category_id': self.test_category.id,
            'subscriber_id': self.test_subscriber.id,
        })
        meter = self.Meter.create({
            'meter_number': f'MTR-REV-{suffix}',
            'customer_id': customer.id,
            'multiplier': 1.0,
        })
        return customer, meter

    def _create_customer_for_region(self, suffix, region):
        return self.Customer.create({
            'customer_number': f'CUST-REV-{suffix}',
            'partner_id': self.Partner.create({
                'name': f'مالك اختبار {suffix}',
                'region_id': region.id,
            }).id,
            'category_id': self.test_category.id,
            'subscriber_id': self.test_subscriber.id,
        })

    def _create_replacement_with_readings(self, suffix, closing_value=1500.0, closing_prev=1000.0):
        """Create a replacement pair (closing + opening) with proper replacement_id."""
        customer, meter_old = self._create_unique_customer_meter(f'RPL-{suffix}')
        meter_new = self.Meter.create({
            'meter_number': f'MTR-RPL-{suffix}-NEW',
            'customer_id': customer.id,
            'multiplier': 1.0,
        })
        replacement = self.Replacement.create({
            'utility_account_id': customer.id,
            'target_type': 'subscriber',
            'old_meter_id': meter_old.id,
            'old_meter_number': meter_old.meter_number,
            'old_closing_reading': closing_value,
            'old_last_invo_reading': closing_prev,
            'new_meter_id': meter_new.id,
            'new_meter_number': meter_new.meter_number,
            'new_opening_reading': 0.0,
            'new_meter_val': 1.0,
            'reason': 'fault',
        })
        self.Reading.create({
            'meter_id': meter_old.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': closing_prev,
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'reading_event': 'replacement',
            'is_initial_reading': True,
            'state': 'approved',
        })
        closing = self.Reading.create({
            'meter_id': meter_old.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': closing_value,
            'previous_reading': closing_prev,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'replacement_closing',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'approved',
        })
        opening = self.Reading.create({
            'meter_id': meter_new.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 0.0,
            'previous_reading': 0.0,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'approved',
            'is_initial_reading': True,
        })
        replacement.write({'closing_reading_id': closing.id, 'opening_reading_id': opening.id})
        return customer, meter_old, meter_new, replacement, closing, opening

    def test_01_get_review_queue_pagination(self):
        """1. Pagination: 45 unique accounts + meters → page 1 = 40, page 2 = 5."""
        readings_vals = []
        for i in range(45):
            customer, meter = self._create_unique_customer_meter(f'PG-{i:03d}')
            readings_vals.append({
                'meter_id': meter.id,
                'account_id': customer.id,
                'reading_date': self._reading_now(),
                'reading_value': 1000 + (i * 10),
                'state': 'under_review',
                'date_range_id': self.test_period.id,
            })
        self.Reading.create(readings_vals)

        res_p1 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='under_review', offset=0, limit=40)
        self.assertEqual(res_p1['pagination']['page_size'], 40)
        self.assertEqual(len(res_p1['items']), 40)
        self.assertGreaterEqual(res_p1['pagination']['total'], 45)
        self.assertEqual(res_p1['pagination']['pages'], 2)

        res_p2 = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='under_review', offset=40, limit=40, include_stats=False)
        self.assertEqual(len(res_p2['items']), 5)
        self.assertEqual(res_p2['pagination']['page'], 2)
        self.assertEqual(res_p2['stats'], {})

    def test_01b_get_review_queue_includes_stats_and_clamps_limit(self):
        """1b. Queue stats are returned on demand and limit is clamped to 40."""
        approved_customer, approved_meter = self._create_unique_customer_meter('STAT-APP')
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 2100,
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        approved = self.Reading.create({
            'meter_id': approved_meter.id,
            'account_id': approved_customer.id,
            'reading_date': self._reading_now() + timedelta(days=1),
            'reading_value': 2200,
            'state': 'approved',
            'date_range_id': self.test_period.id,
        })
        res_stats = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='all', offset=0, limit=1000, include_stats=True)
        self.assertIn('stats', res_stats)
        self.assertEqual(res_stats['pagination']['page_size'], 40)
        self.assertGreaterEqual(res_stats['stats']['pending'], 1)
        self.assertGreaterEqual(res_stats['stats']['approved'], 1)
        self.assertIn(reading.id, [item['id'] for item in res_stats['items']])
        self.assertIn(approved.id, [item['id'] for item in self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='all', offset=0, limit=40, include_stats=True)['items']])

    def test_02_action_approve_review(self):
        """2. Approve a reading via Review Service; bill generated immediately."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 2500,
            'image_state': 'clear',
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_approve_review([reading.id])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.state, 'billed')
        self.assertEqual(reading.reviewer_id, self.env.user)
        self.assertTrue(reading.review_date)
        self.assertTrue(reading.included_sale_order_id)

    def test_03_action_reject_review(self):
        """3. Reject a reading via Review Service."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 3000,
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_reject_review(
            [reading.id], rejection_reason='الصورة غير واضحة', review_notes='يرجى إعادة التصوير')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.state, 'draft')
        self.assertEqual(reading.rejection_reason, 'الصورة غير واضحة')
        self.assertEqual(reading.review_notes, 'يرجى إعادة التصوير')

    def test_04_action_bulk_approve_safe(self):
        """4. Bulk approve: only clear-image readings approved, not_clear excluded.
        Uses different accounts to avoid the unique billable reading constraint."""
        cust1, meter1 = self._create_unique_customer_meter('BLK-01')
        cust2, meter2 = self._create_unique_customer_meter('BLK-02')
        r1 = self.Reading.create({
            'meter_id': meter1.id, 'account_id': cust1.id,
            'reading_date': self._reading_now(), 'reading_value': 4000,
            'state': 'under_review', 'image_state': 'clear',
            'date_range_id': self.test_period.id,
        })
        r2 = self.Reading.create({
            'meter_id': meter2.id, 'account_id': cust2.id,
            'reading_date': self._reading_now(), 'reading_value': 4100,
            'state': 'under_review', 'image_state': 'not_clear',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.action_bulk_approve_safe([r1.id, r2.id])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(r1.state, 'billed')
        self.assertEqual(r2.state, 'under_review')

    def test_05_reading_semantics_and_is_billable(self):
        """5. is_billable: only periodic customer/private-transformer readings are billable."""
        r_cust = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 5000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'date_range_id': self.test_period.id,
        })
        self.assertTrue(r_cust.is_billable)

        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'installation',
        })
        self.assertFalse(r_open.is_billable)

        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام شبكي', 'code': 'TR-PUB-01', 'is_private': False,
            'region_id': self.test_region.id, 'area_id': self.test_area.id,
        })
        meter_trans = self.Meter.create({
            'meter_number': 'MTR-TR-01', 'linked_transformer_id': trans_pub.id,
        })
        r_trans = self.Reading.create({
            'meter_id': meter_trans.id, 'transformer_id': trans_pub.id,
            'reading_date': self._reading_now(), 'reading_value': 12000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'date_range_id': self.test_period.id,
        })
        self.assertFalse(r_trans.is_billable)

    def test_05b_billing_queue_excludes_non_billable_periodic_readings(self):
        """The queue must never contain public-transformer periodic readings."""
        transformer = self.env['utility.transformer'].create({
            'name': 'محول عام لاختبار الطابور',
            'code': 'TR-QUEUE-NB',
            'is_private': False,
            'region_id': self.test_region.id, 'area_id': self.test_area.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-QUEUE-NB',
            'linked_transformer_id': transformer.id,
        })
        reading = self.Reading.create({
            'meter_id': meter.id,
            'transformer_id': transformer.id,
            'reading_date': self._reading_now(),
            'reading_value': 12000,
            'reading_category': 'transformer',
            'reading_purpose': 'periodic',
            'date_range_id': self.test_period.id,
            'state': 'approved',
        })
        self.assertFalse(reading.is_billable)
        self.Reading.cron_queue_approved_readings()
        self.assertEqual(reading.state, 'approved')

    def test_06_context_aware_vee_opening_zero_not_exception(self):
        """6. Opening + zero consumption → no ZERO_CONSUMPTION VEE flag."""
        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement', 'state': 'under_review',
        })
        vee_flags = self.ReadingReviewService._build_context_aware_vee_flags(r_open)
        zero_flags = [f for f in vee_flags if f['code'] == 'ZERO_CONSUMPTION']
        self.assertEqual(len(zero_flags), 0)

    def test_07_replacement_pair_review(self):
        """7. Approve a replacement pair: closing + opening under_review → approved, replacement → done."""
        customer, meter_old, meter_new, replacement, _, _ = self._create_replacement_with_readings('RP-07')
        closing = self.Reading.create({
            'meter_id': meter_old.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 1500.0,
            'previous_reading': 1000.0,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'replacement_closing',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'under_review',
        })
        opening = self.Reading.create({
            'meter_id': meter_new.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 0.0,
            'previous_reading': 0.0,
            'meter_multiplier': 1.0,
            'reading_category': 'customer',
            'reading_purpose': 'opening',
            'reading_event': 'replacement',
            'replacement_id': replacement.id,
            'state': 'under_review',
        })
        replacement.write({
            'closing_reading_id': closing.id,
            'opening_reading_id': opening.id,
        })
        res = self.ReadingReviewService.action_approve_replacement_pair(replacement.id)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(closing.state, 'approved')
        self.assertEqual(opening.state, 'approved')
        self.assertEqual(replacement.state, 'done')

    def test_08_network_readings_in_review_queue(self):
        """8. Non-billable network reading visible in Network review queue."""
        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام شبكي 2', 'code': 'TR-PUB-02', 'is_private': False,
            'region_id': self.test_region.id, 'area_id': self.test_area.id,
        })
        meter_net = self.Meter.create({
            'meter_number': 'MTR-NET-01', 'linked_transformer_id': trans_pub.id,
        })
        r_net = self.Reading.create({
            'meter_id': meter_net.id, 'transformer_id': trans_pub.id,
            'reading_date': self._reading_now(), 'reading_value': 12000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        self.assertFalse(r_net.is_billable)
        res = self.ReadingReviewService.get_review_queue(
            review_tab='network', status='under_review')
        ids_in_queue = [item['id'] for item in res['items']]
        self.assertIn(r_net.id, ids_in_queue)

    def test_08c_network_region_filter_matches_meter_region_when_account_missing(self):
        """8c. Network region filter should match meter region when account_id is absent."""
        network_region = self.Region.create({
            'name': 'منطقة شبكة',
            'code': 'NET-REG-01',
            'type': 'region',
        })
        feeder = self.env['utility.feeder'].create({
            'name': 'فيدر شبكة',
            'code': 'FEED-NET-01',
            'region_id': network_region.id,
        })
        meter_net = self.Meter.create({
            'meter_number': 'MTR-NET-REG-01',
            'connection_type': 'feeder',
            'linked_feeder_id': feeder.id,
        })
        self.assertEqual(meter_net.region_id.id, network_region.id)
        reading = self.Reading.create({
            'meter_id': meter_net.id,
            'feeder_id': feeder.id,
            'reading_date': self._reading_now(),
            'reading_value': 12000,
            'reading_category': 'feeder',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.get_review_queue(
            region_id=network_region.id, review_tab='network', status='under_review')
        self.assertIn(reading.id, [item['id'] for item in res['items']])

    def test_08b_status_does_not_zero_other_stats(self):
        """8b. Status filter on queue does not wipe unrelated stats counts."""
        approved_customer, approved_meter = self._create_unique_customer_meter('STAT-APP-2')
        reading_under_review = self.Reading.create({
            'meter_id': self.test_meter.id,
            'account_id': self.test_customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 2600,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        reading_approved = self.Reading.create({
            'meter_id': approved_meter.id,
            'account_id': approved_customer.id,
            'reading_date': self._reading_now() + timedelta(days=1),
            'reading_value': 2700,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'state': 'approved',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.get_review_queue(
            period_id=self.test_period.id, status='under_review', include_stats=True)
        self.assertGreaterEqual(res['stats']['pending'], 1)
        self.assertGreaterEqual(res['stats']['approved'], 1)
        self.assertIn(reading_under_review.id, [item['id'] for item in res['items']])
        self.assertNotIn(reading_approved.id, [item['id'] for item in res['items']])

    def test_08d_replacement_scope_supports_subscriber_and_network_regions(self):
        """8d. Replacement scope honors assigned regions for available targets."""
        region_a = self.Region.create({
            'name': 'منطقة استبدال A',
            'code': 'REP-A',
            'type': 'region',
        })
        region_b = self.Region.create({
            'name': 'منطقة استبدال B',
            'code': 'REP-B',
            'type': 'region',
        })
        area_a = self.Region.create({
            'name': 'فرع استبدال A',
            'code': 'REP-AREA-A',
            'type': 'area',
            'parent_id': region_a.id,
        })
        area_b = self.Region.create({
            'name': 'فرع استبدال B',
            'code': 'REP-AREA-B',
            'type': 'area',
            'parent_id': region_b.id,
        })
        customer_a = self._create_customer_for_region('REP-A', region_a)
        customer_b = self._create_customer_for_region('REP-B', region_b)
        feeder_a = self.env['utility.feeder'].create({
            'name': 'فيدر استبدال A',
            'code': 'FEED-REP-A',
            'region_id': region_a.id,
        })
        feeder_b = self.env['utility.feeder'].create({
            'name': 'فيدر استبدال B',
            'code': 'FEED-REP-B',
            'region_id': region_b.id,
        })
        transformer_a = self.env['utility.transformer'].create({
            'name': 'محول استبدال A',
            'code': 'TR-REP-A',
            'region_id': region_a.id,
            'area_id': area_a.id,
        })
        transformer_b = self.env['utility.transformer'].create({
            'name': 'محول استبدال B',
            'code': 'TR-REP-B',
            'region_id': region_b.id,
            'area_id': area_b.id,
        })
        self.Replacement.create([
            {
                'utility_account_id': customer_a.id,
                'target_type': 'subscriber',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
            {
                'feeder_id': feeder_a.id,
                'target_type': 'feeder',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
            {
                'transformer_id': transformer_a.id,
                'target_type': 'transformer',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
            {
                'utility_account_id': customer_b.id,
                'target_type': 'subscriber',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
            {
                'feeder_id': feeder_b.id,
                'target_type': 'feeder',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
            {
                'transformer_id': transformer_b.id,
                'target_type': 'transformer',
                'old_closing_reading': 10.0,
                'old_last_invo_reading': 0.0,
                'new_opening_reading': 0.0,
                'new_meter_val': 1.0,
                'reason': 'fault',
            },
        ])
        scoped_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'مراجع استبدال مقيد A',
            'login': 'replacement.scope.08d@example.com',
            'email': 'replacement.scope.08d@example.com',
            'groups_id': [(6, 0, [self.env.ref('utility_core.group_utility_auditor').id])],
            'assigned_region_ids': [(6, 0, [region_a.id])],
        })
        res = self.ReadingReviewService.with_user(scoped_user).get_review_queue(
            review_tab='replacements', include_stats=False)
        visible_names = [item['name'] for item in res['items']]
        self.assertTrue(any('مالك اختبار REP-A' in name for name in visible_names))
        self.assertIn('استبدال عداد فيدر: فيدر استبدال A', visible_names)
        self.assertFalse(any('مالك اختبار REP-B' in name for name in visible_names))
        self.assertNotIn('استبدال عداد فيدر: فيدر استبدال B', visible_names)

    def test_09_dto_has_reading_context_fields(self):
        """9. DTO has reading context fields, NOT billing_behavior."""
        reading = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 2500,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'under_review',
            'date_range_id': self.test_period.id,
        })
        res = self.ReadingReviewService.get_review_queue(
            review_tab='commercial', status='under_review')
        item = next((i for i in res['items'] if i['id'] == reading.id), None)
        self.assertIsNotNone(item)
        self.assertIn('reading_purpose', item)
        self.assertIn('reading_event', item)
        self.assertIn('reading_purpose_label', item)
        self.assertIn('reading_event_label', item)
        self.assertIn('is_billable', item)
        self.assertNotIn('billing_behavior', item)

    def test_10_action_submit_review_routes_to_under_review(self):
        """10. action_submit_review routes ALL readings to under_review."""
        r_cust = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 3000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'state': 'draft',
            'meter_image': base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
            ),
            'date_range_id': self.test_period.id,
        })
        r_cust.action_submit_review()
        self.assertEqual(r_cust.state, 'under_review')

        trans_pub = self.env['utility.transformer'].create({
            'name': 'محول عام 4', 'code': 'TR-PUB-04', 'is_private': False,
            'region_id': self.test_region.id, 'area_id': self.test_area.id,
        })
        meter_net = self.Meter.create({
            'meter_number': 'MTR-NET-03', 'linked_transformer_id': trans_pub.id,
        })
        r_net = self.Reading.create({
            'meter_id': meter_net.id, 'transformer_id': trans_pub.id,
            'reading_date': self._reading_now(), 'reading_value': 8000,
            'reading_category': 'transformer', 'reading_purpose': 'periodic',
            'state': 'draft', 'date_range_id': self.test_period.id,
        })
        r_net.action_submit_review()
        self.assertEqual(r_net.state, 'under_review')

    def test_11_opening_not_in_exceptions_queue(self):
        """11. Opening reading: consumption_alert='normal' → NOT in Exceptions queue.
        Note: opening readings cannot have date_range_id (constraint)."""
        customer_exc, meter_exc = self._create_unique_customer_meter('EXC-01')
        r_open = self.Reading.create({
            'meter_id': meter_exc.id, 'account_id': customer_exc.id,
            'reading_date': self._reading_now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement', 'state': 'under_review',
        })
        # Model-level: consumption_alert must be 'normal'
        self.assertEqual(r_open.consumption_alert, 'normal')

        # Exceptions queue must NOT include this opening reading
        res_exc = self.ReadingReviewService.get_review_queue(
            review_tab='exceptions', status='all')
        exc_ids = [item['id'] for item in res_exc['items']]
        self.assertNotIn(r_open.id, exc_ids)

    def test_11b_replacement_queue_scope_respects_assigned_regions(self):
        """11b. Replacement queue should honor the user's assigned_region_ids scope."""
        other_region = self.Region.create({
            'name': 'منطقة مراجعة أخرى',
            'code': 'REV-REG-02',
            'type': 'region',
        })
        other_customer = self._create_customer_for_region('REV-OTHER', other_region)
        old_meter = self.Meter.create({
            'meter_number': 'MTR-REP-OTHER-OLD',
            'customer_id': other_customer.id,
            'multiplier': 1.0,
        })
        new_meter = self.Meter.create({
            'meter_number': 'MTR-REP-OTHER-NEW',
            'customer_id': other_customer.id,
            'multiplier': 1.0,
        })
        replacement = self.Replacement.create({
            'utility_account_id': other_customer.id,
            'target_type': 'subscriber',
            'old_meter_id': old_meter.id,
            'old_meter_number': old_meter.meter_number,
            'old_closing_reading': 10.0,
            'old_last_invo_reading': 0.0,
            'new_meter_id': new_meter.id,
            'new_meter_number': new_meter.meter_number,
            'new_opening_reading': 0.0,
            'new_meter_val': 1.0,
            'reason': 'fault',
        })
        scoped_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'مراجع استبدال مقيد',
            'login': 'replacement.scope.11b@example.com',
            'email': 'replacement.scope.11b@example.com',
            'groups_id': [(6, 0, [self.env.ref('utility_core.group_utility_auditor').id])],
            'assigned_region_ids': [(6, 0, [self.test_region.id])],
        })
        res = self.ReadingReviewService.with_user(scoped_user).get_review_queue(
            review_tab='replacements', include_stats=False)
        self.assertNotIn(replacement.id, [item['id'] for item in res['items']])

    def test_12_billing_regression_periodic_only(self):
        """12. Billing regression: periodic only → total = periodic consumption."""
        customer_b, meter_b = self._create_unique_customer_meter('REG-01')
        self.Reading.create({
            'meter_id': meter_b.id, 'account_id': customer_b.id,
            'reading_date': self._reading_now(), 'reading_value': 1000.0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement', 'is_initial_reading': True,
            'state': 'approved',
        })
        r_periodic = self.Reading.create({
            'meter_id': meter_b.id, 'account_id': customer_b.id,
            'reading_date': self._reading_now(), 'reading_value': 1100.0,
            'previous_reading': 1000.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })
        self.assertEqual(r_periodic.consumption, 100.0)

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 0)
        total = r_periodic.consumption + sum(closings.mapped('consumption'))
        self.assertEqual(total, 100.0)

    def test_13_billing_regression_single_replacement(self):
        """13. Billing regression: closing(300) + periodic(100) = 400.
        Tests _get_unbilled_closing_components + _prepare_component_vals."""
        _, meter_old, meter_new, _, r_closing, _ = self._create_replacement_with_readings('REG-02', 1300.0, 1000.0)
        customer_b = r_closing.account_id

        r_periodic = self.Reading.create({
            'meter_id': meter_new.id, 'account_id': customer_b.id,
            'reading_date': self._reading_now(), 'reading_value': 100.0,
            'previous_reading': 20.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 1)
        self.assertEqual(closings.id, r_closing.id)

        total = r_periodic.consumption + sum(closings.mapped('consumption'))
        self.assertEqual(total, 400.0)

        # Test _prepare_component_vals produces correct snapshots
        fake_order = type('FakeOrder', (), {'id': 999999})()
        all_readings = closings | r_periodic
        vals_list = r_periodic._prepare_component_vals(fake_order, all_readings)
        self.assertEqual(len(vals_list), 2)
        # Each component has correct fields
        for v in vals_list:
            self.assertIn('sale_order_id', v)
            self.assertIn('reading_id', v)
            self.assertIn('consumption', v)
            self.assertIn('previous_reading', v)
            self.assertIn('current_reading', v)
            self.assertEqual(v['sale_order_id'], 999999)

    def test_14_billing_regression_multiple_replacements(self):
        """14. Billing regression: A(300) + B(150) + C(100) = 550, 3 segments.
        All closings must belong to the same account as the periodic reading."""
        # Create one shared account with 3 meters
        shared_customer = self._create_customer_for_region('MULTI-REG-03', self.test_region)
        meter_a = self.Meter.create({
            'meter_number': 'MTR-MULTI-REG-03A', 'customer_id': shared_customer.id, 'multiplier': 1.0,
        })
        meter_b = self.Meter.create({
            'meter_number': 'MTR-MULTI-REG-03B', 'customer_id': shared_customer.id, 'multiplier': 1.0,
        })
        meter_c = self.Meter.create({
            'meter_number': 'MTR-MULTI-REG-03C', 'customer_id': shared_customer.id, 'multiplier': 1.0,
        })

        self.Reading.create([
            {
                'meter_id': meter_a.id, 'account_id': shared_customer.id,
                'reading_date': self._reading_now(), 'reading_value': 1000.0,
                'reading_category': 'customer', 'reading_purpose': 'opening',
                'reading_event': 'replacement', 'is_initial_reading': True,
                'state': 'approved',
            },
            {
                'meter_id': meter_b.id, 'account_id': shared_customer.id,
                'reading_date': self._reading_now(), 'reading_value': 20.0,
                'reading_category': 'customer', 'reading_purpose': 'opening',
                'reading_event': 'replacement', 'is_initial_reading': True,
                'state': 'approved',
            },
        ])

        # Create 2 replacement closings under the same account
        repl_a = self.Replacement.create({
            'utility_account_id': shared_customer.id, 'target_type': 'subscriber',
            'old_meter_id': meter_a.id, 'old_meter_number': meter_a.meter_number,
            'old_closing_reading': 1300.0, 'old_last_invo_reading': 1000.0,
            'new_meter_id': meter_b.id, 'new_meter_number': meter_b.meter_number,
            'new_opening_reading': 0.0, 'new_meter_val': 1.0, 'reason': 'fault',
        })
        self.Reading.create({
            'meter_id': meter_a.id, 'account_id': shared_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 1300.0,
            'previous_reading': 1000.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'replacement_closing',
            'reading_event': 'replacement', 'replacement_id': repl_a.id,
            'state': 'approved',
        })
        repl_b = self.Replacement.create({
            'utility_account_id': shared_customer.id, 'target_type': 'subscriber',
            'old_meter_id': meter_b.id, 'old_meter_number': meter_b.meter_number,
            'old_closing_reading': 170.0, 'old_last_invo_reading': 20.0,
            'new_meter_id': meter_c.id, 'new_meter_number': meter_c.meter_number,
            'new_opening_reading': 0.0, 'new_meter_val': 1.0, 'reason': 'fault',
        })
        self.Reading.create({
            'meter_id': meter_b.id, 'account_id': shared_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 170.0,
            'previous_reading': 20.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'replacement_closing',
            'reading_event': 'replacement', 'replacement_id': repl_b.id,
            'state': 'approved',
        })

        # Periodic reading on the 3rd meter, same account
        r_periodic = self.Reading.create({
            'meter_id': meter_c.id, 'account_id': shared_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 100.0,
            'previous_reading': 5.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 2)
        total = r_periodic.consumption + sum(closings.mapped('consumption'))
        self.assertEqual(total, 550.0)

        # Test _prepare_component_vals with all 3 segments
        fake_order = type('FakeOrder', (), {'id': 888888})()
        all_readings = closings | r_periodic
        vals_list = r_periodic._prepare_component_vals(fake_order, all_readings)
        self.assertEqual(len(vals_list), 3)
        for v in vals_list:
            self.assertIn('sale_order_id', v)
            self.assertIn('reading_id', v)
            self.assertIn('consumption', v)
            self.assertIn('meter_multiplier', v)
            self.assertEqual(v['sale_order_id'], 888888)

    def test_15_is_billable_only_periodic(self):
        """15. is_billable: periodic=True, replacement_closing=False, opening=False, closing=False."""
        r_periodic = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 5000,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'date_range_id': self.test_period.id,
        })
        self.assertTrue(r_periodic.is_billable)

        # replacement_closing → False (needs replacement_id)
        _, _, _, replacement, r_close, _ = self._create_replacement_with_readings('ISC-01')
        self.assertFalse(r_close.is_billable)

        # opening → False
        r_open = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 0,
            'reading_category': 'customer', 'reading_purpose': 'opening',
            'reading_event': 'replacement',
        })
        self.assertFalse(r_open.is_billable)

        # closing (contract_closure) → False
        r_contract_close = self.Reading.create({
            'meter_id': self.test_meter.id, 'account_id': self.test_customer.id,
            'reading_date': self._reading_now(), 'reading_value': 5500,
            'reading_category': 'customer', 'reading_purpose': 'closing',
            'reading_event': 'contract_closure',
        })
        self.assertFalse(r_contract_close.is_billable)

    def test_16_context_aware_vee_replacement_closing(self):
        """16. Context-aware VEE: replacement_closing returns list, flags only NEGATIVE_CLOSING."""
        _, _, _, _, r_closing, _ = self._create_replacement_with_readings('VEE-CL')
        vee_flags = self.ReadingReviewService._build_context_aware_vee_flags(r_closing)
        self.assertIsInstance(vee_flags, list)
        # Normal closing (consumption >= 0) should have no flags
        neg_flags = [f for f in vee_flags if f['code'] == 'NEGATIVE_CLOSING']
        self.assertEqual(len(neg_flags), 0)

    def test_17_bill_component_persistence_real_order(self):
        """17. Real persistence: create sale.order + bill components, verify DB storage."""
        _, meter_old, meter_new, _, r_closing, _ = self._create_replacement_with_readings('PERS-01', 1300.0, 1000.0)
        customer = r_closing.account_id

        r_periodic = self.Reading.create({
            'meter_id': meter_new.id, 'account_id': customer.id,
            'reading_date': self._reading_now(), 'reading_value': 100.0,
            'previous_reading': 20.0, 'meter_multiplier': 1.0,
            'reading_category': 'customer', 'reading_purpose': 'periodic',
            'reading_event': 'normal', 'state': 'approved',
            'date_range_id': self.test_period.id,
        })

        order = self.env['sale.order'].create({
            'partner_id': customer.partner_id.id,
            'customer_id': customer.id,
            'meter_id': meter_new.id,
            'reading_id': r_periodic.id,
            'date_range_id': self.test_period.id,
            'date_order': self._reading_now(),
        })

        closings = r_periodic._get_unbilled_closing_components()
        self.assertEqual(len(closings), 1)
        all_readings = closings | r_periodic
        vals_list = r_periodic._prepare_component_vals(order, all_readings)
        components = self.env['utility.bill.reading.component'].create(vals_list)

        self.assertEqual(len(components), 2)
        self.assertEqual(components.mapped('sale_order_id'), order)
        self.assertTrue(all(c.account_id == customer for c in components))
        self.assertEqual(components.filtered(lambda c: c.reading_id == r_closing).consumption, 300.0)
        self.assertEqual(components.filtered(lambda c: c.reading_id == r_periodic).consumption, 100.0)

    def test_18_image_state_actions_and_approval_gate(self):
        """18. Verify image state actions and image review gate before approval."""
        customer, meter = self._create_unique_customer_meter('IMG-GATE-01')
        reading = self.Reading.create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 250.0,
            'previous_reading': 0.0,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'date_range_id': self.test_period.id,
            'state': 'under_review',
            'image_state': 'none',
        })

        # Gate: attempting to approve without clear image raises ValidationError
        with self.assertRaises(ValidationError):
            reading.action_approve()

        # Test action_mark_image_not_clear
        reading.action_mark_image_not_clear()
        self.assertEqual(reading.image_state, 'not_clear')

        # Test action_mark_image_not_same
        reading.action_mark_image_not_same()
        self.assertEqual(reading.image_state, 'not_same')

        # Test action_mark_image_loss_read
        reading.action_mark_image_loss_read()
        self.assertEqual(reading.image_state, 'loss_read')

        # Test RPC action_set_image_state
        res = self.ReadingReviewService.action_set_image_state([reading.id], 'not_same')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.image_state, 'not_same')

        res = self.ReadingReviewService.action_set_image_state([reading.id], 'loss_read')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(reading.image_state, 'loss_read')

        # Marking clear enables approval
        reading.action_mark_image_clear()
        self.assertEqual(reading.image_state, 'clear')

        # Approval succeeds now
        reading.action_approve()
        self.assertEqual(reading.state, 'billed')

    def test_19_review_queue_approved_counts_and_items(self):
        """19. get_review_queue: approved filter and stats include approved, queued, and billed readings."""
        customer, meter = self._create_unique_customer_meter('REV-STAT-01')
        reading = self.Reading.create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 400.0,
            'previous_reading': 100.0,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'date_range_id': self.test_period.id,
            'state': 'under_review',
            'image_state': 'clear',
        })

        # Initial queue check in under_review
        queue_pending = self.ReadingReviewService.get_review_queue(status='under_review')
        pending_ids = [it['id'] for it in queue_pending.get('items', [])]
        self.assertIn(reading.id, pending_ids)

        # Approve reading
        self.ReadingReviewService.action_approve_review([reading.id])

        # Approved queue check
        queue_approved = self.ReadingReviewService.get_review_queue(status='approved')
        approved_ids = [it['id'] for it in queue_approved.get('items', [])]
        self.assertIn(reading.id, approved_ids)
        self.assertGreaterEqual(queue_approved.get('stats', {}).get('approved', 0), 1)

    def test_20_network_reading_stays_approved_without_bill(self):
        """20. Network transformer/feeder reading is non-billable and remains approved without billing."""
        transformer = self.env['utility.transformer'].create({
            'name': 'محول اختبار المراجعة',
            'code': 'TR-REV-01',
            'is_private': False,
            'region_id': self.test_region.id, 'area_id': self.test_area.id,
        })
        net_meter = self.Meter.create({
            'meter_number': 'MTR-NET-TR-01',
            'linked_transformer_id': transformer.id,
        })

        net_reading = self.Reading.create({
            'meter_id': net_meter.id,
            'transformer_id': transformer.id,
            'reading_date': self._reading_now(),
            'reading_value': 12000.0,
            'previous_reading': 10000.0,
            'reading_category': 'transformer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'date_range_id': self.test_period.id,
            'state': 'under_review',
            'image_state': 'clear',
        })

        self.assertFalse(net_reading.is_billable)
        net_reading.action_approve()

        # Must remain approved, not queued or billed, and no sale order created
        self.assertEqual(net_reading.state, 'approved')
        self.assertFalse(net_reading.included_sale_order_id)

    def test_21_billable_reading_auto_generates_posted_invoice_when_template_present(self):
        """21. End-to-end: Approved billable reading auto-generates sale.order, confirms to 'sale', and posts invoice to 'posted'."""
        product = self.env['product.product'].create({
            'name': 'خدمة كهرباء اختبار الفوترة الفورية',
            'type': 'service',
            'invoice_policy': 'order',
        })
        template = self.env['utility.contract.template'].create({
            'name': 'قالب فوترة فورية عند الاعتماد',
            'code': 'TPL-REV-AUTO-BILL',
            'pricing_mode': 'flat',
            'price_per_kwh': 25.0,
            'service_charge': 150.0,
            'subscriber_category_ids': [(6, 0, [self.test_category.id])],
            'subscriber_ids': [(6, 0, [self.test_subscriber.id])],
            'scope': 'global',
        })
        self.env['utility.contract.template.line'].create({
            'template_id': template.id,
            'product_id': product.id,
            'name': 'استهلاك طاقة',
            'meter_line_type': 'consumption',
        })

        customer, meter = self._create_unique_customer_meter('AUTO-BILL-01')
        customer.write({'contract_template_id': template.id})

        self.Reading.create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_date': fields.Datetime.now() - timedelta(days=30),
            'reading_value': 200.0,
            'reading_purpose': 'opening',
            'is_initial_reading': True,
            'image_state': 'clear',
            'state': 'approved',
        })

        reading = self.Reading.create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_date': self._reading_now(),
            'reading_value': 500.0,
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'reading_event': 'normal',
            'date_range_id': self.test_period.id,
            'state': 'under_review',
            'image_state': 'clear',
        })

        self.assertTrue(reading.is_billable)
        self.assertEqual(reading.consumption, 300.0)

        # Operational supervisor approves reading -> bill generated immediately
        reading.action_approve()
        self.assertEqual(reading.state, 'billed')

        # Reading must transition to billed
        self.assertEqual(reading.state, 'billed')
        self.assertTrue(reading.is_validated)

        # Sale order must be created and confirmed
        order = reading.included_sale_order_id
        self.assertTrue(order)
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.consumption, 300.0)

        # Invoice must be created and posted
        invoices = order.invoice_ids
        self.assertTrue(invoices)
        self.assertEqual(invoices[:1].state, 'posted')
        self.assertGreater(order.amount_total, 0.0)

        # Review queue approved tab must include the reading
        approved_queue = self.ReadingReviewService.get_review_queue(status='approved')
        item_ids = [it['id'] for it in approved_queue.get('items', [])]
        self.assertIn(reading.id, item_ids)
