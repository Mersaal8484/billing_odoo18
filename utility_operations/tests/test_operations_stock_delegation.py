from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_operations')
class TestOperationsStockDelegation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.region = self.env['utility.region'].create({
            'name': 'منطقة العمليات', 'code': 'OP-REG', 'type': 'region',
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة عمليات', 'code': 'OP-CAT',
        })
        self.subscriber = self.env['utility.subscriber'].create({
            'name': 'نوع عمليات', 'code': 'OP-SUB',
            'category_id': self.category.id,
        })
        self.partner = self.env['res.partner'].create({
            'name': 'عميل العمليات', 'region_id': self.region.id,
        })
        self.customer = self.env['utility.customer'].create({
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })

        self.product_serial = self.env['product.product'].create({
            'name': 'عداد عمليات ذكي',
            'type': 'consu',
            'tracking': 'serial',
        })
        self.lot_1 = self.env['stock.lot'].create({
            'name': 'SN-OP-101',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.stock_location.id,
            'lot_id': self.lot_1.id,
            'quantity': 1.0,
        })
        self.meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-OP-101',
            'operational_number': 'OP-NUM-101',
            'product_id': self.product_serial.id,
            'lot_id': self.lot_1.id,
        })

    def test_01_operations_models_do_not_implement_direct_stock_picking_creation(self):
        """Operations models must not implement _create_stock_picking helper."""
        self.assertFalse(hasattr(self.env['utility.service.order'], '_create_stock_picking'))
        self.assertFalse(hasattr(self.env['utility.meter.replacement'], '_create_stock_picking'))

    def test_02_service_order_new_connection_delegates_to_inventory_layer(self):
        """Service order completion invokes utility_inventory API and creates stock picking."""
        so = self.env['utility.service.order'].create({
            'service_type': 'new_connection',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'description': 'توصيلة جديدة تجريبية',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertEqual(self.meter.customer_id, self.customer)
        self.assertEqual(so.picking_count, 1)
        picking = so.picking_ids[0]
        self.assertEqual(picking.utility_inventory_operation, 'install')
        self.assertEqual(picking.utility_meter_id, self.meter)

    def test_03_service_order_removal_delegates_to_inventory_layer(self):
        """Service order removal routes meter to Meter Inspection via inventory API."""
        self.meter.inventory_install_meter(origin='PRE-INST')
        self.meter.write({'customer_id': self.customer.id})

        so = self.env['utility.service.order'].create({
            'service_type': 'meter_removal',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'description': 'رفع عداد تجريبي',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertFalse(self.meter.customer_id)
        self.assertEqual(self.meter.physical_state, 'inspection')

    def test_04_installation_uses_immutable_serial_snapshot(self):
        """utility.installation uses meter_serial_snapshot as immutable serial snapshot."""
        inst = self.env['utility.installation'].create({
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
        })
        self.assertEqual(inst.meter_serial_snapshot, 'SN-OP-101')
        self.assertEqual(inst.meter_serial, 'SN-OP-101')

    def test_05_failed_inventory_validation_rolls_back_service_order_completion(self):
        """If inventory execution fails (e.g. invalid lot state), service order does not complete."""
        # Scrap lot
        scrap_loc = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1)
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': scrap_loc.id,
            'lot_id': self.lot_1.id,
            'quantity': 1.0,
        })
        so = self.env['utility.service.order'].create({
            'service_type': 'new_connection',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'description': 'توصيلة بفشل مخزني',
            'state': 'in_progress',
        })
        with self.assertRaises(ValidationError):
            so.action_complete()
        self.assertEqual(so.state, 'in_progress')

    def test_06_service_order_new_connection_with_new_meter_id_field(self):
        """Service order completion works whether meter_id or new_meter_id is populated."""
        so = self.env['utility.service.order'].create({
            'service_type': 'new_connection',
            'customer_id': self.customer.id,
            'new_meter_id': self.meter.id,
            'description': 'توصيلة عبر new_meter_id',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertEqual(self.meter.customer_id, self.customer)
        self.assertEqual(so.picking_count, 1)

    def test_07_service_order_removal_with_old_meter_id_field(self):
        """Service order removal works whether meter_id or old_meter_id is populated."""
        self.meter.inventory_install_meter(origin='PRE-INST-07')
        self.meter.write({'customer_id': self.customer.id})

        so = self.env['utility.service.order'].create({
            'service_type': 'meter_removal',
            'customer_id': self.customer.id,
            'old_meter_id': self.meter.id,
            'description': 'رفع عداد عبر old_meter_id',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertFalse(self.meter.customer_id)
        self.assertEqual(self.meter.physical_state, 'inspection')

    def test_08_service_order_meter_replacement_field_consistency(self):
        """Service order replacement requires old and new meters and performs replacement stock flow."""
        lot_2 = self.env['stock.lot'].create({
            'name': 'SN-OP-102',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': self.stock_location.id,
            'lot_id': lot_2.id,
            'quantity': 1.0,
        })
        new_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-OP-102',
            'product_id': self.product_serial.id,
            'lot_id': lot_2.id,
        })

        self.meter.inventory_install_meter(origin='PRE-INST-08')
        self.meter.write({'customer_id': self.customer.id})

        so = self.env['utility.service.order'].create({
            'service_type': 'meter_replacement',
            'customer_id': self.customer.id,
            'old_meter_id': self.meter.id,
            'new_meter_id': new_meter.id,
            'description': 'استبدال عداد ميداني',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertFalse(self.meter.customer_id)
        self.assertEqual(self.meter.physical_state, 'inspection')
        self.assertEqual(new_meter.customer_id, self.customer)
        self.assertEqual(new_meter.physical_state, 'installed')

    def test_09_disconnection_service_order_resolves_customer_from_meter(self):
        """Disconnection resolves customer from attached meter if customer_id is empty, or fails if unresolvable."""
        self.meter.inventory_install_meter(origin='PRE-INST-09')
        self.meter.write({'customer_id': self.customer.id})
        self.customer.with_context(lifecycle_operation=True).write({'meter_id': self.meter.id})
        self.customer.action_activate()

        # 1. Successful disconnection resolving customer from meter_id
        so = self.env['utility.service.order'].create({
            'service_type': 'disconnection',
            'meter_id': self.meter.id,
            'description': 'فصل العداد عبر العداد المباشر',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertEqual(self.customer.state, 'disconnected')

        # 2. Unresolvable customer raises ValidationError
        unattached_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-UNATTACHED',
            'product_id': self.product_serial.id,
        })
        so_fail = self.env['utility.service.order'].create({
            'service_type': 'disconnection',
            'meter_id': unattached_meter.id,
            'description': 'فصل بلا مشترك',
            'state': 'in_progress',
        })
        with self.assertRaises(ValidationError):
            so_fail.action_complete()

    def test_10_reconnection_service_order_executes_lifecycle(self):
        """Reconnection executes action_reconnect on customer."""
        self.meter.write({'customer_id': self.customer.id})
        self.customer.with_context(lifecycle_operation=True).write({'meter_id': self.meter.id})
        self.customer.action_activate()
        self.customer.with_context(lifecycle_override=True).action_disconnect(reason='فصل تجريبي لإعادة التوصيل')

        so = self.env['utility.service.order'].create({
            'service_type': 'reconnection',
            'customer_id': self.customer.id,
            'meter_id': self.meter.id,
            'description': 'إعادة توصيل المشترك',
            'state': 'in_progress',
        })
        so.action_complete()
        self.assertEqual(so.state, 'completed')
        self.assertEqual(self.customer.state, 'active')


