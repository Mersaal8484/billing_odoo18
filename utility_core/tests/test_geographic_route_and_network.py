from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestGeographicRouteAndNetwork(TransactionCase):
    """Deterministic tests for the shared route hierarchy and network types."""

    def setUp(self):
        super().setUp()
        self.Customer = self.env['utility.customer']
        self.Region = self.env['utility.region']
        self.Transformer = self.env['utility.transformer']
        self.Feeder = self.env['utility.feeder']
        self.Meter = self.env['utility.meter']
        self.MeterModel = self.env['utility.meter.model']
        self.Connection = self.env['utility.connection']
        self.ConnectionType = self.env['utility.connection.type']
        self.Substation = self.env['utility.substation']
        self.Route = self.env['utility.route']
        self.Reading = self.env['utility.reading']
        self.Replacement = self.env['utility.meter.replacement']

    def test_route_domain_specificity(self):
        self.assertEqual(
            self.Customer._get_route_domain(1, 2, 3), [('zone_id', '=', 3)])
        self.assertEqual(
            self.Customer._get_route_domain(1, 2), [('area_id', '=', 2)])
        self.assertEqual(
            self.Customer._get_route_domain(1), [('region_id', '=', 1)])
        self.assertEqual(self.Customer._get_route_domain(), [])

    def test_private_transformer_is_geographically_validated(self):
        region = self.Region.create({'name': 'منطقة اختبار', 'code': 'GEO-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع اختبار', 'code': 'GEO-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'ناحية اختبار', 'code': 'GEO-Z', 'type': 'zone', 'parent_id': area.id})
        other_region = self.Region.create({'name': 'منطقة أخرى', 'code': 'GEO-R2', 'type': 'region'})
        other_area = self.Region.create({'name': 'فرع آخر', 'code': 'GEO-A2', 'type': 'area', 'parent_id': other_region.id})
        other_zone = self.Region.create({'name': 'ناحية أخرى', 'code': 'GEO-Z2', 'type': 'zone', 'parent_id': other_area.id})
        transformer = self.Transformer.create({
            'name': 'محول خاص اختبار', 'code': 'GEO-T', 'is_private': True,
            'zone_region_id': zone.id,
        })
        zone.write({'private_transformer_id': transformer.id})
        self.assertEqual(zone.private_transformer_id, transformer)
        with self.assertRaises(ValidationError):
            other_zone.write({'private_transformer_id': transformer.id})

    def test_general_transformer_requires_region_and_area_under_region(self):
        """المحول العام يجب أن يكون مربوطًا بمنطقة وفرع تابع لها؛ الخاص مستثنى."""
        region = self.Region.create({'name': 'منطقة إلزامية', 'code': 'REQ-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع إلزامي', 'code': 'REQ-A', 'type': 'area', 'parent_id': region.id})
        other_area = self.Region.create({'name': 'فرع تابع لمنطقة أخرى', 'code': 'REQ-A2', 'type': 'area'})

        with self.assertRaises(ValidationError):
            self.Transformer.create({'name': 'محول بدون ربط جغرافي', 'code': 'REQ-T1'})
        with self.assertRaises(ValidationError):
            self.Transformer.create({
                'name': 'محول بدون فرع', 'code': 'REQ-T2', 'region_id': region.id,
            })
        with self.assertRaises(ValidationError):
            self.Transformer.create({
                'name': 'فرع خارج المنطقة', 'code': 'REQ-T3',
                'region_id': region.id, 'area_id': other_area.id,
            })

        private = self.Transformer.create({
            'name': 'محول خاص معفى', 'code': 'REQ-PRV1', 'is_private': True,
        })
        self.assertTrue(private.is_private)

        valid = self.Transformer.create({
            'name': 'محول سليم', 'code': 'REQ-T4',
            'region_id': region.id, 'area_id': area.id,
        })
        self.assertEqual(valid.region_id, region)
        self.assertEqual(valid.area_id, area)
        self.assertTrue(valid.zone_region_id)
        self.assertEqual(valid.zone_region_id.parent_id, area)
        self.assertEqual(valid.zone_region_id.parent_id.parent_id, region)

        with self.assertRaises(ValidationError):
            valid.write({'zone_region_id': False})

    def test_write_area_change_updates_zone_and_keeps_one_to_one_zone(self):
        """تغيير الفرع فقط عبر write() يحدّث وجهة الـZone دون تبديل رابط 1:1."""
        region = self.Region.create({'name': 'منطقة نقل فرع', 'code': 'WRT-R', 'type': 'region'})
        area_old = self.Region.create({'name': 'فرع قديم', 'code': 'WRT-A1', 'type': 'area', 'parent_id': region.id})
        area_new = self.Region.create({'name': 'فرع جديد', 'code': 'WRT-A2', 'type': 'area', 'parent_id': region.id})
        transformer = self.Transformer.create({
            'name': 'محول نقل فرع', 'code': 'WRT-T',
            'region_id': region.id, 'area_id': area_old.id,
        })
        zone = transformer.zone_region_id

        transformer.write({'area_id': area_new.id})

        self.assertEqual(transformer.zone_region_id, zone)
        self.assertEqual(zone.transformer_origin_id, transformer)
        self.assertEqual(zone.parent_id, area_new)
        self.assertEqual(zone.parent_id.parent_id, region)
        self.assertEqual(transformer.area_id, area_new)
        self.assertEqual(transformer.region_id, region)

    def test_write_region_and_area_relocate_zone(self):
        """نقل المحول إلى منطقة وفرع جديدين عبر write() يحدّث الـZone والسلسلة كاملة."""
        r1 = self.Region.create({'name': 'منطقة أولى', 'code': 'WRT-R1', 'type': 'region'})
        a1 = self.Region.create({'name': 'فرع أول', 'code': 'WRT-R1A', 'type': 'area', 'parent_id': r1.id})
        r2 = self.Region.create({'name': 'منطقة ثانية', 'code': 'WRT-R2', 'type': 'region'})
        a2 = self.Region.create({'name': 'فرع ثانٍ', 'code': 'WRT-R2A', 'type': 'area', 'parent_id': r2.id})
        transformer = self.Transformer.create({
            'name': 'محول انتقال', 'code': 'WRT-T2',
            'region_id': r1.id, 'area_id': a1.id,
        })
        zone = transformer.zone_region_id

        transformer.write({'region_id': r2.id, 'area_id': a2.id})

        self.assertEqual(transformer.zone_region_id, zone)
        self.assertEqual(zone.parent_id, a2)
        self.assertEqual(zone.parent_id.parent_id, r2)
        self.assertEqual(transformer.area_id, a2)
        self.assertEqual(transformer.region_id, r2)

    def test_write_region_change_only_raises_for_general_transformer(self):
        """تغيير المنطقة دون تغيير الفرع عبر write() يُرفض للمحول العام."""
        region = self.Region.create({'name': 'منطقة مصدر', 'code': 'WRT-R3', 'type': 'region'})
        area = self.Region.create({'name': 'فرع مصدر', 'code': 'WRT-R3A', 'type': 'area', 'parent_id': region.id})
        other_region = self.Region.create({'name': 'منطقة هدف', 'code': 'WRT-R4', 'type': 'region'})
        transformer = self.Transformer.create({
            'name': 'محول تنقيل', 'code': 'WRT-T3',
            'region_id': region.id, 'area_id': area.id,
        })

        with self.assertRaises(ValidationError):
            transformer.write({'region_id': other_region.id})

        self.assertEqual(transformer.area_id, area)
        self.assertEqual(transformer.region_id, region)

    def test_private_transformer_write_can_relocate_and_clear_geography(self):
        """المحول الخاص عبر write() يمكنه تغيير فرعه/منطقته أو مسح الربط الجغرافي."""
        r1 = self.Region.create({'name': 'منطقة خاصة 1', 'code': 'WRT-PR1', 'type': 'region'})
        a1 = self.Region.create({'name': 'فرع خاص 1', 'code': 'WRT-PR1A', 'type': 'area', 'parent_id': r1.id})
        r2 = self.Region.create({'name': 'منطقة خاصة 2', 'code': 'WRT-PR2', 'type': 'region'})
        a2 = self.Region.create({'name': 'فرع خاص 2', 'code': 'WRT-PR2A', 'type': 'area', 'parent_id': r2.id})
        transformer = self.Transformer.create({
            'name': 'محول خاص متحرك', 'code': 'WRT-PRV',
            'is_private': True, 'region_id': r1.id, 'area_id': a1.id,
        })

        transformer.write({'region_id': r2.id, 'area_id': a2.id})
        self.assertEqual(transformer.zone_region_id.parent_id, a2)
        self.assertEqual(transformer.area_id, a2)
        self.assertEqual(transformer.region_id, r2)

        transformer.write({'region_id': False, 'area_id': False})
        self.assertFalse(transformer.zone_region_id.parent_id)
        self.assertFalse(transformer.area_id)
        self.assertFalse(transformer.region_id)

    def test_transformer_and_zone_have_a_bidirectional_one_to_one_link(self):
        region = self.Region.create({'name': 'منطقة 1:1', 'code': 'ONE-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع 1:1', 'code': 'ONE-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'Zone 1:1', 'code': 'ONE-Z', 'type': 'zone', 'parent_id': area.id})
        other_zone = self.Region.create({'name': 'Zone 1:1 آخر', 'code': 'ONE-Z2', 'type': 'zone', 'parent_id': area.id})

        transformer = self.Transformer.create({
            'name': 'محول 1:1', 'code': 'ONE-T', 'zone_region_id': zone.id,
        })

        self.assertEqual(transformer.zone_region_id, zone)
        self.assertEqual(zone.transformer_origin_id, transformer)
        with self.assertRaises(ValidationError):
            self.Transformer.create({
                'name': 'محول مكرر', 'code': 'ONE-T2', 'zone_region_id': zone.id,
            })

        transformer.write({'zone_region_id': other_zone.id})
        self.assertFalse(zone.transformer_origin_id)
        self.assertEqual(other_zone.transformer_origin_id, transformer)

    def test_feeder_type_is_backward_compatible_and_searchable(self):
        default_feeder = self.Feeder.create({'name': 'فيدر توزيع', 'code': 'GEO-F1'})
        production = self.Feeder.create({
            'name': 'فيدر إنتاج', 'code': 'GEO-F2', 'feeder_type': 'production_area',
        })
        self.assertEqual(default_feeder.feeder_type, 'distribution')
        self.assertEqual(production.feeder_type, 'production_area')
        self.assertIn(production, self.Feeder.search([('feeder_type', '=', 'production_area')]))

    def test_meter_phase_must_match_transformer_or_feeder(self):
        single_model = self.MeterModel.create({
            'name': 'موديل أحادي', 'code': 'PH-1', 'phase': 'single',
        })
        three_model = self.MeterModel.create({
            'name': 'موديل ثلاثي', 'code': 'PH-3', 'phase': 'three',
        })
        region = self.Region.create({'name': 'منطقة طور', 'code': 'PH-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع طور', 'code': 'PH-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'Zone طور', 'code': 'PH-Z', 'type': 'zone', 'parent_id': area.id})
        transformer = self.Transformer.create({
            'name': 'محول ثلاثي', 'code': 'PH-T', 'zone_region_id': zone.id, 'phase': 'three',
        })
        feeder = self.Feeder.create({
            'name': 'فيدر أحادي', 'code': 'PH-F', 'phase': 'single',
        })

        with self.assertRaises(ValidationError):
            self.Meter.create({
                'meter_number': 'PH-M-T', 'model_id': single_model.id,
                'connection_type': 'transformer', 'linked_transformer_id': transformer.id,
            })
        with self.assertRaises(ValidationError):
            self.Meter.create({
                'meter_number': 'PH-M-F', 'model_id': three_model.id,
                'connection_type': 'feeder', 'linked_feeder_id': feeder.id,
            })

    def test_connection_type_phase_must_match_subscriber_meter(self):
        single_model = self.MeterModel.create({
            'name': 'موديل وصلة أحادي', 'code': 'CON-PH-1', 'phase': 'single',
        })
        three_type = self.ConnectionType.create({
            'name': 'توصيلة ثلاثية اختبار', 'code': 'CON-PH-3', 'phase': 'three',
        })
        meter = self.Meter.create({'meter_number': 'CON-PH-M', 'model_id': single_model.id})
        partner = self.env['res.partner'].create({'name': 'مشترك اختبار الطور'})
        customer = self.Customer.create({
            'customer_number': 'CON-PH-C', 'partner_id': partner.id,
        })
        with self.assertRaises(ValidationError):
            self.Connection.create({
                'customer_id': customer.id, 'connection_type': three_type.id, 'meter_id': meter.id,
            })

    def test_network_and_route_hierarchy_cannot_be_mixed(self):
        region = self.Region.create({'name': 'منطقة شبكة', 'code': 'NET-R', 'type': 'region'})
        area = self.Region.create({'name': 'فرع شبكة', 'code': 'NET-A', 'type': 'area', 'parent_id': region.id})
        zone = self.Region.create({'name': 'Zone شبكة', 'code': 'NET-Z', 'type': 'zone', 'parent_id': area.id})
        other_zone = self.Region.create({'name': 'Zone شبكة أخرى', 'code': 'NET-Z2', 'type': 'zone', 'parent_id': area.id})
        station = self.Substation.create({'name': 'محطة شبكة', 'code': 'NET-S', 'zone_id': zone.id})
        feeder = self.Feeder.create({
            'name': 'فيدر شبكة', 'code': 'NET-F', 'substation_id': station.id,
        })
        transformer = self.Transformer.create({
            'name': 'محول شبكة', 'code': 'NET-T', 'zone_region_id': zone.id,
            'substation_id': station.id, 'feeder_id': feeder.id,
        })
        self.assertEqual(feeder.area_id, area)
        with self.assertRaises(ValidationError):
            self.Route.create({
                'name': 'مسار غير متطابق', 'code': 'NET-RT', 'area_id': area.id,
                'zone_id': other_zone.id, 'transformer_id': transformer.id,
            })

    def test_reading_category_and_replacement_phase_are_enforced(self):
        single_model = self.MeterModel.create({
            'name': 'موديل اختبار أحادي', 'code': 'RULE-PH-1', 'phase': 'single',
        })
        three_model = self.MeterModel.create({
            'name': 'موديل اختبار ثلاثي', 'code': 'RULE-PH-3', 'phase': 'three',
        })
        partner = self.env['res.partner'].create({'name': 'مشترك قواعد القراءة'})
        customer = self.Customer.create({'customer_number': 'RULE-READ-C', 'partner_id': partner.id})
        meter = self.Meter.create({
            'meter_number': 'RULE-READ-M', 'model_id': single_model.id,
            'connection_type': 'subscriber', 'customer_id': customer.id,
        })
        with self.assertRaises(ValidationError):
            self.Reading.create({
                'meter_id': meter.id, 'account_id': customer.id,
                'reading_value': 10.0, 'reading_category': 'feeder',
            })

        feeder = self.Feeder.create({'name': 'فيدر قواعد', 'code': 'RULE-F', 'phase': 'three'})
        new_meter = self.Meter.create({
            'meter_number': 'RULE-NEW-M', 'model_id': single_model.id,
        })
        with self.assertRaises(ValidationError):
            self.Replacement.create({
                'target_type': 'feeder', 'feeder_id': feeder.id,
                'new_meter_id': new_meter.id, 'new_opening_reading': 0.0,
            })
        valid_meter = self.Meter.create({
            'meter_number': 'RULE-NEW-M3', 'model_id': three_model.id,
        })
        replacement = self.Replacement.create({
            'target_type': 'feeder', 'feeder_id': feeder.id,
            'new_meter_id': valid_meter.id, 'new_opening_reading': 0.0,
        })
        self.assertEqual(replacement.new_meter_id, valid_meter)
