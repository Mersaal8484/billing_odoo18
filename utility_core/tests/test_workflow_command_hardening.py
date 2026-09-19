import json
from datetime import timedelta
from psycopg2 import OperationalError, IntegrityError

from odoo import api, fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.utility_core.adapters.workflow.local import LocalWorkflowAdapter
from odoo.addons.utility_core.adapters.workflow.temporal import TemporalWorkflowAdapter


class TestWorkflowCommandHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.cmd_model = self.env['utility.workflow.command']
        self.wf_service = self.env['utility.workflow.service']
        self.adapter = LocalWorkflowAdapter(self.env)

        # Setup test period
        self.period = self.env['date.range'].create({
            'name': 'فترة اختبار أوامر مسارات العمل',
            'code': '2026-WF-TEST',
            'type_id': self.env['date.range.type'].search([], limit=1).id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
        })

        # Test users
        self.admin_user = self.env.ref('base.user_admin')
        self.regular_user = self.env['res.users'].create({
            'name': 'مستخدم عمليات عادي / Regular Ops User',
            'login': 'regular_workflow_user',
            'email': 'regular_wf@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_workflow_command_tree_keeps_integer_priority_renderable(self):
        """The integer priority must not use Odoo's selection-only priority widget."""
        view = self.env.ref('utility_core.view_utility_workflow_command_tree')
        self.assertIn('<field name="priority"/>', view.arch_db)
        self.assertNotIn('<field name="priority" widget="priority"', view.arch_db)

    # =========================================================================
    # 1. Transaction Atomicity
    # =========================================================================
    def test_01_transaction_atomicity_rolls_back_command_and_business_together(self):
        """التحقق من أن فشل معاملة الأعمال يؤدي لتراجع قيد أمر مسار العمل وسجل الأعمال معاً."""
        key = f"ATOMIC_TEST:{self.period.code}"
        initial_cmds = self.cmd_model.search_count([('idempotency_key', '=', key)])
        self.assertEqual(initial_cmds, 0)

        # Execute inside a failing transaction savepoint
        try:
            with self.env.cr.savepoint():
                self.wf_service.dispatch(
                    workflow_type='open_reading_window',
                    reference_model='date.range',
                    reference_id=self.period.id,
                    idempotency_key=key,
                )
                # Simulate business exception occurring in same transaction
                raise ValidationError("Simulated failure in business transaction")
        except ValidationError:
            pass

        # Verify command was NOT persisted due to rollback
        count_after = self.cmd_model.search_count([('idempotency_key', '=', key)])
        self.assertEqual(count_after, 0, "Command record must be rolled back atomically with business transaction failure.")

    # =========================================================================
    # 2. Deterministic Idempotency
    # =========================================================================
    def test_02_deterministic_idempotency_prevents_duplicate_commands(self):
        """التحقق من أن استدعاء الأمر بنفس مفتاح عدم التكرار يرجع نفس السجل دون إنشاء تكرار."""
        key = f"IDEMPOTENT_TEST:{self.period.code}"

        cmd1 = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=key,
        )
        cmd2 = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=key,
        )

        self.assertEqual(cmd1.id, cmd2.id, "Dispatching with same idempotency key must return the exact same command record.")
        total_matching = self.cmd_model.search_count([('idempotency_key', '=', key)])
        self.assertEqual(total_matching, 1, "Exactly one durable command record must exist.")

    # =========================================================================
    # 3. Real Multi-Session Concurrency Claiming (Two DB Cursors)
    # =========================================================================
    def test_03_real_concurrency_claiming_with_separate_cursors(self):
        """
        التحقق من التزامن الحقيقي باستخدام جلستين/مؤشرين مستقلين لقاعدة البيانات:
        عندما يقوم Worker A بحجز الأمر عبر FOR UPDATE، يفشل Worker B في حجز نفس السجل.
        """
        key = f"CONCURRENCY_TEST:{self.period.code}"
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=key,
        )

        with self.env.registry.cursor() as cr_worker_a:
            env_a = api.Environment(cr_worker_a, self.env.uid, self.env.context)
            cmd_worker_a = env_a['utility.workflow.command'].browse(cmd.id)

            # Worker A claims the command
            claimed_a = cmd_worker_a.action_claim()
            self.assertTrue(claimed_a, "Worker A must successfully claim the command.")
            self.assertEqual(cmd_worker_a.state, 'processing')

            # Worker B on self.env.cr tries to claim the same command concurrently
            with self.env.registry.cursor() as cr_worker_b:
                env_b = api.Environment(cr_worker_b, self.env.uid, self.env.context)
                cmd_worker_b = env_b['utility.workflow.command'].browse(cmd.id)

                # Worker B should skip because record is locked by Worker A
                claimed_b = cmd_worker_b.action_claim()
                self.assertFalse(claimed_b, "Worker B must NOT be able to claim a record locked by Worker A.")

            cr_worker_a.rollback()

    # =========================================================================
    # 4. Concurrent Distinct Commands Claiming
    # =========================================================================
    def test_04_different_commands_can_be_claimed_concurrently(self):
        """التحقق من أن حجز أمر معين لا يمنع مشغلاً آخر من حجز أمر مختلف تماماً."""
        cmd1 = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"DISTINCT_CMD_1:{self.period.code}",
        )
        cmd2 = self.wf_service.dispatch(
            workflow_type='close_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"DISTINCT_CMD_2:{self.period.code}",
        )

        with self.env.registry.cursor() as cr_worker_a:
            env_a = api.Environment(cr_worker_a, self.env.uid, self.env.context)
            cmd1_a = env_a['utility.workflow.command'].browse(cmd1.id)
            self.assertTrue(cmd1_a.action_claim(), "Worker A must claim Command 1.")

            with self.env.registry.cursor() as cr_worker_b:
                env_b = api.Environment(cr_worker_b, self.env.uid, self.env.context)
                cmd2_b = env_b['utility.workflow.command'].browse(cmd2.id)
                self.assertTrue(cmd2_b.action_claim(), "Worker B must claim distinct Command 2 independently.")

            cr_worker_a.rollback()

    # =========================================================================
    # 5. Transient Failure and Deterministic Exponential Backoff
    # =========================================================================
    def test_05_transient_failure_exponential_backoff(self):
        """التحقق من أن الأخطاء المؤقتة تزيد عدد المحاولات وتحدد موعد المحاولة القادمة وفق التراجع الزمني المحسوب."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"BACKOFF_TEST:{self.period.code}",
        )
        cmd.action_claim()
        self.assertEqual(cmd.attempt_count, 1)

        # Simulate transient operational error
        now_before = fields.Datetime.now()
        cmd.action_fail(
            error="Connection timeout to meter gateway",
            error_category='transient',
            error_details="Traceback details...",
        )

        self.assertEqual(cmd.state, 'failed')
        self.assertEqual(cmd.error_category, 'transient')
        self.assertIn("Connection timeout", cmd.last_error)
        self.assertTrue(cmd.scheduled_at)
        # First attempt delay is 60 seconds
        expected_min = now_before + timedelta(seconds=55)
        self.assertGreaterEqual(cmd.scheduled_at, expected_min)

    # =========================================================================
    # 6. Permanent Business Failure Boundary
    # =========================================================================
    def test_06_permanent_business_failure_boundary(self):
        """التحقق من أن أخطاء الأعمال وقواعد التحقق لا تتكرر إلى ما لا نهاية."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"BIZ_FAIL_TEST:{self.period.code}",
        )
        cmd.action_claim()

        cmd.action_fail(
            error="Period is already closed, cannot open window.",
            error_category='business',
        )

        self.assertEqual(cmd.state, 'failed')
        self.assertEqual(cmd.error_category, 'business')
        # Business errors do not schedule automatic retry
        self.assertEqual(cmd.scheduled_at, cmd.create_date or cmd.scheduled_at)

    # =========================================================================
    # 7. Exhausted Attempts (Dead-Letter State)
    # =========================================================================
    def test_07_exhausted_attempts_transitions_to_dead_state(self):
        """التحقق من أن استنفاد الحد الأقصى للمحاولات ينقل الأمر إلى حالة متعثر نهائياً (dead)."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"DEAD_TEST:{self.period.code}",
        )
        cmd.write({'attempt_count': 3, 'max_attempts': 3, 'state': 'processing'})

        cmd.action_fail(
            error="Unrecoverable error on 3rd attempt",
            error_category='transient',
        )

        self.assertEqual(cmd.state, 'dead')
        self.assertIn("Unrecoverable error", cmd.last_error)

    # =========================================================================
    # 8. Stale Processing Recovery
    # =========================================================================
    def test_08_stale_processing_recovery(self):
        """التحقق من استعادة الأوامر المعلقة في processing عند تعثر المشغل وتجاوز المهلة المحددة."""
        old_time = fields.Datetime.now() - timedelta(hours=3)
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"STALE_TEST:{self.period.code}",
        )
        cmd.write({
            'state': 'processing',
            'started_at': old_time,
            'attempt_count': 1,
            'max_attempts': 3,
        })

        recovered = self.cmd_model.action_recover_stale(stale_threshold_seconds=7200)
        self.assertGreaterEqual(recovered, 1)

        cmd.invalidate_recordset()
        self.assertEqual(cmd.state, 'failed')
        self.assertIn('استعادة الأمر', cmd.last_error)

    # =========================================================================
    # 9. Adapter Boundary and Backend Resolver
    # =========================================================================
    def test_09_backend_resolver_and_adapter_boundary(self):
        """التحقق من أن معالج البنية التحتية المركزي يحدد المحول النشط بدقة ويرفع خطأ صريحاً عند اختيار Temporal غير الجاهز."""
        ICP = self.env['ir.config_parameter'].sudo()

        # 1. Local backend
        ICP.set_param('utility.workflow_adapter', 'local')
        adapter = self.wf_service._get_workflow_adapter()
        self.assertIsInstance(adapter, LocalWorkflowAdapter)

        # 2. Temporal backend (Placeholder - must block without silent fallback)
        ICP.set_param('utility.workflow_adapter', 'temporal')
        with self.assertRaises(UserError):
            self.wf_service._get_workflow_adapter()

        # 3. Invalid backend
        ICP.set_param('utility.workflow_adapter', 'unknown_backend')
        with self.assertRaises(UserError):
            self.wf_service._get_workflow_adapter()

        ICP.set_param('utility.workflow_adapter', 'local')

    # =========================================================================
    # 10. Immutability on Completed Commands
    # =========================================================================
    def test_10_completed_command_immutability(self):
        """التحقق من منع تعديل الهوية أو البيانات المدخلة للأمر بعد اكتمال تنفيذه."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"IMMUTABLE_TEST:{self.period.code}",
        )
        cmd.action_claim()
        cmd.action_complete(result="Success outcome")

        self.assertEqual(cmd.state, 'completed')

        # Attempting to mutate identity fields must raise UserError
        with self.assertRaises(UserError):
            cmd.write({'idempotency_key': 'NEW_MUTATED_KEY'})

        with self.assertRaises(UserError):
            cmd.write({'workflow_type': 'different_type'})

    # =========================================================================
    # 11. Pure Infrastructure Cron Dispatcher
    # =========================================================================
    def test_11_cron_dispatcher_processes_pending_commands(self):
        """التحقق من أن المجدول يعمل كـ Infrastructure Glue فقط لتوزيع الأوامر المؤهلة دون احتواء منطق أعمال."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"CRON_DISPATCH_TEST:{self.period.code}",
        )
        self.assertEqual(cmd.state, 'pending')

        # Run cron dispatcher
        res = self.cmd_model.cron_dispatch_pending_commands(batch_size=10)
        self.assertGreaterEqual(res.get('processed'), 1)

        cmd.invalidate_recordset()
        self.assertIn(cmd.state, ('completed', 'failed'))

    # =========================================================================
    # 12. Security and Authorization
    # =========================================================================
    def test_12_security_authorization_checks(self):
        """التحقق من حظر العمليات الحساسة (إلغاء، إعادة تشغيل، استعادة) على المستخدمين غير المخولين."""
        cmd = self.wf_service.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=self.period.id,
            idempotency_key=f"SECURITY_TEST:{self.period.code}",
        )
        cmd.write({'state': 'failed'})

        # Regular user cannot retry or cancel
        with self.assertRaises(AccessError):
            cmd.with_user(self.regular_user).action_retry_manual()

        with self.assertRaises(AccessError):
            cmd.with_user(self.regular_user).action_cancel(reason="Unauthorized attempt")

    # =========================================================================
    # 13. Strict Workflow Registry & Model Validation
    # =========================================================================
    def test_13_registry_validation_rejects_unregistered_types_and_mismatched_models(self):
        """التحقق من أن dispatch يفرض التحقق الصارم من نوع المسار والنموذج المعتمد قبل إنشاء الأمر."""
        # 1. Unregistered workflow type MUST raise ValidationError
        with self.assertRaises(ValidationError):
            self.wf_service.dispatch(
                workflow_type='unregistered_arbitrary_workflow',
                reference_model='date.range',
                reference_id=self.period.id,
            )

        # 2. Mismatched model (e.g. res.partner instead of date.range) MUST raise ValidationError
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        with self.assertRaises(ValidationError):
            self.wf_service.dispatch(
                workflow_type='open_reading_window',
                reference_model='res.partner',
                reference_id=partner.id,
            )

    # =========================================================================
    # 14. Payment Period Workflow Mapping
    # =========================================================================
    def test_14_payment_period_workflow_mapping(self):
        """التحقق من أن trigger_payment_workflow يوجه لدالة فتح فترة السداد action_open_payment."""
        payment_period = self.env['date.range'].create({
            'name': 'فترة سداد اختبارية',
            'code': 'PAY-2026-TEST',
            'period_role': 'payment',
            'type_id': self.env['date.range.type'].search([], limit=1).id,
            'date_start': '2026-01-15',
            'date_end': '2026-02-15',
        })

        cmd = self.wf_service.dispatch(
            workflow_type='trigger_payment_workflow',
            reference_model='date.range',
            reference_id=payment_period.id,
            idempotency_key=f"PAY_WF_TEST:{payment_period.code}",
        )
        self.assertEqual(cmd.workflow_type, 'trigger_payment_workflow')
        self.assertEqual(cmd.reference_model, 'date.range')

        # Execute command
        res = self.adapter.execute_command(cmd)
        self.assertEqual(res.get('status'), 'success')
        payment_period.invalidate_recordset(['state'])
        self.assertEqual(payment_period.state, 'open')
