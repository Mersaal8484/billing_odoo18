from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory')
class TestMeterStockExecution(TransactionCase):

    def setUp(self):
        super().setUp()
        self.category = self.env['product.category'].create({'name': 'فئة العدادات المادية'})
        self.product_serial = self.env['product.product'].create({
            'name': 'عداد مادي ذكي',
            'type': 'product',
            'tracking': 'serial',
            'categ_id': self.category.id,
        })
        self.lot_stock = self.env['stock.lot'].create({
            'name': 'SN-PHYS-1001',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.lot_installed = self.env['stock.lot'].create({
            'name': 'SN-PHYS-1002',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })

        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.customer_location = self.env.ref('stock.stock_location_customers')
        self.scrap_location = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1)
        if not self.scrap_location:
            self.scrap_location = self.env['stock.location'].create({
                'name': 'مخزن الخردة',
                'scrap_location': True,
                'usage': 'inventory',
                'company_id': self.env.company.id,
            })
        self.inspection_location = self.env['utility.meter']._resolve_meter_inspection_location(self.env.company)

        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.stock_location.id,
            'lot_id': self.lot_stock.id,
            'quantity': 1.0,
        })

        self.meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-EXEC-001',
            'operational_number': 'OP-EXEC-001',
            'product_id': self.product_serial.id,
            'lot_id': self.lot_stock.id,
        })

    def test_01_physical_installation_creates_correct_stock_movement(self):
        """Test physical meter installation moves stock from Stock -> Customers."""
        picking = self.meter.inventory_install_meter(origin='SO-TEST-001', operation_ref='REF-INST-1')
        self.assertTrue(picking)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.location_id, self.stock_location)
        self.assertEqual(picking.location_dest_id, self.customer_location)
        self.assertEqual(picking.utility_inventory_operation, 'install')
        self.assertEqual(picking.utility_meter_id, self.meter)
        self.assertEqual(picking.utility_operation_ref, 'REF-INST-1')
        self.assertEqual(self.meter.physical_state, 'installed')

    def test_02_installation_rejects_scrap_serial(self):
        """Test that creating a meter with a lot in scrap location is rejected at create time."""
        scrap_lot = self.env['stock.lot'].create({
            'name': 'SN-SCRAP-99',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.scrap_location.id,
            'lot_id': scrap_lot.id,
            'quantity': 1.0,
        })
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-SCRAP-01',
                'product_id': self.product_serial.id,
                'lot_id': scrap_lot.id,
            })

    def test_03_installation_rejects_product_lot_mismatch(self):
        """Test installation rejects invalid lot/product combo."""
        other_product = self.env['product.product'].create({
            'name': 'منتج آخر',
            'type': 'product',
            'tracking': 'serial',
        })
        mismatch_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-MISMATCH',
            'product_id': other_product.id,
        })
        self.env.cr.execute(
            'UPDATE utility_meter SET lot_id = %s WHERE id = %s',
            [self.lot_stock.id, mismatch_meter.id]
        )
        self.env.invalidate_all()
        with self.assertRaises(ValidationError):
            mismatch_meter.inventory_install_meter(origin='SO-MISMATCH')

    def test_04_removal_routes_to_inspection_by_default(self):
        """Test removal moves meter from Customers -> Meter Inspection (not Scrap)."""
        self.meter.inventory_install_meter(origin='SO-INST')
        picking = self.meter.inventory_remove_meter(origin='SO-REM', operation_ref='REF-REM-1')
        self.assertTrue(picking)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.location_id, self.customer_location)
        self.assertEqual(picking.location_dest_id, self.inspection_location)
        self.assertNotEqual(picking.location_dest_id, self.scrap_location)
        self.assertEqual(self.meter.physical_state, 'inspection')

    def test_05_explicit_scrap_action_routes_to_scrap(self):
        """Test explicit scrap routes meter to scrap location."""
        picking = self.meter.inventory_scrap_meter(origin='SO-SCRAP-ACTION')
        self.assertTrue(picking)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.location_dest_id, self.scrap_location)
        self.assertEqual(self.meter.physical_state, 'scrap')

    def test_06_return_to_stock_routes_inspection_to_stock(self):
        """Test return to stock moves meter from Inspection -> Stock."""
        self.meter.inventory_install_meter(origin='SO-INST')
        self.meter.inventory_remove_meter(origin='SO-REM')
        picking = self.meter.inventory_return_to_stock(origin='SO-RET')
        self.assertTrue(picking)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(picking.location_id, self.inspection_location)
        self.assertEqual(picking.location_dest_id, self.stock_location)
        self.assertEqual(self.meter.physical_state, 'available')

    def test_07_replacement_executes_atomic_movement(self):
        """Test replacement executes atomic removal of old and installation of new."""
        self.meter.inventory_install_meter(origin='SO-OLD-INST')

        lot_new = self.env['stock.lot'].create({
            'name': 'SN-PHYS-NEW-900',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.stock_location.id,
            'lot_id': lot_new.id,
            'quantity': 1.0,
        })
        new_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-NEW-900',
            'product_id': self.product_serial.id,
            'lot_id': lot_new.id,
        })

        res = self.meter.inventory_replace_meter(
            new_meter=new_meter,
            origin='SO-REPLACE-1',
            operation_ref='REF-REPLACE-1',
        )
        self.assertTrue(res['old_picking'])
        self.assertTrue(res['new_picking'])
        self.assertEqual(res['old_picking'].location_dest_id, self.inspection_location)
        self.assertEqual(res['new_picking'].location_dest_id, self.customer_location)
        self.assertEqual(self.meter.physical_state, 'inspection')
        self.assertEqual(new_meter.physical_state, 'installed')

    def test_08_idempotency_prevents_duplicate_pickings(self):
        """Test that calling inventory_install_meter twice with same operation_ref returns existing picking."""
        p1 = self.meter.inventory_install_meter(origin='SO-IDEM', operation_ref='IDEM-KEY-001')
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.stock_location.id,
            'lot_id': self.lot_stock.id,
            'quantity': 1.0,
        })
        p2 = self.meter.inventory_install_meter(origin='SO-IDEM', operation_ref='IDEM-KEY-001')
        self.assertEqual(p1.id, p2.id)

    def test_09_legacy_meter_raises_validation_error_on_physical_actions(self):
        """Test physical operations on legacy meters without product/lot raise ValidationError."""
        legacy_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-LEGACY-SYS',
            'operational_number': 'OP-LEGACY-SYS',
        })
        self.assertFalse(legacy_meter.product_id)
        self.assertFalse(legacy_meter.lot_id)
        self.assertEqual(legacy_meter.physical_state, 'unresolved')
        with self.assertRaises(ValidationError):
            legacy_meter.inventory_install_meter(origin='SO-LEGACY')
        with self.assertRaises(ValidationError):
            legacy_meter.inventory_remove_meter(origin='SO-LEGACY')

    def test_10_meter_model_product_mismatch_rejected(self):
        """Test that assigning a meter product different from model_id.product_id raises ValidationError."""
        model_product = self.env['product.product'].create({
            'name': 'منتج موديل أصل',
            'type': 'product',
            'tracking': 'serial',
        })
        other_product = self.env['product.product'].create({
            'name': 'منتج مخالف',
            'type': 'product',
            'tracking': 'serial',
        })
        model = self.env['utility.meter.model'].create({
            'name': 'موديل محدد المنتج',
            'product_id': model_product.id,
        })
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-PRODUCT-MISMATCH',
                'model_id': model.id,
                'product_id': other_product.id,
            })

    def test_11_warehouse_inspection_location_resolution(self):
        """Test per-warehouse meter inspection location creation and resolution."""
        wh = self.env['stock.warehouse'].create({
            'name': 'مستودع فرعي أداء',
            'code': 'WH-PERF',
            'company_id': self.env.company.id,
        })
        self.assertTrue(wh.meter_inspection_location_id)
        self.assertIn(wh.code, wh.meter_inspection_location_id.name)
        resolved_loc = self.meter._resolve_meter_inspection_location(warehouse=wh)
        self.assertEqual(resolved_loc, wh.meter_inspection_location_id)

    def test_12_strict_picking_type_resolution_rejects_missing_direction(self):
        """Test strict picking type resolution raises ValidationError if warehouse has no picking types."""
        dummy_company = self.env['res.company'].create({'name': 'شركة اختبار بدون حركات'})
        dummy_loc = self.env['stock.location'].create({
            'name': 'موقع اختبار',
            'usage': 'internal',
            'company_id': dummy_company.id,
        })
        with self.assertRaises(ValidationError):
            self.meter._resolve_meter_picking_type(
                source_loc=dummy_loc,
                dest_loc=self.customer_location,
            )

    def test_13_physical_state_is_unstored_live_projection(self):
        """Test physical_state dynamically updates on movements without stored cache staleness."""
        self.assertEqual(self.meter.physical_state, 'available')
        self.meter.inventory_install_meter(origin='SO-LIVE-STATE')
        self.assertEqual(self.meter.physical_state, 'installed')

    def test_14_multi_warehouse_execution_and_isolation(self):
        """Test installation and removal strictly respect designated warehouse."""
        wh_sanaa = self.env['stock.warehouse'].create({
            'name': 'مستودع صنعاء',
            'code': 'WH-SANAA',
            'company_id': self.env.company.id,
        })
        lot_sanaa = self.env['stock.lot'].create({
            'name': 'SN-SANAA-001',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': wh_sanaa.lot_stock_id.id,
            'lot_id': lot_sanaa.id,
            'quantity': 1.0,
        })
        meter_sanaa = self.env['utility.meter'].create({
            'meter_number': 'MTR-SANAA-01',
            'product_id': self.product_serial.id,
            'lot_id': lot_sanaa.id,
        })

        # Install from WH-SANAA
        p_inst = meter_sanaa.inventory_install_meter(warehouse=wh_sanaa, origin='SO-SANAA-INST')
        self.assertEqual(p_inst.location_id, wh_sanaa.lot_stock_id)
        self.assertEqual(p_inst.picking_type_id, wh_sanaa.out_type_id)

        # Remove to WH-SANAA Meter Inspection
        p_rem = meter_sanaa.inventory_remove_meter(warehouse=wh_sanaa, origin='SO-SANAA-REM')
        self.assertEqual(p_rem.location_dest_id, wh_sanaa.meter_inspection_location_id)
        self.assertEqual(p_rem.picking_type_id, wh_sanaa.in_type_id)

    def test_15_multi_warehouse_replacement(self):
        """Test replacement across different warehouses (Old -> WH-A Inspection, New WH-B Stock -> Customers)."""
        wh_a = self.env['stock.warehouse'].create({
            'name': 'مستودع أ',
            'code': 'WH-A',
            'company_id': self.env.company.id,
        })
        wh_b = self.env['stock.warehouse'].create({
            'name': 'مستودع ب',
            'code': 'WH-B',
            'company_id': self.env.company.id,
        })

        meter_old = self.meter
        lot_a = self.env['stock.lot'].create({
            'name': 'SN-WHA-OLD',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': wh_a.lot_stock_id.id,
            'lot_id': lot_a.id,
            'quantity': 1.0,
        })
        meter_old.write({'lot_id': lot_a.id})
        meter_old.inventory_install_meter(warehouse=wh_a, origin='SO-OLD-INST')

        lot_b = self.env['stock.lot'].create({
            'name': 'SN-WHB-99',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': wh_b.lot_stock_id.id,
            'lot_id': lot_b.id,
            'quantity': 1.0,
        })
        meter_new = self.env['utility.meter'].create({
            'meter_number': 'MTR-WHB-99',
            'product_id': self.product_serial.id,
            'lot_id': lot_b.id,
        })

        res = meter_old.inventory_replace_meter(
            new_meter=meter_new,
            old_warehouse=wh_a,
            new_warehouse=wh_b,
            origin='SO-MULTI-REPLACE',
        )
        self.assertEqual(res['old_picking'].location_dest_id, wh_a.meter_inspection_location_id)
        self.assertEqual(res['new_picking'].location_id, wh_b.lot_stock_id)

    def test_16_repair_lifecycle_inspection_to_repair_and_back(self):
        """Test meter repair movements: Inspection -> Repair -> Inspection -> Stock."""
        wh = self.env['stock.warehouse'].create({
            'name': 'مستودع إصلاح',
            'code': 'WH-REP',
            'company_id': self.env.company.id,
        })

        # Inspection -> Repair
        p1 = self.meter.inventory_repair_meter(action='to_repair', warehouse=wh, origin='SO-REP-1')
        self.assertEqual(p1.location_id, wh.meter_inspection_location_id)
        self.assertEqual(p1.location_dest_id, wh.meter_repair_location_id)

        # Repair -> Inspection (re-inspection)
        p2 = self.meter.inventory_repair_meter(action='from_repair', warehouse=wh, origin='SO-REP-2')
        self.assertEqual(p2.location_id, wh.meter_repair_location_id)
        self.assertEqual(p2.location_dest_id, wh.meter_inspection_location_id)

    def test_17_ambiguous_multi_warehouse_raises_validation_error(self):
        """Test _resolve_warehouse raises ValidationError if multi-warehouse company context is ambiguous."""
        multi_company = self.env['res.company'].create({'name': 'شركة متعددة المستودعات'})
        wh1 = self.env['stock.warehouse'].create({'name': 'WH1', 'code': 'W1', 'company_id': multi_company.id})
        wh2 = self.env['stock.warehouse'].create({'name': 'WH2', 'code': 'W2', 'company_id': multi_company.id})

        unbound_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-AMBIGUOUS',
            'company_id': multi_company.id,
        })

        with self.assertRaises(ValidationError):
            unbound_meter._resolve_warehouse()


