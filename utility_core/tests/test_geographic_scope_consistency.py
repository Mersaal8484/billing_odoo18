from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestGeographicScopeConsistency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Region = cls.env['utility.region']
        cls.region_a = Region.create({
            'name': 'Geo scope Region A',
            'code': 'GEO-SCOPE-A',
            'type': 'region',
        })
        cls.region_b = Region.create({
            'name': 'Geo scope Region B',
            'code': 'GEO-SCOPE-B',
            'type': 'region',
        })
        cls.branch_a = Region.create({
            'name': 'Geo scope Branch A',
            'code': 'GEO-SCOPE-BA',
            'type': 'area',
            'parent_id': cls.region_a.id,
        })
        cls.branch_b = Region.create({
            'name': 'Geo scope Branch B',
            'code': 'GEO-SCOPE-BB',
            'type': 'area',
            'parent_id': cls.region_b.id,
        })

    def test_01_partner_rejects_branch_from_another_region(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Out of scope branch partner',
                'region_id': self.region_a.id,
                'area_id': self.branch_b.id,
            })

    def test_02_customer_wizard_rejects_branch_from_another_region(self):
        with self.assertRaises(ValidationError):
            self.env['utility.customer.wizard'].create({
                'name': 'Out of scope branch wizard',
                'utility_region_id': self.region_a.id,
                'utility_area_id': self.branch_b.id,
            })

    def test_03_matching_branch_is_accepted(self):
        partner = self.env['res.partner'].create({
            'name': 'In scope branch partner',
            'region_id': self.region_a.id,
            'area_id': self.branch_a.id,
        })
        self.assertEqual(partner.area_id, self.branch_a)
