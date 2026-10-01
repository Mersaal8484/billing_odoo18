import importlib.util
from pathlib import Path

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_MIGRATION_FILE = Path(__file__).resolve().parent.parent / 'migrations' / '16.0.1.1.0' / 'pre-migration.py'


def _load_migrate():
    spec = importlib.util.spec_from_file_location('pre_migration_test', _MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory')
class TestMeterInventoryMigrationPolicy(TransactionCase):
    """Legacy migration must not block upgrades over incomplete inventory
    data while still rejecting genuine serial contradictions."""

    def setUp(self):
        super().setUp()
        self.product = self.env['product.product'].create({
            'name': 'عداد ترقية',
            'type': 'consu',
            'tracking': 'serial',
        })

    def _make_legacy_meter(self, meter_number, serial):
        meter = self.env['utility.meter'].create({
            'meter_number': meter_number,
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
        })
        # Simulate a leftover legacy column before the projection is installed.
        # Drop ORM cache so the installed stored related projection cannot
        # recompute serial_number from lot_id and erase the legacy value.
        self.env.invalidate_all()
        self.env.cr.execute(
            'UPDATE utility_meter SET serial_number = %s WHERE id = %s',
            [serial, meter.id])
        return meter

    def test_missing_product_does_not_block_upgrade(self):
        meter = self._make_legacy_meter('LEGACY-NOPROD-1', 'SER-NOPROD-1')
        # No product_id, no model_id, no lot_id -> policy C, must not raise.
        migrate = _load_migrate()
        self.env.cr.execute(
            "UPDATE utility_meter SET product_id = NULL, model_id = NULL, "
            "lot_id = NULL WHERE id = %s", [meter.id])
        migrate(self.env.cr, '16.0.1.1.0')   # should complete without error
        self.env.invalidate_all()
        self.assertFalse(meter.lot_id)

    def test_nonserial_product_does_not_block_upgrade(self):
        """A legacy meter whose product is not serial-tracked must never block
        the upgrade: it is either safely converted or left unresolved."""
        product = self.env['product.product'].create({
            'name': 'عداد غير مهدأ', 'type': 'consu', 'tracking': 'none',
        })
        meter = self._make_legacy_meter('LEGACY-NONSERIAL-1', 'SER-NS-1')
        self.env.cr.execute(
            "UPDATE utility_meter SET product_id = %s, model_id = NULL, "
            "lot_id = NULL WHERE id = %s", [product.id, meter.id])
        migrate = _load_migrate()
        migrate(self.env.cr, '16.0.1.1.0')   # must not raise
        self.env.invalidate_all()
        self.assertTrue(meter.exists())

    def test_resolvable_serial_product_creates_lot(self):
        meter = self._make_legacy_meter('LEGACY-SERIAL-1', 'SER-OK-9001')
        self.env.cr.execute(
            "UPDATE utility_meter SET product_id = %s, model_id = NULL, "
            "lot_id = NULL WHERE id = %s", [self.product.id, meter.id])
        migrate = _load_migrate()
        migrate(self.env.cr, '16.0.1.1.0')
        # Assert through the stored columns exactly like the migration sees
        # them: the ORM projection would recompute serial_number on the fly.
        self.env.cr.execute(
            "SELECT lot_id, serial_number FROM utility_meter WHERE id = %s",
            [meter.id])
        lot_id, serial_db = self.env.cr.fetchone()
        self.assertTrue(lot_id)
        self.assertEqual(serial_db, 'SER-OK-9001')
        lot = self.env['stock.lot'].browse(lot_id)
        self.assertEqual(lot.name, 'SER-OK-9001')
        self.assertEqual(lot.product_id, self.product)

    def test_existing_lot_serial_conflict_blocks_migration(self):
        lot = self.env['stock.lot'].create({
            'name': 'SER-CONFLICT-A',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': 'LEGACY-CONFLICT-1',
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
            'product_id': self.product.id,
            'lot_id': lot.id,
        })
        # Drop ORM cache so the stored related serial_number projection cannot
        # recompute back over the raw legacy value the migration must read.
        self.env.invalidate_all()
        self.env.cr.execute(
            'UPDATE utility_meter SET serial_number = %s WHERE id = %s',
            ['SER-CONFLICT-B', meter.id])
        migrate = _load_migrate()
        with self.assertRaises(ValidationError):
            migrate(self.env.cr, '16.0.1.1.0')

    def test_operational_and_physical_serial_can_differ(self):
        lot = self.env['stock.lot'].create({
            'name': 'LGY230498711',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPPHYS-1',
            'operational_number': 'OP-458721',
            'product_id': self.product.id,
            'lot_id': lot.id,
        })
        self.assertEqual(meter.operational_number, 'OP-458721')
        self.assertEqual(meter.serial_number, 'LGY230498711')
        self.assertNotEqual(meter.operational_number, meter.serial_number)

    def test_legacy_customer_meter_usable_without_lot(self):
        meter = self.env['utility.meter'].create({
            'meter_number': 'LEGACY-NOLOT-1',
            'operational_number': 'OP-LEGACY-1',
            'connection_type': 'subscriber',
            'payment_type': 'postpaid',
        })
        self.assertFalse(meter.product_id)
        self.assertFalse(meter.lot_id)
        self.assertFalse(meter.serial_number)
        # A customer can still be created end to end without a physical lot.
        region = self.env['utility.region'].create({
            'name': 'منطقة تراثية', 'code': 'LEG-REG', 'type': 'region',
        })
        category = self.env['utility.subscriber.category'].create({
            'name': 'فئة تراثية', 'code': 'LEG-CAT',
        })
        subscriber = self.env['utility.subscriber'].create({
            'name': 'نوع تراثي', 'code': 'LEG-SUB',
            'category_id': category.id,
        })
        partner = self.env['res.partner'].create({
            'name': 'عميل تراثي', 'region_id': region.id,
        })
        customer = self.env['utility.customer'].create({
            'partner_id': partner.id,
            'category_id': category.id,
            'subscriber_id': subscriber.id,
            'meter_id': meter.id,
        })
        customer.action_activate()
        self.assertEqual(customer.state, 'active')
