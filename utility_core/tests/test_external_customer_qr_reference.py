from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestExternalCustomerQRReference(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار QR الخارجي',
            'code': 'EXT-QR-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار QR الخارجي',
            'code': 'EXT-QR-SUBSCRIBER',
            'category_id': cls.category.id,
        })

    def _customer(self, suffix, reference=False):
        partner = self.env['res.partner'].create({'name': 'عميل QR %s' % suffix})
        return self.env['utility.customer'].create({
            'customer_number': 'EXT-QR-CUSTOMER-%s' % suffix,
            'external_qr_reference': reference,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
        })

    def test_customer_without_external_qr_is_valid(self):
        customer = self._customer('NO-QR')
        self.assertFalse(customer.external_qr_reference)

    def test_external_qr_reference_normalization(self):
        customer = self._customer('NORMALIZE', '  QR-100  ')
        self.assertEqual(customer.external_qr_reference, 'QR-100')
        customer.write({'external_qr_reference': '   '})
        self.assertFalse(customer.external_qr_reference)

    def test_external_qr_reference_unique_per_company(self):
        self._customer('UNIQUE-A', 'QR-UNIQUE')
        with self.cr.savepoint(), self.assertRaises(IntegrityError):
            self._customer('UNIQUE-B', 'QR-UNIQUE')

    def test_external_qr_reference_can_change(self):
        customer = self._customer('CHANGE', 'QR-OLD')
        customer.write({'external_qr_reference': 'QR-NEW'})
        self.assertEqual(customer.external_qr_reference, 'QR-NEW')

    def test_old_qr_no_longer_resolves_after_change(self):
        customer = self._customer('CURRENT', 'QR-OLD-CURRENT')
        customer.write({'external_qr_reference': 'QR-NEW-CURRENT'})
        self.assertFalse(self.env['utility.customer'].search([
            ('external_qr_reference', '=', 'QR-OLD-CURRENT'),
        ]))
        self.assertEqual(self.env['utility.customer'].search([
            ('external_qr_reference', '=', 'QR-NEW-CURRENT'),
        ]), customer)

    def test_customer_search_by_external_qr_reference(self):
        customer = self._customer('SEARCH', 'QR-SEARCH')
        matches = self.env['utility.customer'].name_search('QR-SEARCH')
        self.assertIn(customer.id, [record_id for record_id, _name in matches])
