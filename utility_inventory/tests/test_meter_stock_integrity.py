from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory')
class TestMeterStockIntegrity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.category = self.env['product.category'].create({'name': 'عدادات كهربائية'})
        self.product_serial = self.env['product.product'].create({
            'name': 'عداد رقمي ذكي',
            'type': 'consu',
            'tracking': 'serial',
            'categ_id': self.category.id,
        })
        self.product_none = self.env['product.product'].create({
            'name': 'كيبل توصيل غير مهدأ',
            'type': 'consu',
            'tracking': 'none',
        })
        self.lot_1 = self.env['stock.lot'].create({
            'name': 'SN-MTR-9001',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.lot_2 = self.env['stock.lot'].create({
            'name': 'SN-MTR-9002',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })

    def test_meter_product_lot_mismatch_raises(self):
        """Test that assigning a lot from product A to meter with product B raises ValidationError."""
        product_other = self.env['product.product'].create({
            'name': 'عداد ميكانيكي',
            'type': 'consu',
            'tracking': 'serial',
        })
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-901',
                'product_id': product_other.id,
                'lot_id': self.lot_1.id,
            })

    def test_meter_product_not_serial_raises(self):
        """Test that assigning a product without serial tracking raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-902',
                'product_id': self.product_none.id,
            })

    def test_meter_serial_unique_active_constraint(self):
        """Test that a physical stock lot cannot be assigned to two active utility meters."""
        meter_1 = self.env['utility.meter'].create({
            'meter_number': 'MTR-TEST-903',
            'product_id': self.product_serial.id,
            'lot_id': self.lot_1.id,
        })
        self.assertTrue(meter_1.id)
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-904',
                'product_id': self.product_serial.id,
                'lot_id': self.lot_1.id,
            })

    def test_scrapped_serial_cannot_be_assigned(self):
        """Test that a serial lot located in a scrap location raises ValidationError on meter creation."""
        scrap_location = self.env['stock.location'].create({
            'name': 'مخزن الخردة التالفة للاختبار',
            'scrap_location': True,
            'usage': 'inventory',
        })
        self.env['stock.quant'].create({
            'product_id': self.product_serial.id,
            'location_id': scrap_location.id,
            'lot_id': self.lot_2.id,
            'quantity': 1.0,
        })
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-SCRAP-999',
                'product_id': self.product_serial.id,
                'lot_id': self.lot_2.id,
            })

    def test_serial_number_is_readonly_projection_of_stock_lot(self):
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-PROJECTION-001',
            'product_id': self.product_serial.id,
            'lot_id': self.lot_1.id,
        })
        self.assertEqual(meter.serial_number, self.lot_1.name)
        with self.assertRaises(ValidationError):
            meter.write({'serial_number': 'SN-OTHER'})
