from odoo.tests import common
from odoo.exceptions import ValidationError

class TestTransformerLossHistoricalSnapshot(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup basic data
        cls.company = cls.env.user.company_id

        # Geography (Region -> Area) required for general transformers
        cls.loss_region = cls.env['utility.region'].create({
            'name': 'منطقة الفقد', 'code': 'LOSS-REG',
            'type': 'region', 'company_id': cls.company.id,
        })
        cls.loss_area = cls.env['utility.region'].create({
            'name': 'فرع الفقد', 'code': 'LOSS-AREA',
            'type': 'area', 'parent_id': cls.loss_region.id,
            'company_id': cls.company.id,
        })

        # Transformers
        cls.transformer_A = cls.env['utility.transformer'].create({
            'name': 'Transformer A',
            'code': 'TR-A-001',
            'region_id': cls.loss_region.id,
            'area_id': cls.loss_area.id,
        })
        cls.transformer_B = cls.env['utility.transformer'].create({
            'name': 'Transformer B',
            'code': 'TR-B-001',
            'region_id': cls.loss_region.id,
            'area_id': cls.loss_area.id,
        })

        # Customer and Meter linked to Transformer A initially
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة الاختبار',
            'code': 'CAT-LOSS-TEST',
        })
        cls.subscriber_type = cls.env['utility.subscriber'].create({
            'name': 'مشترك الاختبار',
            'code': 'SUB-LOSS-TEST',
            'category_id': cls.category.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'شريك اختبار فقد',
        })
        cls.customer = cls.env['utility.customer'].create({
            'customer_number': 'CUST-LOSS-TEST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber_type.id,
            'transformer_id': cls.transformer_A.id,
        })
        cls.meter = cls.env['utility.meter'].create({
            'meter_number': 'METER-001',
            'customer_id': cls.customer.id,
            'transformer_id': cls.transformer_A.id,  # Initial state
            'multiplier': 1.0,
        })

        # Date Range for Period 1
        cls.period_1 = cls.env['date.range'].create({
            'name': 'Period 1',
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'type_id': cls.env.ref('date_range.date_range_type_monthly').id,
        })
        
        # Date Range for Period 2
        cls.period_2 = cls.env['date.range'].create({
            'name': 'Period 2',
            'date_start': '2025-02-01',
            'date_end': '2025-02-28',
            'type_id': cls.env.ref('date_range.date_range_type_monthly').id,
        })

    def test_transformer_snapshot_historical_integrity(self):
        # 1. Create a reading for Period 1 (linked to Transformer A)
        reading_1 = self.env['utility.reading'].create({
            'meter_id': self.meter.id,
            'reading_value': 100.0,
            'reading_date': '2025-01-31',
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'date_range_id': self.period_1.id,
        })

        # 2. Check snapshot is A immediately after creation
        self.assertEqual(reading_1.transformer_snapshot_id, self.transformer_A,
                         "Snapshot must be Transformer A exactly at creation.")

        # Approve and bill Reading 1 (to populate sale_order for loss report)
        reading_1.action_approve()
        
        # 3. Change Customer (and Meter) to Transformer B
        self.customer.transformer_id = self.transformer_B.id
        self.meter.transformer_id = self.transformer_B.id

        # 4. Re-read the old reading from database and verify it still belongs to A
        reading_1_reloaded = self.env['utility.reading'].browse(reading_1.id)
        
        # The dynamic related field changes to B
        self.assertEqual(reading_1_reloaded.transformer_id, self.transformer_B,
                         "Old dynamic transformer_id should change to B (known behavior).")
        
        # The snapshot field MUST remain A
        self.assertEqual(reading_1_reloaded.transformer_snapshot_id, self.transformer_A,
                         "Historical snapshot must strictly remain Transformer A despite meter moving.")

        # 5. Create a new reading for Period 2 (now linked to Transformer B)
        reading_2 = self.env['utility.reading'].create({
            'meter_id': self.meter.id,
            'reading_value': 200.0,
            'reading_date': '2025-02-28',
            'reading_category': 'customer',
            'reading_purpose': 'periodic',
            'date_range_id': self.period_2.id,
        })

        self.assertEqual(reading_2.transformer_snapshot_id, self.transformer_B,
                         "New reading snapshot must be Transformer B since meter moved.")
        reading_2.action_approve()

        # 6. Attempt direct write on snapshot field by normal code MUST fail
        with self.assertRaises(ValidationError, msg="Must block manual update of snapshot"):
            reading_1_reloaded.write({'transformer_snapshot_id': self.transformer_B.id})

        # 7. Check Transformer Loss Report data
        # We need a Transformer Reading for A in Period 1 to generate loss report
        tr_reading_A_P1 = self.env['utility.reading'].create({
            'transformer_id': self.transformer_A.id,
            'reading_value': 150.0,
            'reading_date': '2025-01-31',
            'reading_category': 'transformer',
            'reading_purpose': 'periodic',
            'date_range_id': self.period_1.id,
        })
        tr_reading_A_P1.action_approve()

        # Query the report directly
        self.env.cr.execute("""
            SELECT energy_sold, customer_count
            FROM utility_transformer_loss_report 
            WHERE transformer_id = %s AND date_range_id = %s
        """, (self.transformer_A.id, self.period_1.id))
        
        result_A_P1 = self.env.cr.fetchone()
        
        self.assertIsNotNone(result_A_P1, "Loss report must have an entry for Transformer A in Period 1.")
        # energy_sold should be 100 (from reading 1), not moved to B
        # customer_count should be 1
        self.assertEqual(result_A_P1[0], 100.0, "Energy sold in Period 1 must remain 100 on Transformer A.")
        self.assertEqual(result_A_P1[1], 1, "Customer count in Period 1 must remain 1 on Transformer A.")

