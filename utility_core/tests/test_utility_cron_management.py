import logging
from datetime import timedelta
import zlib

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestUtilityCronManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.supervisor_group = cls.env.ref('utility_core.group_utility_supervisor')
        cls.admin_group = cls.env.ref('utility_core.group_utility_admin')
        cls.readonly_group = cls.env.ref('utility_core.group_utility_readonly')

        # Test user with supervisor role (can run allowed jobs)
        cls.supervisor_user = cls.env['res.users'].create({
            'name': 'Supervisor User',
            'login': 'test_supervisor_cron',
            'email': 'supervisor_cron@example.com',
            'groups_id': [(6, 0, [cls.supervisor_group.id])],
        })

        # Test user with readonly role (cannot run manual jobs)
        cls.readonly_user = cls.env['res.users'].create({
            'name': 'Readonly User',
            'login': 'test_readonly_cron',
            'email': 'readonly_cron@example.com',
            'groups_id': [(6, 0, [cls.readonly_group.id])],
        })

        # Create a test managed cron
        cls.cron_model = cls.env['ir.model'].search([('model', '=', 'utility.meter')], limit=1)
        cls.test_managed_cron = cls.env['ir.cron'].create({
            'name': 'Test Managed Cron',
            'model_id': cls.cron_model.id,
            'state': 'code',
            'code': 'model.search_count([("active", "=", True)])',
            'interval_number': 1,
            'interval_type': 'hours',
            'active': True,
            'utility_managed': True,
            'utility_code': 'test_managed_job_alpha',
            'utility_category': 'operations',
            'prevent_overlap': True,
            'allow_manual_run': True,
            'allow_disable': True,
            'batch_size': 100,
        })

        # Create a second managed cron for multi-job concurrency test
        cls.test_managed_cron_beta = cls.env['ir.cron'].create({
            'name': 'Test Managed Cron Beta',
            'model_id': cls.cron_model.id,
            'state': 'code',
            'code': 'model.search_count([("active", "=", True)])',
            'interval_number': 1,
            'interval_type': 'hours',
            'active': True,
            'utility_managed': True,
            'utility_code': 'test_managed_job_beta',
            'utility_category': 'maintenance',
            'prevent_overlap': True,
            'allow_manual_run': True,
            'allow_disable': True,
            'batch_size': 50,
        })

        # Create a non-managed cron
        cls.test_unmanaged_cron = cls.env['ir.cron'].create({
            'name': 'Test Unmanaged Native Cron',
            'model_id': cls.cron_model.id,
            'state': 'code',
            'code': 'pass',
            'interval_number': 1,
            'interval_type': 'days',
            'active': True,
            'utility_managed': False,
        })

    def test_01_utility_cron_visibility(self):
        """التحقق من أن استعلام المهام المدارة يعيد فقط utility_managed=True ويستثني باقي مهام أودو العامة."""
        managed_crons = self.env['ir.cron'].search([('utility_managed', '=', True)])
        self.assertIn(self.test_managed_cron, managed_crons)
        self.assertIn(self.test_managed_cron_beta, managed_crons)
        self.assertNotIn(self.test_unmanaged_cron, managed_crons)

    def test_02_action_run_now_canonical(self):
        """التحقق من أن التشغيل اليدوي ينفذ نفس المسار القياسي وينشئ سجلاً في تاريخ التنفيذ."""
        cron = self.test_managed_cron.with_user(self.supervisor_user)
        initial_logs_count = self.env['utility.cron.execution'].search_count([('cron_id', '=', cron.id)])

        action_result = cron.action_run_now()
        self.assertEqual(action_result.get('type'), 'ir.actions.client')
        self.assertEqual(action_result.get('tag'), 'display_notification')

        # Check execution history record
        logs = self.env['utility.cron.execution'].search([('cron_id', '=', cron.id)], order='id desc')
        self.assertEqual(len(logs), initial_logs_count + 1)
        latest_log = logs[0]
        self.assertEqual(latest_log.trigger_type, 'manual')
        self.assertEqual(latest_log.triggered_by, self.supervisor_user)
        self.assertEqual(latest_log.status, 'success')
        self.assertEqual(latest_log.utility_code, 'test_managed_job_alpha')
        self.assertTrue(latest_log.finished_at)
        self.assertGreaterEqual(latest_log.duration_seconds, 0.0)

        # Check cron health state
        cron_refreshed = self.env['ir.cron'].browse(cron.id)
        self.assertEqual(cron_refreshed.last_execution_status, 'success')
        self.assertEqual(cron_refreshed.consecutive_failure_count, 0)
        self.assertTrue(cron_refreshed.last_success_at)

    def test_03_action_level_authorization(self):
        """التحقق من أن المستخدم غير المخول (Readonly) يُمنع من تشغيل أو تعديل حالة المهام المجدولة."""
        readonly_cron = self.test_managed_cron.with_user(self.readonly_user)
        with self.assertRaises(AccessError):
            readonly_cron.action_run_now()

        with self.assertRaises(AccessError):
            readonly_cron.action_enable()

        with self.assertRaises(AccessError):
            readonly_cron.action_disable()

        with self.assertRaises(AccessError):
            readonly_cron.action_reset_failure_count()

    def test_04_anti_overlap_protection_real_concurrency(self):
        """اختبار التزامن ومنع التداخل الحقيقي عبر قفل PostgreSQL الاستشاري باستخدام اتصالين/جلستين منفصلتين."""
        cron = self.test_managed_cron
        lock_key = cron._get_advisory_lock_key()

        # Connection / Session A (Worker A) acquires advisory lock on its own independent cursor
        with self.env.registry.cursor() as cr_worker_a:
            cr_worker_a.execute("SELECT pg_try_advisory_lock(%s);", (lock_key,))
            locked_by_a = cr_worker_a.fetchone()[0]
            self.assertTrue(locked_by_a, "Worker A must acquire the advisory lock on its independent session.")

            try:
                # Connection / Session B (Worker B via self.env.cr) attempts to execute the same cron
                # Worker B must be skipped because Worker A holds the lock on a separate DB session
                result = cron._execute_utility_managed_cron(trigger_type='manual')
                self.assertEqual(result.get('status'), 'skipped')
                self.assertEqual(result.get('reason'), 'locked')

                # Verify skipped execution log was recorded
                skipped_log = self.env['utility.cron.execution'].search([
                    ('cron_id', '=', cron.id),
                    ('status', '=', 'skipped'),
                ], limit=1, order='id desc')
                self.assertTrue(skipped_log)
                self.assertIn("قفل التزامن", skipped_log.error_message)

            finally:
                # Worker A releases the lock
                cr_worker_a.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))

        # Now that Worker A released the lock, Worker B can acquire it and run successfully
        result_after = cron._execute_utility_managed_cron(trigger_type='manual')
        self.assertEqual(result_after.get('status'), 'success')

    def test_05_different_jobs_concurrency(self):
        """التحقق من أن قفل مهمة معينة في جلسة مستقلة لا يمنع تشغيل مهمة أخرى مختلفة في جلسة أخرى."""
        cron_a = self.test_managed_cron
        cron_b = self.test_managed_cron_beta

        lock_key_a = cron_a._get_advisory_lock_key()
        lock_key_b = cron_b._get_advisory_lock_key()
        self.assertNotEqual(lock_key_a, lock_key_b, "Lock keys for distinct jobs must be different.")

        # Worker A acquires lock on Job A in its own independent cursor
        with self.env.registry.cursor() as cr_worker_a:
            cr_worker_a.execute("SELECT pg_try_advisory_lock(%s);", (lock_key_a,))
            self.assertTrue(cr_worker_a.fetchone()[0])

            try:
                # Worker B can still acquire its own lock for Job B and execute successfully!
                res_b = cron_b._execute_utility_managed_cron(trigger_type='manual')
                self.assertEqual(res_b.get('status'), 'success')
            finally:
                cr_worker_a.execute("SELECT pg_advisory_unlock(%s);", (lock_key_a,))

    def test_06_failure_handling_and_consecutive_counter(self):
        """التحقق من تسجيل الفشل في الحالتين (يدوي ومجدول) وحفظ سجل واحد دقيق للمحاولة اليدوية مع إعادة رفع الاستثناء في التشغيل المجدول."""
        failing_cron = self.env['ir.cron'].create({
            'name': 'Failing Test Cron',
            'model_id': self.cron_model.id,
            'state': 'code',
            'code': 'raise ValueError("Simulated Business Error 123")',
            'interval_number': 1,
            'interval_type': 'hours',
            'active': True,
            'utility_managed': True,
            'utility_code': 'test_failing_job',
            'prevent_overlap': True,
            'allow_manual_run': True,
        })

        initial_failures = failing_cron.consecutive_failure_count

        # 1. Manual run: captures failure, updates single existing exec_log, and returns dict without crashing
        res_manual = failing_cron._execute_utility_managed_cron(trigger_type='manual')
        self.assertEqual(res_manual.get('status'), 'failed')
        self.assertIn('Simulated Business Error 123', res_manual.get('error_message'))

        # Verify exactly ONE execution record exists for this manual run, and NO 'running' record remains
        manual_logs = self.env['utility.cron.execution'].search([('cron_id', '=', failing_cron.id)])
        self.assertEqual(len(manual_logs), 1, "Manual failure must produce exactly ONE execution record.")
        self.assertEqual(manual_logs[0].status, 'failed')
        self.assertEqual(manual_logs[0].trigger_type, 'manual')
        self.assertIn('Simulated Business Error 123', manual_logs[0].error_message)
        running_logs = self.env['utility.cron.execution'].search([('cron_id', '=', failing_cron.id), ('status', '=', 'running')])
        self.assertEqual(len(running_logs), 0, "No orphan 'running' execution log should remain.")

        # 2. Scheduled run: captures failure, saves audit record in isolated cursor, and re-raises exception
        with self.assertRaises(ValueError):
            failing_cron._execute_utility_managed_cron(trigger_type='scheduled')

        # Verify total logs count is now exactly 2 (one manual failed, one scheduled failed)
        all_logs = self.env['utility.cron.execution'].search([('cron_id', '=', failing_cron.id)], order='id desc')
        self.assertEqual(len(all_logs), 2)
        self.assertEqual(all_logs[0].status, 'failed')
        self.assertEqual(all_logs[0].trigger_type, 'scheduled')

        failing_cron.invalidate_recordset()
        self.assertGreaterEqual(failing_cron.consecutive_failure_count, initial_failures + 2)
        self.assertEqual(failing_cron.last_execution_status, 'failed')
        self.assertTrue(failing_cron.last_failure_at)
        self.assertIn('Simulated Business Error 123', failing_cron.last_error_message)

    def test_07_success_resets_failure_count(self):
        """التحقق من أن التشغيل الناجح بعد فشل سابق يصفر عداد الإخفاقات ويعيد الحالة إلى success."""
        cron = self.test_managed_cron
        for _ in range(3):
            self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
                'cron_id': cron.id,
                'utility_code': cron.utility_code,
                'started_at': fields.Datetime.now(),
                'status': 'failed',
                'error_message': 'Old failure message',
            })

        self.assertGreaterEqual(cron.consecutive_failure_count, 3)

        res = cron._execute_utility_managed_cron(trigger_type='manual')
        self.assertEqual(res.get('status'), 'success')

        cron.invalidate_recordset()
        self.assertEqual(cron.consecutive_failure_count, 0)
        self.assertEqual(cron.last_execution_status, 'success')
        self.assertFalse(cron.last_error_message)

    def test_08_partial_success_handling(self):
        """التحقق من أن استجابة الدالة بإحصائيات جزئية تسجل status='partial' مع الإحصائيات الدقيقة."""
        partial_cron = self.env['ir.cron'].create({
            'name': 'Partial Test Cron',
            'model_id': self.cron_model.id,
            'state': 'code',
            'code': '{"processed": 100, "success": 95, "failed": 5, "skipped": 0}',
            'interval_number': 1,
            'interval_type': 'hours',
            'active': True,
            'utility_managed': True,
            'utility_code': 'test_partial_job',
            'prevent_overlap': True,
            'allow_manual_run': True,
        })

        res = partial_cron._execute_utility_managed_cron(trigger_type='manual')
        self.assertEqual(res.get('status'), 'partial')
        self.assertEqual(res.get('processed'), 100)
        self.assertEqual(res.get('success'), 95)
        self.assertEqual(res.get('failed'), 5)

        log = self.env['utility.cron.execution'].search([('cron_id', '=', partial_cron.id)], limit=1, order='id desc')
        self.assertEqual(log.status, 'partial')
        self.assertEqual(log.processed_count, 100)
        self.assertEqual(log.success_count, 95)
        self.assertEqual(log.failure_count, 5)

    def test_09_execution_history_immutability(self):
        """التحقق من منع التعديل اليدوي لسجلات التنفيذ (Immutability)."""
        log = self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
            'cron_id': self.test_managed_cron.id,
            'utility_code': self.test_managed_cron.utility_code,
            'started_at': fields.Datetime.now(),
            'status': 'success',
        })

        with self.assertRaises(AccessError):
            log.with_user(self.supervisor_user).write({'status': 'failed'})

        with self.assertRaises(AccessError):
            log.with_user(self.admin_user).write({'error_message': 'Tampered message'})

    def test_10_non_utility_cron_rejection(self):
        """التحقق من رفض تشغيل المهام غير المدارة (utility_managed=False) عبر إجراءات الكهرباء."""
        unmanaged = self.test_unmanaged_cron
        with self.assertRaises(UserError):
            unmanaged.action_run_now()

    def test_11_health_status_computation(self):
        """التحقق من احتساب الحالة التشغيلية الصحية للمهام المجدولة بمختلف حالاتها."""
        cron = self.test_managed_cron

        # Disabled
        cron.active = False
        self.assertEqual(cron.health_status, 'disabled')

        # Healthy
        cron.active = True
        self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
            'cron_id': cron.id,
            'utility_code': cron.utility_code,
            'started_at': fields.Datetime.now(),
            'finished_at': fields.Datetime.now(),
            'status': 'success',
        })
        cron.nextcall = fields.Datetime.now() + timedelta(hours=1)
        self.assertEqual(cron.health_status, 'healthy')

        # Failed
        self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
            'cron_id': cron.id,
            'utility_code': cron.utility_code,
            'started_at': fields.Datetime.now(),
            'finished_at': fields.Datetime.now(),
            'status': 'failed',
            'error_message': 'Recent failure',
        })
        self.assertEqual(cron.health_status, 'failed')

        # Delayed
        self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
            'cron_id': cron.id,
            'utility_code': cron.utility_code,
            'started_at': fields.Datetime.now(),
            'finished_at': fields.Datetime.now(),
            'status': 'success',
        })
        cron.nextcall = fields.Datetime.now() - timedelta(hours=5)
        self.assertEqual(cron.health_status, 'delayed')

    def test_12_retention_cleanup(self):
        """التحقق من تنظيف السجلات القديمة وحذف ما يتجاوز فترة الاحتفاظ المحددة."""
        Execution = self.env['utility.cron.execution']
        old_date = fields.Datetime.now() - timedelta(days=120)
        recent_date = fields.Datetime.now() - timedelta(days=5)

        old_log = Execution.sudo().with_context(_cron_internal_write=True).create({
            'cron_id': self.test_managed_cron.id,
            'started_at': old_date,
            'finished_at': old_date,
            'status': 'success',
        })
        recent_log = Execution.sudo().with_context(_cron_internal_write=True).create({
            'cron_id': self.test_managed_cron.id,
            'started_at': recent_date,
            'finished_at': recent_date,
            'status': 'success',
        })

        # Cleanup records older than 90 days
        Execution.cron_cleanup_execution_history(retention_days=90)

        self.assertFalse(old_log.exists(), "Old log past retention cutoff should be deleted.")
        self.assertTrue(recent_log.exists(), "Recent log within retention cutoff must be preserved.")

    def test_12b_retention_cleanup_is_bounded_and_keeps_running_logs(self):
        """Cleanup removes only the requested batch and never running executions."""
        Execution = self.env['utility.cron.execution']
        old_date = fields.Datetime.now() - timedelta(days=120)
        old_logs = Execution.sudo().with_context(_cron_internal_write=True).create([
            {
                'cron_id': self.test_managed_cron.id,
                'started_at': old_date,
                'finished_at': old_date,
                'status': 'success',
            }
            for _index in range(3)
        ])
        running_log = Execution.sudo().with_context(_cron_internal_write=True).create({
            'cron_id': self.test_managed_cron.id,
            'started_at': old_date,
            'status': 'running',
        })

        result = Execution.cron_cleanup_execution_history(retention_days=90, batch_size=2)

        self.assertEqual(result['processed'], 2)
        self.assertEqual(len(old_logs.exists()), 1)
        self.assertTrue(running_log.exists())

    def test_13_callback_scheduler_routing(self):
        """التحقق من أن استدعاء _callback بواسطة مجدول أودو يوجه المهمة المدارة بالـ job_id الصحيح."""
        cron = self.test_managed_cron
        initial_logs_count = self.env['utility.cron.execution'].search_count([('cron_id', '=', cron.id)])

        # Simulate Odoo 16 scheduler calling _callback on ir.cron model
        self.env['ir.cron']._callback(
            cron_name=cron.name,
            server_action_id=cron.ir_actions_server_id.id if cron.ir_actions_server_id else False,
            job_id=cron.id,
        )

        # Verify execution log was generated with trigger_type='scheduled'
        logs = self.env['utility.cron.execution'].search([('cron_id', '=', cron.id)], order='id desc')
        self.assertEqual(len(logs), initial_logs_count + 1)
        latest_log = logs[0]
        self.assertEqual(latest_log.trigger_type, 'scheduled')
        self.assertEqual(latest_log.status, 'success')
