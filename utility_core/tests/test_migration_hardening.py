import base64
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestMigrationHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.other_company = self.env['res.company'].create({'name': 'شركة الاختبار الثانوية'})

        # Setup master data for primary company
        self.region = self.env['utility.region'].create({
            'name': 'المنطقة الشمالية',
            'code': 'REG-NORTH',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.area = self.env['utility.region'].create({
            'name': 'فرع المركز',
            'code': 'AREA-CENTER',
            'type': 'area',
            'parent_id': self.region.id,
            'company_id': self.company.id,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني',
            'code': 'RESIDENTIAL',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك عادي',
            'code': 'NORMAL',
            'category_id': self.category.id,
        })
        self.contract_template = self.env['utility.contract.template'].create({
            'name': 'قالب توريد الطاقة',
            'code': 'TMPL-POWER',
            'subscriber_category_ids': [(4, self.category.id)],
            'subscriber_ids': [(4, self.subscriber_type.id)],
            'region_ids': [(4, self.region.id)],
            'area_ids': [(4, self.area.id)],
        })
        self.meter_model_single = self.env['utility.meter.model'].create({
            'name': 'عداد أحادي 1P',
            'code': 'MDL-1P',
            'phase': 'single',
        })
        self.meter_model_three = self.env['utility.meter.model'].create({
            'name': 'عداد ثلاثي 3P',
            'code': 'MDL-3P',
            'phase': 'three',
        })
        self.company.legacy_single_phase_meter_model_id = self.meter_model_single

        # Setup master data for other company
        self.region_b = self.env['utility.region'].create({
            'name': 'المنطقة الجنوبية',
            'code': 'REG-SOUTH',
            'type': 'region',
            'company_id': self.other_company.id,
        })

    def test_mapping_orm_constraints_and_normalization(self):
        """اختبار القيود والقواعد لنموذج جدول الترميز واستقلالية الشركات."""
        # 1. Whitspace normalization
        mapping = self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': '  REG_001  ',
            'region_id': self.region.id,
            'company_id': self.company.id,
        })
        self.assertEqual(mapping.legacy_code, 'REG_001')

        # 2. Duplicate code in same company is rejected
        with self.assertRaises(Exception):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'REG_001',
                'region_id': self.region.id,
                'company_id': self.company.id,
            })

        # 3. Target company consistency: linking company B mapping to company A region must fail
        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'REG_002',
                'region_id': self.region.id,  # Company A region
                'company_id': self.other_company.id,  # Company B
            })

        # 4. Correct multi-company mapping is allowed
        other_mapping = self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': 'REG_003',
            'region_id': self.region_b.id,
            'company_id': self.other_company.id,
        })
        self.assertTrue(other_mapping.id)

        # 5. Target field constraint validation (Exactly one target matching mapping_type)
        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'area',
                'legacy_code': 'AREA_ERR',
                'company_id': self.company.id,
            })

        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'MULTI_TARGET_ERR',
                'region_id': self.region.id,
                'area_id': self.area.id,  # Two targets set!
                'company_id': self.company.id,
            })

    def test_legacy_meter_model_domains_match_configured_phase(self):
        """إعدادات موديلات العدادات القديمة تعرض الطور المتوافق فقط."""
        company_fields = self.env['res.company']._fields
        settings_fields = self.env['res.config.settings']._fields
        self.assertIn("('phase', '=', 'single')", str(company_fields['legacy_single_phase_meter_model_id'].domain))
        self.assertIn("('phase', '=', 'three')", str(company_fields['legacy_three_phase_meter_model_id'].domain))
        self.assertIn("('phase', '=', 'single')", str(settings_fields['legacy_single_phase_meter_model_id'].domain))
        self.assertIn("('phase', '=', 'three')", str(settings_fields['legacy_three_phase_meter_model_id'].domain))

        self.company.legacy_single_phase_meter_model_id = self.meter_model_three
        self.assertEqual(self.company.legacy_single_phase_meter_model_id, self.meter_model_three)
        # ORM/runtime validation remains the final guard for imports and legacy data.
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل طور غير متوافق', 'customer_number': 'CUST-PHASE-MISMATCH',
            'meter_number': 'MTR-PHASE-MISMATCH', 'phase': 'single',
            'category_id': self.category.id, 'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id, 'region_id': self.region.id,
            'area_id': self.area.id, 'company_id': self.company.id,
        })
        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('LEGACY_DEFAULT_METER_MODEL_PHASE_MISMATCH', staging.error_message)
        self.company.legacy_single_phase_meter_model_id = self.meter_model_single

    def test_customer_migration_execution_and_idempotency(self):
        """اختبار تهيئة المشترك والعداد وقراءة الافتتاح 0 وتوفّر created_reading_id."""
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': 'LEG_REG',
            'region_id': self.region.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'area',
            'legacy_code': 'LEG_AREA',
            'area_id': self.area.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'category',
            'legacy_code': 'LEG_CAT',
            'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'subscriber',
            'legacy_code': 'LEG_SUB',
            'subscriber_type_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'contract',
            'legacy_code': 'LEG_CON',
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

        staging = self.env['utility.migration.customer'].create({
            'name': 'أحمد علي (ميجريشن)',
            'customer_number': 'CUST-MIG-001',
            'meter_number': 'MTR-MIG-001',
            'last_reading': 0.0,  # Zero opening reading is VALID
            'phase': 'single',
            'legacy_region': 'LEG_REG',
            'legacy_area': 'LEG_AREA',
            'legacy_category': 'LEG_CAT',
            'legacy_subscriber_type': 'LEG_SUB',
            'legacy_contract': 'LEG_CON',
            'is_active': True,
            'company_id': self.company.id,
        })

        staging.action_import_data()
        self.assertEqual(staging.state, 'imported', staging.error_message)
        self.assertTrue(staging.created_customer_id)
        self.assertTrue(staging.created_meter_id)
        self.assertTrue(staging.created_reading_id)  # Field created_reading_id verified

        # Meter model should be set to single phase model
        self.assertEqual(staging.created_meter_id.model_id, self.meter_model_single)
        self.assertEqual(staging.created_meter_id.phase, 'single')
        self.assertEqual(staging.created_meter_id.meter_number, 'MTR-MIG-001')
        self.assertEqual(staging.created_meter_id.operational_number, 'MTR-MIG-001')

        # Opening reading value 0 is created
        self.assertEqual(staging.created_reading_id.reading_value, 0.0)
        self.assertEqual(staging.created_reading_id.reading_purpose, 'opening')
        self.assertEqual(staging.created_reading_id.reading_category, 'customer')

        # Test idempotency
        cust_id = staging.created_customer_id.id
        meter_id = staging.created_meter_id.id
        staging.state = 'draft'
        staging.action_import_data()

        self.assertEqual(staging.created_customer_id.id, cust_id)
        self.assertEqual(staging.created_meter_id.id, meter_id)
        self.assertEqual(staging.created_meter_id.operational_number, staging.meter_number)
        self.assertEqual(self.env['utility.meter'].search_count([
            ('company_id', '=', self.company.id), ('meter_number', '=', staging.meter_number),
        ]), 1)

    def test_customer_migration_links_transformer_and_default_route(self):
        """ربط العميل بمحول مرفوع مسبقاً عبر رمز المحول وإنشاء المسار الافتراضي للمحول."""
        transformer = self.env['utility.transformer'].create({
            'name': 'محول حي النور',
            'code': 'TR-NOOR-01',
            'company_id': self.company.id,
            'area_id': self.area.id,
        })
        self.assertFalse(transformer.route_ids)

        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل مرتبط بمحول',
            'customer_number': 'CUST-TR-001',
            'meter_number': 'MTR-TR-001',
            'phase': 'single',
            'region_id': self.region.id,
            'area_id': self.area.id,
            'legacy_transformer_code': 'TR-NOOR-01',
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

        staging.action_import_data()
        self.assertEqual(staging.state, 'imported', staging.error_message)
        self.assertEqual(staging.transformer_id, transformer)
        self.assertEqual(staging.created_customer_id.transformer_id, transformer)
        route = staging.created_customer_id.route_id
        self.assertTrue(route, 'يجب ربط العميل بالمسار التابع للمحول.')
        self.assertEqual(route.transformer_id, transformer)
        self.assertEqual(staging.route_id, route)

        # Idempotency: re-import must not create a duplicate route
        route_id = route.id
        staging.state = 'draft'
        staging.action_import_data()
        self.assertEqual(staging.state, 'imported', staging.error_message)
        self.assertEqual(staging.created_customer_id.route_id.id, route_id)
        self.assertEqual(self.env['utility.route'].search_count([
            ('transformer_id', '=', transformer.id),
        ]), 1)

    def test_customer_migration_applies_current_reading_and_date(self):
        """القراءة الحالية وتاريخ آخر قراءة يُسجَّلان على العداد وعلى الحساب بعد التوريد."""
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل بقراءة حالية',
            'customer_number': 'CUST-CUR-001',
            'meter_number': 'MTR-CUR-001',
            'phase': 'single',
            'region_id': self.region.id,
            'area_id': self.area.id,
            'current_reading': 1234.5,
            'last_reading_date': '2024-05-31',
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })
        self.assertTrue(staging.has_current_reading)

        staging.action_import_data()
        self.assertEqual(staging.state, 'imported', staging.error_message)

        expected_date = fields.Datetime.to_datetime('2024-05-31')
        customer = staging.created_customer_id
        meter = staging.created_meter_id
        self.assertEqual(customer.last_reading_value, 1234.5)
        self.assertEqual(meter.last_reading_value, 1234.5)
        self.assertEqual(customer.last_reading_date, expected_date)
        self.assertEqual(meter.last_read_date, expected_date)

    def test_customer_migration_missing_transformer_code_is_explicit(self):
        """رمز محول غير مرفوع مسبقاً يوقف المطابقة والتوريد برسالة صريحة."""
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل برمز محول مفقود',
            'customer_number': 'CUST-TR-MISSING',
            'meter_number': 'MTR-TR-MISSING',
            'phase': 'single',
            'region_id': self.region.id,
            'area_id': self.area.id,
            'legacy_transformer_code': 'TR-DOES-NOT-EXIST',
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

        staging.action_map_codes(strict=False)
        self.assertIn('MISSING_TRANSFORMER_CODE', staging.error_message)

        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('MISSING_TRANSFORMER_CODE', staging.error_message)

    def test_customer_migration_uses_configured_default_not_phase_search(self):
        """الموديلات الأخرى ذات الطور نفسه لا تسبب غموضًا."""
        other_model = self.env['utility.meter.model'].create({
            'name': 'عداد أحادي ثانوي',
            'code': 'MDL-1P-2',
            'phase': 'single',
        })

        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل موديل غامض',
            'customer_number': 'CUST-AMB-001',
            'meter_number': 'MTR-AMB-001',
            'phase': 'single',
            'is_active': True,
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'region_id': self.region.id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        })

        staging.action_import_data()
        self.assertEqual(staging.state, 'imported', staging.error_message)
        self.assertEqual(staging.created_meter_id.model_id, self.meter_model_single)
        self.assertNotEqual(staging.created_meter_id.model_id, other_model)

    def test_customer_migration_missing_default_model_is_explicit(self):
        self.company.legacy_single_phase_meter_model_id = False
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل بلا موديل افتراضي', 'customer_number': 'CUST-NO-DEFAULT',
            'meter_number': 'MTR-NO-DEFAULT', 'phase': 'single',
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'region_id': self.region.id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        })
        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('LEGACY_SINGLE_PHASE_METER_MODEL_NOT_CONFIGURED', staging.error_message)

    def test_feeder_migration_execution(self):
        """اختبار تهيئة الفيدر وعداد الرصد وقراءة الافتتاح الصفرية."""
        staging_feeder = self.env['utility.migration.feeder'].create({
            'name': 'فيدر المصانع الشمالي',
            'feeder_code': 'FDR-NORTH-01',
            'meter_number': 'MTR-FDR-001',
            'current_reading': 0.0,
            'company_id': self.company.id,
        })

        staging_feeder.action_import_data()
        self.assertEqual(staging_feeder.state, 'imported')
        self.assertTrue(staging_feeder.created_feeder_id)
        self.assertTrue(staging_feeder.created_meter_id)
        self.assertEqual(staging_feeder.created_meter_id.meter_number, 'MTR-FDR-001')
        self.assertEqual(staging_feeder.created_meter_id.operational_number, 'MTR-FDR-001')
        self.assertTrue(staging_feeder.created_reading_id)

        self.assertEqual(staging_feeder.created_reading_id.meter_id, staging_feeder.created_meter_id)
        self.assertEqual(staging_feeder.created_reading_id.feeder_id, staging_feeder.created_feeder_id)
        self.assertEqual(staging_feeder.created_reading_id.reading_category, 'feeder')
        self.assertEqual(staging_feeder.created_reading_id.reading_purpose, 'opening')
        self.assertEqual(staging_feeder.created_reading_id.reading_value, 0.0)

        feeder_id = staging_feeder.created_feeder_id.id
        meter_id = staging_feeder.created_meter_id.id
        staging_feeder.state = 'draft'
        staging_feeder.action_import_data()
        self.assertEqual(staging_feeder.created_feeder_id.id, feeder_id)
        self.assertEqual(staging_feeder.created_meter_id.id, meter_id)
        self.assertEqual(staging_feeder.created_meter_id.operational_number, staging_feeder.meter_number)
        self.assertEqual(self.env['utility.meter'].search_count([
            ('company_id', '=', self.company.id), ('meter_number', '=', staging_feeder.meter_number),
        ]), 1)

    def test_feeder_production_area_classification_is_explicit_and_idempotent(self):
        staging = self.env['utility.migration.feeder'].create({
            'name': 'فيدر إنتاج صريح',
            'feeder_code': 'FDR-PROD-01',
            'meter_number': 'MTR-PROD-001',
            'is_production_area': True,
            'company_id': self.company.id,
        })
        staging.action_import_data()
        self.assertEqual(staging.state, 'imported')
        feeder_id = staging.created_feeder_id.id
        self.assertEqual(staging.created_feeder_id.feeder_type, 'production_area')

        staging.state = 'draft'
        staging.action_import_data()
        self.assertEqual(staging.created_feeder_id.id, feeder_id)
        self.assertEqual(self.env['utility.feeder'].search_count([('code', '=', 'FDR-PROD-01'), ('company_id', '=', self.company.id)]), 1)

    def test_transformer_migration_execution(self):
        """اختبار تهيئة المحول وتحديد الهوية المرجعية واختيار قراءة بداية الاشتراك (150.5)."""
        staging_feeder = self.env['utility.migration.feeder'].create({
            'name': 'فيدر الخلايا',
            'feeder_code': 'FDR-CELL-01',
            'meter_number': 'MTR-CELL-001',
            'company_id': self.company.id,
        })
        staging_feeder.action_import_data()

        staging_trans = self.env['utility.migration.transformer'].create({
            'name': 'محول حي السلام',
            'reference': 'TR-SALAM-01',
            'meter_number': 'MTR-TR-001',
            'cell_meter_number': 'MTR-CELL-001',
            'opening_reading': 150.5,
            'region_id': self.region.id,
            'area_id': self.area.id,
            'company_id': self.company.id,
        })

        staging_trans.action_import_data()
        self.assertEqual(staging_trans.state, 'imported')
        self.assertTrue(staging_trans.created_transformer_id)
        self.assertTrue(
            staging_trans.created_transformer_id.route_ids,
            'يجب إنشاء مسار افتراضي لكل محول عام عند التهيئة.',
        )
        self.assertEqual(staging_trans.created_transformer_id.feeder_id, staging_feeder.created_feeder_id)
        self.assertEqual(staging_trans.created_meter_id.meter_number, 'MTR-TR-001')
        self.assertEqual(staging_trans.created_meter_id.operational_number, 'MTR-TR-001')
        self.assertEqual(staging_trans.created_reading_id.reading_category, 'transformer')
        self.assertEqual(staging_trans.created_reading_id.reading_value, 150.5)

        transformer_id = staging_trans.created_transformer_id.id
        meter_id = staging_trans.created_meter_id.id
        staging_trans.state = 'draft'
        staging_trans.action_import_data()
        self.assertEqual(staging_trans.created_transformer_id.id, transformer_id)
        self.assertEqual(staging_trans.created_meter_id.id, meter_id)
        self.assertEqual(staging_trans.created_meter_id.operational_number, staging_trans.meter_number)
        self.assertEqual(self.env['utility.meter'].search_count([
            ('company_id', '=', self.company.id), ('meter_number', '=', staging_trans.meter_number),
        ]), 1)

    def test_legacy_operational_number_is_unique_per_company(self):
        """الرقم التشغيلي يساوي رقم العداد، وفريد داخل الشركة فقط."""
        meter_model = self.meter_model_single
        self.env['utility.meter'].create({
            'meter_number': 'MTR-UNIQUE-001', 'operational_number': 'MTR-UNIQUE-001',
            'model_id': meter_model, 'company_id': self.company.id,
        })
        with self.assertRaises(Exception):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-UNIQUE-002', 'operational_number': 'MTR-UNIQUE-001',
                'model_id': meter_model, 'company_id': self.company.id,
            })
        other_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-UNIQUE-001', 'operational_number': 'MTR-UNIQUE-001',
            'model_id': meter_model, 'company_id': self.other_company.id,
        })
        self.assertEqual(other_meter.company_id, self.other_company)

    def test_wizard_blank_vs_zero_and_presence_semantics(self):
        """اختبار دقة معالج الاستيراد في التمييز بين الخلية الفارغة وقيمة الصفر."""
        wizard = self.env['utility.migration.import.wizard'].create({
            'import_type': 'transformer',
            'import_file': base64.b64encode(b'dummy_excel_data'),
            'file_name': 'test.xlsx'
        })
        # 1. Blank cell parsing
        self.assertFalse(wizard._has_cell_value(None))
        self.assertFalse(wizard._has_cell_value('   '))
        self.assertTrue(wizard._has_cell_value(0))
        self.assertTrue(wizard._has_cell_value('0.0'))
        self.assertTrue(wizard._has_cell_value('150.5'))

        # 2. Invalid numeric parsing raises ValidationError
        with self.assertRaises(ValidationError):
            wizard.parse_float('15O.5')

        # 3. Staging model creation without reading fields maintains has_opening_reading = False
        staging_blank = self.env['utility.migration.transformer'].create({
            'name': 'محول فارغ القراءة',
            'reference': 'TR-BLANK-01',
            'company_id': self.company.id,
        })
        self.assertFalse(staging_blank.has_current_reading)
        self.assertFalse(staging_blank.has_opening_reading)
        self.assertIsNone(staging_blank._get_staging_opening_reading_value())

        # 4. Staging model creation with opening_reading = 150.5 sets has_opening_reading = True
        staging_val = self.env['utility.migration.transformer'].create({
            'name': 'محول بقراءة افتتاحية',
            'reference': 'TR-VAL-01',
            'opening_reading': 150.5,
            'company_id': self.company.id,
        })
        self.assertTrue(staging_val.has_opening_reading)
        self.assertEqual(staging_val._get_staging_opening_reading_value(), 150.5)

    def test_upload_mapping_flexible_vs_import_data_strict(self):
        """اختبار مرونة مطابقة الرموز في الـ Upload مقابل الصرامة التامة عند الاعتماد."""
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل بترميز مفقود',
            'customer_number': 'CUST-MISSING-01',
            'meter_number': 'MTR-MISSING-01',
            'legacy_region': 'LEG_UNKNOWN_REG',
            'company_id': self.company.id,
        })

        # 1. Upload-time mapping (strict=False) records error message without raising exception
        staging.action_map_codes(strict=False)
        self.assertIn('MISSING_REGION_MAPPING', staging.error_message)

        # 2. Strict mapping raises ValidationError directly
        with self.assertRaises(ValidationError):
            staging.action_map_codes(strict=True)

        # 3. Business import (action_import_data) catches the error, sets state to 'error' and updates error_message
        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('MISSING_REGION_MAPPING', staging.error_message)
