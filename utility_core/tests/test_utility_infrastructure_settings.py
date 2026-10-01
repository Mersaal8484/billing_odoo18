import base64
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from ..adapters.workflow.local import LocalWorkflowAdapter
from ..adapters.workflow.temporal import TemporalWorkflowAdapter
from ..adapters.workflow.queue_job import QueueJobWorkflowAdapter, _build_geo_channel
from ..adapters.media.attachment import AttachmentMediaAdapter
from ..adapters.media.filesystem import FilesystemMediaAdapter


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

    def test_05_res_config_settings_v1_stabilization_constraints(self):
        """5. اختبار قيود شاشة الإعدادات لمنع تفعيل الأنظمة التي في مرحلة Placeholder (Temporal)"""
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create({
                'workflow_backend': 'temporal',
                'temporal_target_host': 'localhost:7233',
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

        self.ConfigParam.set_param('utility.media_backend', 'unknown_backend')
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
        yer = self.env.ref('base.YER', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'YER')], limit=1)
        self.assertTrue(yer.active)
        self.assertEqual(company.currency_id, yer)

    # =========================================================================
    # Queue Job Adapter Tests
    # =========================================================================

    def test_10_geo_channel_routing_logic(self):
        """اختبار منطق توزيع القنوات الجغرافية لـ OCA Queue Job"""
        # قناة بناءً على region_id
        self.assertEqual(_build_geo_channel({'region_id': 5}), 'utility_region.5')
        # قناة بناءً على branch_id عند غياب region_id
        self.assertEqual(_build_geo_channel({'branch_id': 12}), 'utility_region.12')
        # قناة region_id مقدمة على branch_id
        self.assertEqual(_build_geo_channel({'region_id': 3, 'branch_id': 12}), 'utility_region.3')
        # قناة افتراضية عند غياب المنطقة
        self.assertEqual(_build_geo_channel({}), 'root')
        self.assertEqual(_build_geo_channel(None), 'root')
        # قناة fallback مخصصة
        self.assertEqual(_build_geo_channel({}, fallback_channel='billing_queue'), 'billing_queue')

    def test_11_queue_job_resolver_when_module_present(self):
        """اختبار أن resolver يعيد QueueJobWorkflowAdapter عند اختيار queue_job"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'queue_job')
        # نحاكي queue.job كمثبتة
        with patch.object(
            type(self.env), '__contains__',
            lambda self_env, model: True if model == 'queue.job' else model in self_env.registry,
        ):
            adapter = self.WorkflowService._get_workflow_adapter()
            self.assertIsInstance(adapter, QueueJobWorkflowAdapter)

    def test_12_queue_job_resolver_when_module_absent(self):
        """اختبار أن QueueJobWorkflowAdapter يرفع UserError عند غياب queue_job"""
        self.ConfigParam.set_param('utility.workflow_adapter', 'queue_job')
        # queue.job غير مثبتة -> يجب رفع UserError
        with patch.object(
            type(self.env), '__contains__',
            lambda self_env, model: False if model == 'queue.job' else model in self_env.registry,
        ):
            with self.assertRaises(UserError):
                self.WorkflowService._get_workflow_adapter()

    def test_13_queue_job_dispatch_idempotency(self):
        """اختبار عدم التكرار وإنشاء سجل الأمر بالمحول الموزع"""
        # نحاكي queue.job و with_delay
        mock_job = MagicMock()
        mock_job.uuid = 'test-job-uuid-001'
        mock_delayed = MagicMock()
        mock_delayed._execute_via_queue_job_handler = MagicMock(return_value=mock_job)

        period = self.env['date.range'].search([], limit=1)
        if not period:
            self.skipTest('لا توجد فترة date.range للاختبار')

        with patch.object(
            type(self.env), '__contains__',
            lambda self_env, model: True if model == 'queue.job' else model in self_env.registry,
        ), patch.object(
            type(self.env['utility.workflow.command']), 'with_delay',
            return_value=mock_delayed,
        ):
            adapter = QueueJobWorkflowAdapter(self.env)
            cmd1 = adapter.dispatch(
                workflow_type='open_reading_window',
                reference_model='date.range',
                reference_id=period.id,
                payload={'region_id': 7},
                idempotency_key='TEST-QJ-IDEMPOTENCY-001',
            )
            cmd2 = adapter.dispatch(
                workflow_type='open_reading_window',
                reference_model='date.range',
                reference_id=period.id,
                payload={'region_id': 7},
                idempotency_key='TEST-QJ-IDEMPOTENCY-001',
            )
            # نفس السجل (idempotent)
            self.assertEqual(cmd1.id, cmd2.id)
            self.assertEqual(cmd1.backend, 'queue_job')
