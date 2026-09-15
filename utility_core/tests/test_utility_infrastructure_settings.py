import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from ..adapters.workflow.local import LocalWorkflowAdapter
from ..adapters.workflow.temporal import TemporalWorkflowAdapter
from ..adapters.media.attachment import AttachmentMediaAdapter
from ..adapters.media.filesystem import FilesystemMediaAdapter
from ..adapters.media.s3 import S3MediaAdapter


class TestUtilityInfrastructureSettings(TransactionCase):

    def setUp(self):
        super().setUp()
        self.WorkflowService = self.env['utility.workflow.service']
        self.MediaService = self.env['utility.media.service']
        self.ConfigParam = self.env['ir.config_parameter'].sudo()

    def test_01_default_infrastructure_adapters(self):
        """1. اختبار الإعدادات الافتراضية للبنية التحتية (Local Workflow & Attachment Media)"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'local')
        self.ConfigParam.set_param('utility.media_backend', 'attachment')

        wf_adapter = self.WorkflowService._get_workflow_adapter()
        self.assertIsInstance(wf_adapter, LocalWorkflowAdapter)

        media_adapter = self.MediaService.get_media_adapter()
        self.assertIsInstance(media_adapter, AttachmentMediaAdapter)

    def test_02_temporal_workflow_adapter_validation_and_no_silent_fallback(self):
        """2. اختبار فحص إعدادات Temporal ومنع silent fallback وحظر تفعيل الـ Placeholder"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'temporal')
        self.ConfigParam.set_param('utility.temporal_target_host', '')

        # يجب أن يرفع UserError بدلاً من العودة إلى LocalWorkflowAdapter صمتاً
        with self.assertRaises(UserError):
            self.WorkflowService._get_workflow_adapter()

        # إدخال عنوان خادم Temporal - يرفع UserError أيضاً لأن المحول في مرحلة Placeholder وغير جاهز للإنتاج
        self.ConfigParam.set_param('utility.temporal_target_host', 'localhost:7233')
        with self.assertRaises(UserError):
            self.WorkflowService._get_workflow_adapter()

    def test_03_filesystem_media_adapter_validation(self):
        """3. اختبار فحص إعدادات التخزين على القرص Filesystem"""
        self.ConfigParam.set_param('utility.media_backend', 'filesystem')
        self.ConfigParam.set_param('utility.filesystem_storage_path', '')

        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        self.ConfigParam.set_param('utility.filesystem_storage_path', '/tmp/utility_media_test')
        media_adapter = self.MediaService.get_media_adapter()
        self.assertIsInstance(media_adapter, FilesystemMediaAdapter)

    def test_04_s3_media_adapter_validation(self):
        """4. اختبار فحص إعدادات التخزين السحابي S3 وحظر تفعيل الـ Placeholder"""
        self.ConfigParam.set_param('utility.media_backend', 's3')
        self.ConfigParam.set_param('utility.s3_endpoint_url', '')

        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        self.ConfigParam.set_param('utility.s3_endpoint_url', 'https://s3.example.com')
        self.ConfigParam.set_param('utility.s3_bucket_name', 'utility-bucket')
        self.ConfigParam.set_param('utility.s3_access_key', 'AKIAIOSFODNN7EXAMPLE')
        self.ConfigParam.set_param('utility.s3_secret_key', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')

        # الـ Resolver يرفع UserError لأن المحول في مرحلة Placeholder وغير جاهز للإنتاج
        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        # اختبار أسبقية متغيرات البيئة OS Environment Variables مباشرة على فئة المحول (دون المرور بالـ Resolver الحاظر)
        import os
        os.environ['S3_ACCESS_KEY'] = 'ENV_ACCESS_KEY'
        os.environ['S3_SECRET_KEY'] = 'ENV_SECRET_KEY'
        env_adapter = S3MediaAdapter(self.env)
        self.assertEqual(env_adapter.access_key, 'ENV_ACCESS_KEY')
        self.assertEqual(env_adapter.secret_key, 'ENV_SECRET_KEY')
        del os.environ['S3_ACCESS_KEY']
        del os.environ['S3_SECRET_KEY']

    def test_05_res_config_settings_v1_stabilization_constraints(self):
        """5. اختبار قيود شاشة الإعدادات لمنع تفعيل الأنظمة التي في مرحلة Placeholder (Temporal / S3)"""
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create({
                'workflow_backend': 'temporal',
                'temporal_target_host': 'localhost:7233',
            })

        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create({
                'media_backend': 's3',
                's3_endpoint_url': 'https://s3.example.com',
                's3_bucket_name': 'test-bucket',
                's3_access_key': 'key',
                's3_secret_key': 'secret',
            })

    def test_06_filesystem_adapter_partitioning(self):
        """6. اختبار تقسيم مسار التخزين على القرص باستخدام UUID للأصل"""
        import os
        import tempfile
        test_dir = tempfile.mkdtemp()
        self.ConfigParam.set_param('utility.media_backend', 'filesystem')
        self.ConfigParam.set_param('utility.filesystem_storage_path', test_dir)

        adapter = self.MediaService.get_media_adapter()
        attachment = adapter.store(
            file_data=b'test binary data',
            filename='test_photo.jpg',
            mimetype='image/jpeg',
            metadata={'res_model': 'utility.media.asset', 'res_id': 99, 'asset_uuid': 'uuid-12345'}
        )
        self.assertTrue(attachment.url.startswith('file://'))
        expected_file_path = os.path.join(test_dir, 'uuid-12345', 'test_photo.jpg')
        self.assertEqual(attachment.url.replace('file://', ''), expected_file_path)
        self.assertTrue(os.path.exists(expected_file_path))

    def test_07_media_service_dynamic_storage_backend_metadata(self):
        """7. اختبار تعيين خيار التخزين ديناميكياً في السجل (storage_backend)"""
        self.ConfigParam.set_param('utility.media_backend', 'attachment')
        valid_png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        )
        asset = self.MediaService.store_media(
            file_data=valid_png,
            filename='test_dynamic.jpg',
            mimetype='image/jpeg'
        )
        self.assertEqual(asset.storage_backend, 'attachment')

    def test_07b_invalid_media_is_rejected_without_raw_fallback(self):
        self.ConfigParam.set_param('utility.media_backend', 'attachment')
        with self.assertRaises(ValidationError):
            self.MediaService.store_media(
                file_data=b'not-an-image',
                filename='invalid.jpg',
                mimetype='image/jpeg'
            )

    def test_08_resolver_defense_in_depth_protection(self):
        """8. اختبار حماية التعديل المباشر لمعلمات القاعدة لمنع تشغيل Placeholder Adapters"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'temporal')
        self.ConfigParam.set_param('utility.temporal_target_host', 'localhost:7233')
        with self.assertRaises(UserError):
            self.WorkflowService._get_workflow_adapter()

        self.ConfigParam.set_param('utility.media_backend', 's3')
        self.ConfigParam.set_param('utility.s3_endpoint_url', 'https://s3.example.com')
        self.ConfigParam.set_param('utility.s3_bucket_name', 'test-bucket')
        self.ConfigParam.set_param('utility.s3_access_key', 'key')
        self.ConfigParam.set_param('utility.s3_secret_key', 'secret')
        with self.assertRaises(UserError):
            self.MediaService.get_media_adapter()

        # إعادة الإعدادات الافتراضية
        self.ConfigParam.set_param('utility.workflow_adapter', 'local')
        self.ConfigParam.set_param('utility.media_backend', 'attachment')

    def test_09_populate_missing_defaults(self):
        """9. اختبار زر توليد وتعبئة الحسابات والمنتجات وموديلات العدادات الافتراضية الناقصة تلقائياً."""
        company = self.env.company

        # Clear settings to simulate empty company
        company.electricity_product_id = False
        company.discount_product_id = False
        company.opening_journal_id = False
        company.opening_clearing_account_id = False
        company.legacy_single_phase_meter_model_id = False
        company.legacy_three_phase_meter_model_id = False

        settings = self.env['res.config.settings'].create({})
        res = settings.action_populate_missing_defaults()

        self.assertEqual(res['type'], 'ir.actions.client')
        self.assertEqual(res['tag'], 'display_notification')
        self.assertTrue(company.electricity_product_id)
        self.assertTrue(company.discount_product_id)
        self.assertTrue(company.opening_journal_id)
        self.assertEqual(company.opening_journal_id.type, 'general')
        self.assertTrue(company.opening_clearing_account_id)
        self.assertEqual(settings.opening_journal_id, company.opening_journal_id)
        self.assertEqual(settings.opening_clearing_account_id, company.opening_clearing_account_id)
        self.assertTrue(company.legacy_single_phase_meter_model_id)
        self.assertTrue(company.legacy_three_phase_meter_model_id)
        self.assertEqual(company.legacy_single_phase_meter_model_id.phase, 'single')
        self.assertEqual(company.legacy_three_phase_meter_model_id.phase, 'three')
