from datetime import date
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestContractTemplateVersioningAndPricingSnapshot(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Category and Subscriber
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'Residential Category',
            'code': 'RES-CAT-TEST',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'Residential Subscriber',
            'code': 'RES-SUB-TEST',
            'category_id': cls.category.id,
        })

        # Base Contract Template (Flat)
        cls.template_flat = cls.env['utility.contract.template'].create({
            'name': 'Residential Flat Tariff',
            'code': 'RES-FLAT-01',
            'pricing_mode': 'flat',
            'price_per_kwh': 150.0,
            'service_charge': 500.0,
            'subscriber_category_ids': [(6, 0, cls.category.ids)],
            'subscriber_ids': [(6, 0, cls.subscriber.ids)],
            'scope': 'global',
        })

        # Partner & Customer Account
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Citizen Customer',
        })
        cls.customer = cls.env['utility.customer'].create({
            'customer_number': 'CUST-TEST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
            'contract_template_id': cls.template_flat.id,
        })

        # Meter
        cls.meter = cls.env['utility.meter'].create({
            'meter_number': 'MTR-TEST-001',
            'customer_id': cls.customer.id,
        })

        # Date Range Period
        cls.period_type = cls.env['date.range.type'].search([], limit=1)
        if not cls.period_type:
            cls.period_type = cls.env['date.range.type'].create({
                'name': 'Monthly Billing',
                'company_id': cls.company.id,
            })
        cls.period = cls.env['date.range'].create({
            'name': 'January 2026',
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'type_id': cls.period_type.id,
            'company_id': cls.company.id,
        })

    def test_01_contract_template_initial_version_creation(self):
        """Verify automatic creation of Version 1 upon template creation."""
        template = self.template_flat
        self.assertEqual(template.version_count, 1)
        self.assertTrue(template.current_version_id)
        self.assertEqual(template.current_version_id.version_number, 1)
        self.assertEqual(template.current_version_id.price_per_kwh, 150.0)
        self.assertEqual(template.current_version_id.service_charge, 500.0)
        self.assertFalse(template.current_version_id.is_used_in_billing)

    def test_02_unbilled_template_updates_in_place(self):
        """When a template has NOT been used in billing, editing prices updates the active version in place."""
        template = self.template_flat
        v1 = template.current_version_id
        template.write({'price_per_kwh': 175.0, 'service_charge': 600.0})
        self.assertEqual(template.version_count, 1)
        self.assertEqual(template.current_version_id.id, v1.id)
        self.assertEqual(v1.price_per_kwh, 175.0)
        self.assertEqual(v1.service_charge, 600.0)

    def test_03_billed_template_creates_new_version_on_change(self):
        """When a version is used in a bill, changing the template configuration creates Version 2."""
        template = self.template_flat
        v1 = template.current_version_id

        # Create a bill using v1
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'date_range_id': self.period.id,
            'consumption': 100.0,
            'contract_template_id': template.id,
            'contract_template_version_id': v1.id,
        })
        order._calculate_amounts()

        # After _calculate_amounts, version must be marked as used in billing
        self.assertTrue(v1._is_actually_used_in_billing())
        self.assertTrue(v1.is_used_in_billing)

        # Now update the template price
        template.write({'price_per_kwh': 200.0})
        self.assertEqual(template.version_count, 2)
        v2 = template.current_version_id
        self.assertNotEqual(v1.id, v2.id)
        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v2.price_per_kwh, 200.0)
        self.assertEqual(v1.price_per_kwh, 175.0)  # V1 remains intact!

    def test_04_version_immutability_protection(self):
        """Direct writes or deletion on a used version must be blocked with UserError."""
        template = self.template_flat
        v1 = template.version_ids.sorted('version_number')[0]

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'date_range_id': self.period.id,
            'consumption': 50.0,
            'contract_template_id': template.id,
            'contract_template_version_id': v1.id,
        })
        order._calculate_amounts()

        with self.assertRaises(UserError):
            v1.write({'price_per_kwh': 999.0})

        with self.assertRaises(UserError):
            v1.unlink()

    def test_05_flat_pricing_snapshot_generation(self):
        """Verify immutable pricing snapshot and blocks for flat rate billing."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'date_range_id': self.period.id,
            'consumption': 200.0,
            'contract_template_id': self.template_flat.id,
        })
        order._calculate_amounts()

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(snapshot.billing_consumption, 200.0)
        self.assertEqual(snapshot.contract_template_version_id.id, order.contract_template_version_id.id)
        self.assertEqual(len(snapshot.block_ids), 1)
        self.assertEqual(snapshot.block_ids[0].quantity, 200.0)

    def test_06_progressive_block_pricing_snapshot_breakdown(self):
        """Verify progressive tier (block) calculations produce exact block snapshots."""
        template_block = self.env['utility.contract.template'].create({
            'name': 'Residential Progressive Tariff',
            'code': 'RES-BLOCK-01',
            'pricing_mode': 'block',
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        # Create 3 blocks: 0-100 @ 10, 100-300 @ 20, 300+ @ 30
        self.env['utility.contract.template.block'].create([
            {'template_id': template_block.id, 'sequence': 10, 'name': 'Block 1', 'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 10.0},
            {'template_id': template_block.id, 'sequence': 20, 'name': 'Block 2', 'from_kwh': 100, 'to_kwh': 300, 'price_per_kwh': 20.0},
            {'template_id': template_block.id, 'sequence': 30, 'name': 'Block 3', 'from_kwh': 300, 'to_kwh': 0, 'price_per_kwh': 30.0},
        ])

        cust_block = self.env['utility.customer'].create({
            'customer_number': 'CUST-BLOCK-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': template_block.id,
        })

        # Bill for 250 kWh: 100 kWh @ 10 = 1000, 150 kWh @ 20 = 3000 -> Total Energy = 4000
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': cust_block.id,
            'date_range_id': self.period.id,
            'consumption': 250.0,
            'contract_template_id': template_block.id,
        })
        order._calculate_amounts()

        self.assertEqual(order.amount_energy, 4000.0)

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(snapshot.amount_energy, 4000.0)
        self.assertEqual(len(snapshot.block_ids), 2)
        b1 = snapshot.block_ids.filtered(lambda b: b.block_name == 'Block 1')
        b2 = snapshot.block_ids.filtered(lambda b: b.block_name == 'Block 2')
        self.assertEqual(b1.quantity, 100.0)
        self.assertEqual(b1.price_per_kwh, 10.0)
        self.assertEqual(b1.amount, 1000.0)
        self.assertEqual(b2.quantity, 150.0)
        self.assertEqual(b2.price_per_kwh, 20.0)
        self.assertEqual(b2.amount, 3000.0)

    def test_07_single_tier_pricing_snapshot(self):
        """Verify flat tier (single tier) calculation applies one tier to entire consumption."""
        template_tier = self.env['utility.contract.template'].create({
            'name': 'Commercial Flat Tier Tariff',
            'code': 'COM-TIER-01',
            'pricing_mode': 'tier',
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        self.env['utility.contract.template.block'].create([
            {'template_id': template_tier.id, 'sequence': 10, 'name': 'Tier 1 (Low)', 'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 50.0},
            {'template_id': template_tier.id, 'sequence': 20, 'name': 'Tier 2 (High)', 'from_kwh': 100, 'to_kwh': 0, 'price_per_kwh': 40.0},
        ])

        cust_tier = self.env['utility.customer'].create({
            'customer_number': 'CUST-TIER-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': template_tier.id,
        })

        # Bill for 150 kWh -> falls into Tier 2 (all 150 @ 40 = 6000)
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': cust_tier.id,
            'date_range_id': self.period.id,
            'consumption': 150.0,
            'contract_template_id': template_tier.id,
        })
        order._calculate_amounts()

        self.assertEqual(order.amount_energy, 6000.0)
        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)
        self.assertEqual(len(snapshot.block_ids), 1)
        self.assertEqual(snapshot.block_ids[0].quantity, 150.0)
        self.assertEqual(snapshot.block_ids[0].price_per_kwh, 40.0)
        self.assertEqual(snapshot.block_ids[0].amount, 6000.0)

    def test_08_seasonal_and_tou_modes_blocked_with_validation_error(self):
        """Verify that selecting seasonal or tou pricing modes raises an explicit ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['utility.contract.template'].create({
                'name': 'Seasonal Template Test',
                'code': 'SEASONAL-01',
                'pricing_mode': 'seasonal',
                'subscriber_category_ids': [(6, 0, self.category.ids)],
                'subscriber_ids': [(6, 0, self.subscriber.ids)],
                'scope': 'global',
            })

        with self.assertRaises(ValidationError):
            self.env['utility.contract.template'].create({
                'name': 'TOU Template Test',
                'code': 'TOU-01',
                'pricing_mode': 'tou',
                'subscriber_category_ids': [(6, 0, self.category.ids)],
                'subscriber_ids': [(6, 0, self.subscriber.ids)],
                'scope': 'global',
            })

    def test_09_pricing_snapshot_immutability_on_confirmed_bill(self):
        """When a bill is confirmed, direct modifications to its pricing snapshot are blocked."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'date_range_id': self.period.id,
            'consumption': 80.0,
            'contract_template_id': self.template_flat.id,
        })
        order._calculate_amounts()
        order.action_confirm()

        snapshot = self.env['utility.bill.pricing.snapshot'].search([('sale_order_id', '=', order.id)], limit=1)
        self.assertTrue(snapshot)

        with self.assertRaises(UserError):
            snapshot.write({'amount_energy': 99999.0})

        with self.assertRaises(UserError):
            snapshot.unlink()

    def test_10_historical_repricing_consumes_frozen_version_blocks_not_live_blocks(self):
        """Repricing a historical bill uses the frozen snapshot blocks from its version, not modified template blocks."""
        template_block = self.env['utility.contract.template'].create({
            'name': 'Block Tariff for Versioning Test',
            'code': 'BLK-HIST-01',
            'pricing_mode': 'block',
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        self.env['utility.contract.template.block'].create([
            {'template_id': template_block.id, 'sequence': 10, 'name': 'V1 Block 1', 'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 10.0},
            {'template_id': template_block.id, 'sequence': 20, 'name': 'V1 Block 2', 'from_kwh': 100, 'to_kwh': 0, 'price_per_kwh': 20.0},
        ])

        # Version 1 captures blocks (0-100 @ 10, 100+ @ 20)
        v1 = template_block.current_version_id
        self.assertEqual(v1.version_number, 1)

        cust_block = self.env['utility.customer'].create({
            'customer_number': 'CUST-BLK-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': template_block.id,
        })

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': cust_block.id,
            'date_range_id': self.period.id,
            'consumption': 250.0,
            'contract_template_id': template_block.id,
        })
        order._calculate_amounts()
        self.assertEqual(order.contract_template_version_id, v1)
        self.assertEqual(order.amount_energy, 4000.0)  # 100*10 + 150*20 = 4000
        order.action_confirm()
        self.assertTrue(v1.is_used_in_billing)

        # Now update the template with completely new block prices (30.0 and 50.0) -> creates Version 2
        template_block.block_ids.unlink()
        self.env['utility.contract.template.block'].create([
            {'template_id': template_block.id, 'sequence': 10, 'name': 'V2 Block 1', 'from_kwh': 0, 'to_kwh': 100, 'price_per_kwh': 30.0},
            {'template_id': template_block.id, 'sequence': 20, 'name': 'V2 Block 2', 'from_kwh': 100, 'to_kwh': 0, 'price_per_kwh': 50.0},
        ])
        v2 = template_block.current_version_id
        self.assertEqual(v2.version_number, 2)

        # Repricing Order 1 for 200 kWh MUST use Version 1 blocks (100*10 + 100*20 = 3000), NOT live template blocks (100*30 + 100*50 = 8000)
        simulated_total = order._simulate_bill_total_for_consumption(200.0, version_id=v1.id)
        self.assertEqual(simulated_total, 3000.0, 'إعادة التسعير التاريخي يجب أن تعتمد كلياً على شرائح الإصدار الأول الثابتة.')

    def test_11_multi_component_reading_correction_recalculation(self):
        """Correcting a reading on a multi-component bill recalibrates affected segment and total consumption."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 500.0,
            'contract_template_id': self.template_flat.id,
        })
        order._calculate_amounts()

        reading1 = self.env['utility.reading'].with_context(_bypass_reading_protection=True).create({
            'meter_id': self.meter.id,
            'reading_value': 1200.0,
            'previous_reading': 1000.0,
            'reading_date': '2026-01-15 10:00:00',
            'state': 'billed',
        })
        new_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-NEW-MULTI',
            'customer_id': self.customer.id,
        })
        reading2 = self.env['utility.reading'].with_context(_bypass_reading_protection=True).create({
            'meter_id': new_meter.id,
            'reading_value': 300.0,
            'previous_reading': 0.0,
            'reading_date': '2026-01-31 10:00:00',
            'state': 'billed',
        })

        comp1 = self.env['utility.bill.reading.component'].create({
            'sale_order_id': order.id,
            'reading_id': reading1.id,
            'account_id': self.customer.id,
            'meter_id': self.meter.id,
            'period_start': '2026-01-01 00:00:00',
            'period_end': '2026-01-15 10:00:00',
            'previous_reading': 1000.0,
            'current_reading': 1200.0,
            'meter_multiplier': 1.0,
            'consumption': 200.0,
        })
        comp2 = self.env['utility.bill.reading.component'].create({
            'sale_order_id': order.id,
            'reading_id': reading2.id,
            'account_id': self.customer.id,
            'meter_id': new_meter.id,
            'period_start': '2026-01-15 10:00:00',
            'period_end': '2026-01-31 10:00:00',
            'previous_reading': 0.0,
            'current_reading': 300.0,
            'meter_multiplier': 1.0,
            'consumption': 300.0,
        })

        # Correct reading 1 from 1200 to 1150 (consumption drops from 200 to 150, total becomes 150 + 300 = 450)
        recalculated_consumption = order._calculate_corrected_consumption_for_reading(1150.0, reading_id=reading1.id)
        self.assertEqual(recalculated_consumption, 450.0, 'الاستهلاك الكلي يجب أن يعاد احتسابه بجمع المقاطع المصححة بدقة.')

    def test_12_empty_discount_blocks_in_snapshot_honored(self):
        """Verify that an explicit empty list [] for discount_blocks in snapshot does not fallback to live template discount blocks."""
        # Create template with blocks and no discount blocks
        template = self.env['utility.contract.template'].create({
            'name': 'Tiered Template Without Initial Discount',
            'code': 'TIER-NO-DISC-01',
            'pricing_mode': 'tier',
            'block_ids': [
                (0, 0, {'from_kwh': 0.0, 'to_kwh': 100.0, 'price_per_kwh': 50.0, 'sequence': 1}),
                (0, 0, {'from_kwh': 100.0, 'to_kwh': 0.0, 'price_per_kwh': 100.0, 'sequence': 2}),
            ],
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'scope': 'global',
        })
        v1 = template.current_version_id
        snapshot = v1.get_parsed_snapshot()
        self.assertEqual(snapshot.get('discount_blocks'), [])

        # Later, someone adds discount blocks to the template directly
        self.env['utility.contract.template.discount.block'].create({
            'template_id': template.id,
            'from_kwh': 0.0,
            'to_kwh': 50.0,
            'price_per_kwh': 20.0,
            'sequence': 1,
        })

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 100.0,
            'contract_template_id': template.id,
            'contract_template_version_id': v1.id,
        })

        # Calculate discount blocks using v1 - must return empty list and not the template's new discount block
        calc_d_blocks = order._get_discount_blocks_for_calculation(template, version=v1)
        self.assertEqual(calc_d_blocks, [], 'اللقطة التاريخية الفارغة يجب أن تُحترم وألا ترجع للقالب الحي.')

    def test_14_zero_local_fees_not_added_to_order_lines(self):
        """
        التحقق من أن الرسوم المحلية (المعلم / النظافة / المجالس المحلية) لا تُضاف لسطور الفاتورة إذا كانت قيمتها صفراً.
        """
        template = self.env['utility.contract.template'].create({
            'name': 'تعرفة اختبار الرسوم المحلية',
            'code': 'TPL-ZERO-LOCAL-FEES',
            'pricing_mode': 'flat',
            'price_per_kwh': 100.0,
            'service_charge': 500.0,
            'local_fee_mu_allim': 0.0,
            'local_fee_cleaning': 0.0,
            'local_fee_per_kwh': 0.0,
            'subscriber_category_ids': [(6, 0, self.category.ids)],
            'subscriber_ids': [(6, 0, self.subscriber.ids)],
            'scope': 'global',
        })
        # إضافة بنود الرسوم يدوياً في القالب بأسعار صفرية كما في بيانات التهيئة
        prod = self.env['product.product'].search([('type', '=', 'service')], limit=1)
        self.env['utility.contract.template.line'].create([
            {
                'template_id': template.id,
                'name': 'رسم المعلم',
                'meter_line_type': 'mu_allim',
                'specific_price': 0.0,
                'product_id': prod.id,
            },
            {
                'template_id': template.id,
                'name': 'رسم النظافة',
                'meter_line_type': 'cleaning',
                'specific_price': 0.0,
                'product_id': prod.id,
            },
            {
                'template_id': template.id,
                'name': 'رسم المجالس المحلية',
                'meter_line_type': 'municipality',
                'specific_price': 0.0,
                'product_id': prod.id,
            },
        ])

        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'consumption': 1000.0,
            'contract_template_id': template.id,
        })
        order._calculate_amounts()

        # التحقق من عدم وجود أي بند للرسوم المحلية الصفرية في سطور الفاتورة
        local_fee_lines = order.order_line.filtered(
            lambda l: l.meter_line_type in ('local_fee', 'mu_allim', 'cleaning', 'municipality')
        )
        self.assertEqual(len(local_fee_lines), 0, 'الرسوم المحلية الصفرية لا يجب أن تظهر في سطور الفاتورة.')
        self.assertEqual(order.amount_local_fee, 0.0)

        # عند تحديد قيمة لرسم النظافة فقط (مثلاً 50 ريال لكل ك.و.س)
        template.write({'local_fee_cleaning': 50.0})
        # مزامنة السعر المحدد في سطر القالب
        cleaning_line = template.line_ids.filtered(lambda l: l.meter_line_type == 'cleaning')
        cleaning_line.write({'specific_price': 50.0})
        v2 = template._get_or_create_active_version()
        order.write({'contract_template_version_id': v2.id})
        order._calculate_amounts()

        # الآن يجب أن يظهر رسم النظافة فقط، بينما المعلم والمجالس لا يزالان مستبعدين
        local_fee_lines_after = order.order_line.filtered(
            lambda l: l.meter_line_type in ('local_fee', 'mu_allim', 'cleaning', 'municipality')
        )
        self.assertEqual(len(local_fee_lines_after), 1)
        self.assertEqual(local_fee_lines_after[0].meter_line_type, 'cleaning')
        self.assertEqual(local_fee_lines_after[0].price_unit, 50.0)
        self.assertEqual(local_fee_lines_after[0].product_uom_qty, 1000.0)
        self.assertEqual(order.amount_local_fee, 50000.0)

