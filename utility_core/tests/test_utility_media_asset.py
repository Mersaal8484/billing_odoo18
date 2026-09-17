import base64
import os
import tempfile
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError


class TestUtilityMediaAsset(TransactionCase):

    def setUp(self):
        super().setUp()
        self.MediaAsset = self.env['utility.media.asset']
        self.MediaService = self.env['utility.media.service']
        self.BatchService = self.env['utility.reading.batch.service']
        self.WorkflowService = self.env['utility.workflow.service']
        self.Region = self.env['utility.region']
        self.Meter = self.env['utility.meter']
        self.Customer = self.env['utility.customer']
        self.DateRange = self.env['date.range']
        self.Batch = self.env['utility.reading.batch']
        self.BatchLine = self.env['utility.reading.batch.line']

        # تجهيز صورة تجريبية (100x100 Red Pixel JPEG)
        self.sample_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        self.sample_bytes = base64.b64decode(self.sample_base64)

        self.region = self.Region.create({
            'name': 'منطقة وسائط A1 Final',
            'code': 'REG-MEDIA-A1F',
            'type': 'region',
            'recurring_rule_type': 'monthly',
        })

    def test_01_media_storage_adapter_and_asset_creation(self):
        """1. اختبار تخزين صورة رقمية وتوليد النسخ الثلاث (Original, Review, Thumbnail) عبر Media Service"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_01.jpg",
            mimetype="image/png",
            asset_type="meter_reading"
        )

        self.assertTrue(asset)
        self.assertEqual(asset.state, 'ready')
        self.assertTrue(asset.asset_uuid)
        self.assertTrue(asset.sha256)
        self.assertEqual(asset.storage_backend, 'attachment')
        self.assertTrue(asset.original_attachment_id)
        self.assertTrue(asset.review_attachment_id)
        self.assertTrue(asset.thumbnail_attachment_id)

        # استرجاع المحتوى عبر Adapter
        retrieved_orig = self.MediaService.retrieve_media(asset, variant='original')
        self.assertEqual(retrieved_orig, self.sample_bytes)

    def test_01b_invalid_variant_is_rejected_by_the_adapter_contract(self):
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename='meter_read_variant.jpg',
            mimetype='image/png'
        )
        adapter = self.MediaService.get_media_adapter()
        with self.assertRaises(ValueError):
            adapter.retrieve(asset, variant='unsupported')

    def test_02_duplicate_media_binary_deduplication(self):
        """2. اختبار إعادة استخدام المرفق الثنائي دون إنشاء سجلات مرفقات متكررة مع إنشاء أصل مستقل لكل إثبات"""
        asset1 = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_dup1.jpg",
            mimetype="image/png"
        )

        asset2 = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_dup2.jpg",
            mimetype="image/png"
        )

        # إنشاء سجل أصل إثبات منفصل لكل قراءة مع إعادة استخدام المرفق الثنائي الأصلي لعدم تكرار التخزين
        self.assertNotEqual(asset1.id, asset2.id)
        self.assertEqual(asset1.original_attachment_id.id, asset2.original_attachment_id.id)

    def test_03_canonical_image_asset_id_and_meter_image_non_stored_facade(self):
        """3. اختبار الحقل الأصيل image_asset_id والتوافقية غير المخزنة meter_image بدون تكرار الثنائي"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="meter_read_canonical.jpg",
            mimetype="image/png"
        )

        customer = self.Customer.create({
            'name': 'مشترك الوسائط Canonical A1 Final',
            'customer_number': 'CUST-CANON-F',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-CANON-F',
            'customer_id': customer.id,
        })

        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 100.0,
            'image_asset_id': asset.id,
        })

        self.assertEqual(reading.image_asset_id.id, asset.id)
        # التحقق من أن meter_image يقرأ تلقائياً عبر compute من الأصل الرقمي
        self.assertTrue(reading.meter_image)

    def test_03b_draft_reading_can_persist_image_asset_through_inverse(self):
        """3b. رفع صورة على قراءة مسودة يجب أن يحفظ image_asset_id دون كسر حماية الحالة"""
        customer = self.Customer.create({
            'name': 'مشترك الصورة المسودة',
            'customer_number': 'CUST-DRAFT-IMG',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-DRAFT-IMG',
            'customer_id': customer.id,
        })

        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 42.0,
            'state': 'draft',
        })
        reading.write({'meter_image': self.sample_base64})

        self.assertTrue(reading.image_asset_id)
        self.assertEqual(reading.state, 'draft')
        self.assertTrue(reading.meter_image)

        reading.action_submit_review()
        self.assertEqual(reading.state, 'under_review')

    def test_03c_reading_create_with_meter_image_upload_creates_asset(self):
        """3c. إنشاء قراءة مع meter_image_upload ينشئ أصل وسائط ويربطه تلقائياً"""
        customer = self.Customer.create({
            'name': 'مشترك رفع الصورة إنشاء',
            'customer_number': 'CUST-CREATE-IMG',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-CREATE-IMG',
            'customer_id': customer.id,
        })

        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 55.0,
            'meter_image_upload': self.sample_base64,
            'meter_image_filename': 'test_upload.png',
        })

        self.assertTrue(reading.image_asset_id, 'يجب إنشاء image_asset_id تلقائياً عند الإنشاء مع meter_image_upload')
        self.assertEqual(reading.image_state, 'pending')
        self.assertTrue(reading.meter_image_url)
        self.assertEqual(reading.image_asset_id.reading_id, reading)

    def test_03d_reading_write_with_meter_image_upload_creates_asset(self):
        """3d. كتابة meter_image_upload عبر write على قراءة مسودة تنشئ أصل وسائط وتربطه"""
        customer = self.Customer.create({
            'name': 'مشترك رفع الصورة كتابة',
            'customer_number': 'CUST-WRITE-IMG',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-WRITE-IMG',
            'customer_id': customer.id,
        })

        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 70.0,
            'state': 'draft',
        })
        self.assertFalse(reading.image_asset_id)

        reading.write({
            'meter_image_upload': self.sample_base64,
            'meter_image_filename': 'test_write.png',
        })

        self.assertTrue(reading.image_asset_id, 'يجب إنشاء image_asset_id عند كتابة meter_image_upload')
        self.assertEqual(reading.image_state, 'pending')
        self.assertTrue(reading.meter_image_url)

    def test_03e_reading_newid_onchange_meter_image_upload(self):
        """3e. استدعاء onchange على سجل افتراضي NewId لا يرمي خطأ ويجهز image_asset_id"""
        customer = self.Customer.create({
            'name': 'مشترك أونشينج افتراضي',
            'customer_number': 'CUST-NEWID-IMG',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-NEWID-IMG',
            'customer_id': customer.id,
        })

        # محاكاة فتح شاشة الإدخال قبل الحفظ (سجل NewId)
        new_reading = self.env['utility.reading'].new({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 80.0,
            'state': 'draft',
            'meter_image_upload': self.sample_base64,
        })
        new_reading._onchange_meter_image_upload()

        self.assertTrue(new_reading.image_asset_id, 'يجب تعبئة image_asset_id في الذاكرة أثناء onchange')
        self.assertEqual(new_reading.image_state, 'pending')
        self.assertFalse(new_reading.meter_image_upload)

    def test_03f_existing_reading_onchange_and_save_persists_image(self):
        """3f. رفع صورة عبر onchange على قراءة موجودة وحفظها يضمن بقاء الصورة وعدم اختفائها"""
        customer = self.Customer.create({
            'name': 'مشترك فحص حفظ الصورة',
            'customer_number': 'CUST-SAVE-IMG',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-SAVE-IMG',
            'customer_id': customer.id,
        })
        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 120.0,
            'state': 'draft',
        })
        self.assertFalse(reading.image_asset_id)
        self.assertEqual(reading.meter_image_url, '')

        # محاكاة إرسال الفورم في الواجهة: تعديل الحقل ثم تشغيل onchange
        reading.meter_image_upload = self.sample_base64
        reading._onchange_meter_image_upload()

        # التحقق من أن الصورة جهزت ورابط المعاينة فعال
        self.assertTrue(reading.image_asset_id)
        self.assertTrue(reading.meter_image_url)
        self.assertIn(reading.image_asset_id.asset_uuid, reading.meter_image_url)

        # محاكاة نقر المستخدم على زر الحفظ (Save): إرسال القيم المتبقية في الفورم
        reading.write({
            'image_asset_id': reading.image_asset_id.id,
            'meter_image_upload': False,
        })

        # إعادة قراءة السجل من قاعدة البيانات للتأكد التام من استقرار الصورة وعدم اختفائها
        reading.invalidate_recordset()
        reloaded = self.env['utility.reading'].browse(reading.id)
        self.assertTrue(reloaded.image_asset_id, 'يجب أن يبقى الأصل الرقمي مربوطاً بعد الحفظ')
        self.assertTrue(reloaded.meter_image_url, 'يجب أن يبقى رابط المعاينة فعالاً بعد الحفظ')
        self.assertEqual(reloaded.image_asset_id.reading_id, reloaded)

    def test_04_decoupled_batch_processing_retry_and_under_review_state(self):
        """4. اختبار معالجة الدفعة وحماية التكرار والصور المصحوبة تحت المراجعة (under_review)"""
        period = self.DateRange.create({
            'name': 'فترة الوسائط A1 Final',
            'period_code': 'R-MEDIA-A1F-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك الدفعة A1 Final',
            'customer_number': 'CUST-BATCH-A1F',
            'region_id': self.region.id,
        })

        meter = self.Meter.create({
            'meter_number': 'MTR-BATCH-A1F',
            'customer_id': customer.id,
        })

        payload = {
            'readings': [
                {
                    'seq': 1,
                    'meter_number': 'MTR-BATCH-A1F',
                    'reading_value': 250.0,
                    'image_filename': 'img1.png',
                },
                {
                    'seq': 2,
                    'meter_number': 'MTR-INVALID-99',
                    'reading_value': 300.0,
                    'image_filename': 'img2.png',
                }
            ]
        }
        json_b64 = base64.b64encode(bytes(str(payload).replace("'", '"'), 'utf-8')).decode('utf-8')

        batch = self.Batch.create({
            'name': 'دفعة A1 Final عازلة للأخطاء',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        self.assertTrue(batch.batch_uuid)

        # رفع أصل رقمي مسبق مرتبط بالدفعة باسم img1.png
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="img1.png",
            mimetype="image/png",
            batch_id=batch.id,
            asset_type="meter_reading"
        )

        # تأكيد الدفعة وتفويض الأمر عبر Workflow Command
        batch.action_confirm()

        # التحقق من أن حالة القراءة المصحوبة بصورة أصبحت under_review لمراجعة الصورة
        reading = self.env['utility.reading'].search([('batch_id', '=', batch.id)], limit=1)
        self.assertTrue(reading)
        self.assertEqual(reading.state, 'under_review')

    def test_05_user_media_access_security(self):
        """5. اختبار فحص الأمن والتحقق من صلاحية الوصول الرقمي للأصل"""
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="security_test.jpg",
            mimetype="image/png"
        )
        self.assertTrue(asset.check_user_access_security(self.env.user))

    def test_05b_user_media_access_default_deny_when_region_unresolved(self):
        """5b. الأصل الرقمي المرتبط بقراءة بلا منطقة قابلة للحل يجب أن يُرفض."""
        customer = self.Customer.create({
            'name': 'مشترك وسائط بلا منطقة',
            'customer_number': 'CUST-MEDIA-NOREG',
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-MEDIA-NOREG',
            'customer_id': customer.id,
        })
        reading = self.env['utility.reading'].create({
            'meter_id': meter.id,
            'account_id': customer.id,
            'reading_value': 88.0,
        })
        asset = self.MediaService.store_media(
            file_data=self.sample_bytes,
            filename="security_default_deny.jpg",
            mimetype="image/png",
            reading_id=reading.id,
        )
        scoped_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'مستخدم وسائط مقيد',
            'login': 'media.scope.05b@example.com',
            'email': 'media.scope.05b@example.com',
            'assigned_region_ids': [(6, 0, [self.region.id])],
        })
        with self.assertRaises(AccessError):
            asset.check_user_access_security(scoped_user)

    def test_06_duplicate_confirm_returns_previous_command_result_without_validation_error(self):
        """6. اختبار أن التأكيد المزدوج يعيد نتيجة الأمر السابق دون رفع ValidationError"""
        period = self.DateRange.create({
            'name': 'فترة التكرار 06',
            'period_code': 'R-MEDIA-06-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك التكرار 06',
            'customer_number': 'CUST-DUP-06',
            'region_id': self.region.id,
        })
        meter = self.Meter.create({
            'meter_number': 'MTR-DUP-06',
            'customer_id': customer.id,
        })

        payload = {
            'readings': [
                {'seq': 1, 'meter_number': 'MTR-DUP-06', 'reading_value': 120.0}
            ]
        }
        json_b64 = base64.b64encode(bytes(str(payload).replace("'", '"'), 'utf-8')).decode('utf-8')

        batch = self.Batch.create({
            'name': 'دفعة التكرار الحتمي 06',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        # التأكيد الأول
        res1 = batch.action_confirm()
        cmd_key = f"READING-BATCH:{batch.batch_uuid}"
        cmd1 = self.env['utility.workflow.command'].search([('idempotency_key', '=', cmd_key)], limit=1)
        self.assertTrue(cmd1)
        self.assertEqual(cmd1.state, 'executed')

        # النقر المزدوج على التأكيد مرة ثانية يرجع نتيجة الكاش الحتمي دون رفع ValidationError ودون تكرار الأمر
        res2 = batch.action_confirm()
        cmds = self.env['utility.workflow.command'].search([('idempotency_key', '=', cmd_key)])
        self.assertEqual(len(cmds), 1)

    def test_07_partial_batch_retry_processes_only_failed_lines_and_converts_to_done(self):
        """7. اختبار إعادة المحاولة للدفعات الجزئية مع معالجة الأسطر الفاشلة فقط دون تكرار الأسطر المكتملة"""
        period = self.DateRange.create({
            'name': 'فترة الإعادة الجزئية 07',
            'period_code': 'R-MEDIA-07-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        customer = self.Customer.create({
            'name': 'مشترك الإعادة الجزئية 07',
            'customer_number': 'CUST-RETRY-07',
            'region_id': self.region.id,
        })
        meter1 = self.Meter.create({
            'meter_number': 'MTR-RETRY-07A',
            'customer_id': customer.id,
        })

        payload = {
            'readings': [
                {'seq': 1, 'meter_number': 'MTR-RETRY-07A', 'reading_value': 100.0},
                {'seq': 2, 'meter_number': 'MTR-MISSING-07B', 'reading_value': 200.0},
            ]
        }
        json_b64 = base64.b64encode(bytes(str(payload).replace("'", '"'), 'utf-8')).decode('utf-8')

        batch = self.Batch.create({
            'name': 'دفعة الإعادة الجزئية 07',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'data_file': json_b64,
            'state': 'uploaded',
        })

        # التأكيد الأول ينشئ القراءة للسطر الأول بينما يفشل السطر الثاني لعدم وجود العداد
        batch.action_confirm()
        self.assertEqual(batch.state, 'partial')
        self.assertEqual(len(batch.reading_ids), 1)
        self.assertEqual(len(batch.line_ids.filtered(lambda l: l.state == 'done')), 1)
        self.assertEqual(len(batch.line_ids.filtered(lambda l: l.state == 'failed')), 1)

        # تصحيح المشكلة بإنشاء العداد الفاقد
        meter2 = self.Meter.create({
            'meter_number': 'MTR-MISSING-07B',
            'customer_id': customer.id,
        })

        # تنفيذ إعادة المحاولة الصريحة action_reset_to_uploaded
        batch.action_reset_to_uploaded()

        self.assertEqual(batch.retry_count, 1)
        self.assertEqual(batch.state, 'done')
        # التأكد من إكمال السطرين دون إعادة إنشاء السطر الأول (إجمالي القراءات يجب أن يصبح 2 دقيقاً)
        self.assertEqual(len(batch.reading_ids), 2)
        self.assertEqual(len(batch.line_ids.filtered(lambda l: l.state == 'done')), 2)

    def test_08_batch_max_retry_policy_enforcement(self):
        """8. اختبار تطبيق سياسة الحد الأقصى لإعادة المحاولات للدفعات (MAX_BATCH_RETRIES = 3)"""
        period = self.DateRange.create({
            'name': 'فترة الحد الأقصى 08',
            'period_code': 'R-MEDIA-08-01',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'region_ids': [(6, 0, [self.region.id])],
        })

        batch = self.Batch.create({
            'name': 'دفعة أقصى محاولات 08',
            'region_id': self.region.id,
            'date_range_id': period.id,
            'state': 'partial',
            'retry_count': 3,
        })

        with self.assertRaises(ValidationError):
            batch.action_reset_to_uploaded()

    def test_09_filesystem_media_adapter_delete(self):
        """9. اختبار حذف الوسائط عبر FilesystemMediaAdapter والتأكد من إزالة الملفات والمرفقات"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.env['ir.config_parameter'].sudo().set_param('utility.filesystem_storage_path', tmp_dir)
            from odoo.addons.utility_core.adapters.media.filesystem import FilesystemMediaAdapter
            adapter = FilesystemMediaAdapter(self.env)

            orig_att = adapter.store(
                file_data=self.sample_bytes,
                filename='orig.png',
                mimetype='image/png',
                metadata={'asset_uuid': 'test-uuid-del-1'},
            )
            review_att = adapter.store(
                file_data=self.sample_bytes,
                filename='review.png',
                mimetype='image/png',
                metadata={'asset_uuid': 'test-uuid-del-1'},
            )
            thumb_att = adapter.store(
                file_data=self.sample_bytes,
                filename='thumb.png',
                mimetype='image/png',
                metadata={'asset_uuid': 'test-uuid-del-1'},
            )

            asset = self.MediaAsset.create({
                'name': 'Test Asset For Delete',
                'asset_uuid': 'test-uuid-del-1',
                'storage_backend': 'filesystem',
                'original_attachment_id': orig_att.id,
                'review_attachment_id': review_att.id,
                'thumbnail_attachment_id': thumb_att.id,
            })

            orig_file = orig_att.url.replace('file://', '')
            review_file = review_att.url.replace('file://', '')
            thumb_file = thumb_att.url.replace('file://', '')

            self.assertTrue(os.path.exists(orig_file))
            self.assertTrue(os.path.exists(review_file))
            self.assertTrue(os.path.exists(thumb_file))

            # Execute delete
            result = adapter.delete(asset)
            self.assertTrue(result)

            self.assertFalse(os.path.exists(orig_file))
            self.assertFalse(os.path.exists(review_file))
            self.assertFalse(os.path.exists(thumb_file))
            self.assertFalse(orig_att.exists())
            self.assertFalse(review_att.exists())
            self.assertFalse(thumb_att.exists())
