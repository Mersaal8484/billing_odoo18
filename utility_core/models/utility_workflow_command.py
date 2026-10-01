import json
import logging
import uuid
from datetime import timedelta
from psycopg2 import OperationalError

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Deterministic backoff delays in seconds per attempt index
BACKOFF_DELAYS = [60, 300, 900, 3600]


class UtilityWorkflowCommand(models.Model):
    _name = 'utility.workflow.command'
    _description = 'سجل وطابور أوامر مسارات العمل (Durable Local Workflow Command Queue)'
    _order = 'priority desc, scheduled_at asc, id desc'

    name = fields.Char('رمز الأمر / Command Code', required=True, index=True)
    command_uuid = fields.Char(
        string='رمز المعرف الفريد / Command UUID',
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4())
    )
    idempotency_key = fields.Char(
        string='مفتاح عدم التكرار / Idempotency Key',
        required=True,
        copy=False,
        index=True
    )
    workflow_type = fields.Char(
        string='نوع مسار العمل / Workflow Type',
        required=True,
        default='general',
        index=True
    )
    action_type = fields.Char(
        string='نوع الإجراء (Legacy) / Action Type',
        compute='_compute_action_type',
        inverse='_set_action_type',
        search='_search_action_type',
    )

    # ===== مراجع مرنة لربط أي نموذج (Generic Model Reference) =====
    reference_model = fields.Char(
        string='النموذج المرتبط / Reference Model',
        required=True,
        index=True
    )
    res_model = fields.Char(
        string='النموذج المرتبط (Legacy) / Res Model',
        compute='_compute_res_model',
        inverse='_set_res_model',
        search='_search_res_model',
    )

    reference_id = fields.Many2oneReference(
        string='معرف السجل المرتبط / Reference Record ID',
        model_field='reference_model',
        required=True,
        index=True
    )
    res_id = fields.Many2oneReference(
        string='معرف السجل (Legacy) / Res ID',
        model_field='res_model',
        compute='_compute_res_id',
        inverse='_set_res_id',
        search='_search_res_id',
    )

    period_id = fields.Many2one('date.range', string='الفترة / Period', required=False, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='الشركة / Company', default=lambda self: self.env.company, index=True)

    backend = fields.Selection([
        ('local', 'محلي (Outbox) / Local Outbox'),
        ('temporal', 'تيمبورال / Temporal (Prod)'),
        ('queue_job', 'طوابير OCA موزعة / OCA Queue Job'),
    ], string='محرك المعالجة / Workflow Backend', default='local', required=True, index=True)

    state = fields.Selection([
        ('pending', 'قيد الانتظار / Pending'),
        ('processing', 'قيد المعالجة / Processing'),
        ('completed', 'مكتمل / Completed'),
        ('failed', 'فشل / Failed'),
        ('cancelled', 'ملغي / Cancelled'),
        ('dead', 'متعثر نهائياً / Dead-Letter'),
    ], string='الحالة / State', default='pending', required=True, index=True)

    attempt_count = fields.Integer('عدد المحاولات / Attempt Count', default=0, required=True)
    max_attempts = fields.Integer('الحد الأقصى للمحاولات / Max Attempts', default=3, required=True)

    scheduled_at = fields.Datetime('تاريخ التجدول / Scheduled At', default=fields.Datetime.now, required=True, index=True)
    next_attempt_at = fields.Datetime('موعد المحاولة القادمة / Next Attempt At', compute='_compute_next_attempt_at', store=True, index=True)
    started_at = fields.Datetime('تاريخ بدء التنفيذ / Started At')
    completed_at = fields.Datetime('تاريخ إكمال التنفيذ / Completed At')
    duration_seconds = fields.Float('المدة (ثواني) / Duration (s)', digits=(12, 3), readonly=True)

    priority = fields.Integer('الأولوية / Priority', default=10, index=True, help='الأولوية الأعلى تُعالج أولاً')

    payload_json = fields.Text('بيانات الطلب / Payload JSON')
    payload_version = fields.Integer('إصدار البيانات / Payload Version', default=1)

    result_summary = fields.Text('ملخص النتيجة / Result Summary')
    error_category = fields.Selection([
        ('transient', 'خطأ مؤقت / Transient'),
        ('business', 'خطأ أعمال / Business Rule Violation'),
        ('configuration', 'خطأ إعدادات / Configuration Error'),
        ('unexpected', 'خطأ برمجي غير متوقع / Unexpected System Error'),
    ], string='تصنيف الخطأ / Error Category', index=True)
    last_error = fields.Text('آخر رسالة خطأ / Last Error Message')
    error_message = fields.Text(
        string='رسالة الخطأ (Legacy) / Error Message',
        compute='_compute_error_message',
        inverse='_set_error_message',
    )
    last_error_details = fields.Text('تفاصيل الخطأ التشخيصية / Error Traceback Details')

    external_workflow_ref = fields.Char('مرجع مسار العمل الخارجي / External Workflow Ref', index=True)
    workflow_id = fields.Char(
        string='مرجع مسار العمل (Legacy) / Workflow ID',
        compute='_compute_workflow_id',
        inverse='_set_workflow_id',
    )
    workflow_run_id = fields.Char('مرجع تشغيل مسار العمل / Workflow Run Ref')

    _sql_constraints = [
        ('unique_idempotency_key', 'unique(idempotency_key)', 'مفتاح عدم التكرار (Idempotency Key) يجب أن يكون فريداً لكل أمر!'),
    ]

    # -------------------------------------------------------------------------
    # Backward-Compatibility Computed Fields
    # -------------------------------------------------------------------------
    @api.depends('workflow_type')
    def _compute_action_type(self):
        for rec in self:
            rec.action_type = rec.workflow_type

    def _set_action_type(self):
        for rec in self:
            rec.workflow_type = rec.action_type

    def _search_action_type(self, operator, value):
        return [('workflow_type', operator, value)]

    @api.depends('reference_model')
    def _compute_res_model(self):
        for rec in self:
            rec.res_model = rec.reference_model

    def _set_res_model(self):
        for rec in self:
            rec.reference_model = rec.res_model

    def _search_res_model(self, operator, value):
        return [('reference_model', operator, value)]

    @api.depends('reference_id')
    def _compute_res_id(self):
        for rec in self:
            rec.res_id = rec.reference_id

    def _set_res_id(self):
        for rec in self:
            rec.reference_id = rec.res_id

    def _search_res_id(self, operator, value):
        return [('reference_id', operator, value)]

    @api.depends('last_error')
    def _compute_error_message(self):
        for rec in self:
            rec.error_message = rec.last_error

    def _set_error_message(self):
        for rec in self:
            rec.last_error = rec.error_message

    @api.depends('external_workflow_ref')
    def _compute_workflow_id(self):
        for rec in self:
            rec.workflow_id = rec.external_workflow_ref

    def _set_workflow_id(self):
        for rec in self:
            rec.external_workflow_ref = rec.workflow_id

    @api.depends('scheduled_at')
    def _compute_next_attempt_at(self):
        for rec in self:
            rec.next_attempt_at = rec.scheduled_at

    # -------------------------------------------------------------------------
    # Immutability Guard
    # -------------------------------------------------------------------------
    def write(self, vals):
        # Prevent mutating identity or payload on completed commands
        immutable_fields = {'workflow_type', 'reference_model', 'reference_id', 'idempotency_key', 'payload_json', 'payload_version'}
        if any(f in vals for f in immutable_fields):
            for rec in self:
                if rec.state == 'completed' and not self.env.context.get('_force_workflow_migration'):
                    raise UserError(_("لا يمكن تعديل بيانات أمر مسار عمل مكتمل التنفيذ (%s) للحفاظ على سلامة التدقيق.") % rec.name)
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Controlled State Machine Transitions
    # -------------------------------------------------------------------------
    def action_claim(self):
        """
        حجز الأمر ذرياً للتنفيذ بواسطة مشغل (Atomic Claim with PostgreSQL Row Lock):
        يتحقق من الحالة ويحجز القفل لمنع أي worker آخر من معالجة نفس الأمر في نفس الوقت.
        """
        self.ensure_one()
        if self.state not in ('pending', 'failed'):
            return False

        # Acquire row lock safely with NOWAIT
        try:
            self.env.cr.execute(
                "SELECT id FROM utility_workflow_command WHERE id = %s FOR UPDATE NOWAIT",
                (self.id,)
            )
        except OperationalError as exc:
            pgcode = getattr(exc, 'pgcode', None)
            if pgcode == '55P03':
                _logger.info("Workflow Command [%s] is currently locked by another worker (55P03). Skipping claim.", self.id)
                return False
            raise

        self.invalidate_recordset(['state', 'attempt_count', 'max_attempts'])
        if self.state not in ('pending', 'failed'):
            return False

        now = fields.Datetime.now()
        self.write({
            'state': 'processing',
            'started_at': now,
            'attempt_count': self.attempt_count + 1,
        })
        _logger.info("Workflow Command [%s] claimed (attempt %d/%d, type: %s)", self.name, self.attempt_count, self.max_attempts, self.workflow_type)
        return True

    def action_complete(self, result=None):
        """تحويل الأمر إلى حالة مكتمل وتوثيق مدة التنفيذ والنتيجة."""
        self.ensure_one()
        if self.state != 'processing':
            raise ValidationError(_("لا يمكن إكمال أمر غير موجود في حالة قيد المعالجة (الحالة الحالية: %s).") % self.state)

        now = fields.Datetime.now()
        started = self.started_at or now
        duration = (now - started).total_seconds()
        summary = result if isinstance(result, str) else (json.dumps(result, ensure_ascii=False) if result else False)

        self.write({
            'state': 'completed',
            'completed_at': now,
            'duration_seconds': duration,
            'result_summary': summary,
            'last_error': False,
            'last_error_details': False,
            'error_category': False,
        })
        _logger.info("Workflow Command [%s] completed successfully in %.3fs.", self.name, duration)
        return True

    def action_fail(self, error=None, error_category='unexpected', error_details=None):
        """
        تسجيل فشل الأمر مع التراجع الزمني المحسوب (Deterministic Exponential Backoff):
        إذا تجاوز الحد الأقصى للمحاولات أو كان الخطأ من فئة الأعمال يُنقل إلى dead أو failed نهائي.
        """
        self.ensure_one()
        if self.state != 'processing':
            _logger.warning("Attempted to fail command [%s] which is in state [%s].", self.name, self.state)

        now = fields.Datetime.now()
        err_msg = str(error) if error else _('خطأ غير معروف أثناء التنفيذ')
        is_exhausted = self.attempt_count >= self.max_attempts or error_category in ('business', 'configuration')

        if is_exhausted:
            new_state = 'dead' if self.attempt_count >= self.max_attempts else 'failed'
            next_attempt = False
        else:
            new_state = 'failed'
            # Backoff formula: 1m, 5m, 15m, 60m
            delay_idx = min(self.attempt_count - 1, len(BACKOFF_DELAYS) - 1)
            delay_seconds = BACKOFF_DELAYS[max(0, delay_idx)]
            next_attempt = now + timedelta(seconds=delay_seconds)

        self.write({
            'state': new_state,
            'scheduled_at': next_attempt or now,
            'error_category': error_category,
            'last_error': err_msg,
            'last_error_details': error_details or False,
        })
        _logger.warning(
            "Workflow Command [%s] failed (state: %s, attempt %d/%d, next_attempt: %s): %s",
            self.name, new_state, self.attempt_count, self.max_attempts, next_attempt, err_msg
        )
        return True

    def action_cancel(self, reason=None):
        """إلغاء الأمر للأوامر المعلقة أو الفاشلة فقط."""
        for rec in self:
            rec._verify_admin_security()
            if rec.state not in ('pending', 'failed', 'dead'):
                raise UserError(_("لا يمكن إلغاء الأمر (%s) لأنه بحالة (%s).") % (rec.name, rec.state))
            rec.write({
                'state': 'cancelled',
                'result_summary': _("تم إلغاء الأمر بواسطة %s: %s") % (self.env.user.name, reason or _('بدون سبب محدد')),
            })
        return True

    def action_retry_manual(self):
        """إعادة محاولة تنفيذ الأمر يدوياً للمشرفين ومدراء العمليات."""
        for rec in self:
            rec._verify_operator_security()
            if rec.state not in ('failed', 'dead', 'cancelled'):
                raise UserError(_("يمكن إعادة المحاولة فقط للأوامر الفاشلة أو المتعثرة أو الملغاة."))
            rec.write({
                'state': 'pending',
                'scheduled_at': fields.Datetime.now(),
                'last_error': False,
                'last_error_details': False,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('إعادة جدولة الأمر'),
                'message': _('تمت إعادة جدولة الأوامر المحددة للتنفيذ الفوري بنجاح.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recover_stale(self, stale_threshold_seconds=7200):
        """استعادة الأوامر المعلقة المتعثرة (Stale Processing Recovery)."""
        cutoff = fields.Datetime.now() - timedelta(seconds=stale_threshold_seconds)
        stale_cmds = self.search([
            ('state', '=', 'processing'),
            ('started_at', '<', cutoff),
        ])
        count = 0
        for cmd in stale_cmds:
            cmd._verify_admin_security()
            if cmd.attempt_count < cmd.max_attempts:
                cmd.write({
                    'state': 'failed',
                    'scheduled_at': fields.Datetime.now(),
                    'last_error': _('تم استعادة الأمر: تعثر المشغل السابق أثناء المعالجة (تجاوز مهلة الاستجابة).'),
                })
            else:
                cmd.write({
                    'state': 'dead',
                    'last_error': _('تم نقل الأمر للمتعثرات: تعثر المشغل واستنفذ الحد الأقصى للمحاولات.'),
                })
            count += 1
        return count

    # -------------------------------------------------------------------------
    # Security Checks
    # -------------------------------------------------------------------------
    def _verify_operator_security(self):
        user = self.env.user
        allowed_groups = [
            'utility_core.group_utility_supervisor',
            'utility_core.group_utility_billing_manager',
            'utility_core.group_utility_revenue_manager',
            'utility_core.group_utility_admin',
            'base.group_system',
            'base.group_erp_manager',
        ]
        if not any(user.has_group(g) for g in allowed_groups):
            raise AccessError(_("ليس لديك صلاحية إعادة تشغيل أوامر مسارات العمل."))

    def _verify_admin_security(self):
        user = self.env.user
        allowed_groups = [
            'utility_core.group_utility_admin',
            'base.group_system',
            'base.group_erp_manager',
        ]
        if not any(user.has_group(g) for g in allowed_groups):
            raise AccessError(_("هذه العملية تتطلب صلاحية مسؤول نظام الكهرباء (Utility Admin)."))

    # -------------------------------------------------------------------------
    # Pure Infrastructure Cron Dispatcher
    # -------------------------------------------------------------------------
    @api.model
    def cron_dispatch_pending_commands(self, batch_size=20):
        """
        موزع أوامر البنية التحتية (Infrastructure Command Dispatcher):
        يجلب الأوامر المؤهلة للتنفيذ عبر قفل تزامني جماعي (FOR UPDATE SKIP LOCKED)
        ويمررها للمحول النشط عبر الـ Central Resolver دون احتواء أي منطق أعمال داخله.
        """
        now = fields.Datetime.now()
        # Concurrency-hardened batch selection with FOR UPDATE SKIP LOCKED
        query = """
            SELECT id FROM utility_workflow_command
            WHERE backend = 'local'
              AND (
                  state = 'pending'
                  OR (state = 'failed' AND scheduled_at <= %s AND attempt_count < max_attempts)
              )
            ORDER BY priority DESC, scheduled_at ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """
        self.env.cr.execute(query, (now, batch_size))
        cmd_ids = [row[0] for row in self.env.cr.fetchall()]

        if not cmd_ids:
            return {'processed': 0, 'success': 0, 'failed': 0, 'skipped': 0}

        eligible_cmds = self.browse(cmd_ids)
        adapter = self.env['utility.workflow.service']._get_workflow_adapter()

        processed = 0
        success = 0
        failed = 0
        skipped = 0

        for cmd in eligible_cmds:
            processed += 1
            try:
                res = adapter.execute_command(cmd)
                if res.get('status') == 'skipped':
                    skipped += 1
                elif res.get('status') == 'failed':
                    failed += 1
                else:
                    success += 1
            except Exception as exc:
                _logger.exception("Cron dispatch error for command [%s]: %s", cmd.name, exc)
                failed += 1

        return {
            'processed': processed,
            'success': success,
            'failed': failed,
            'skipped': skipped,
        }

    # -------------------------------------------------------------------------
    # OCA Queue Job Handler — يُستدعى من with_delay() تلقائياً
    # -------------------------------------------------------------------------
    def _execute_via_queue_job_handler(self, command_id):
        """
        نقطة الدخول لـ OCA Queue Job:
        يُنفَّذ هذا الأسلوب داخل worker منفصل عبر queue_job.
        يتولى تنفيذ الأمر بمنطق المحول المحلي (محول محايد للأعمال).

        :param command_id: معرف سجل utility.workflow.command المراد تنفيذه
        :return: ملخص نتيجة التنفيذ (str)
        """
        from ..adapters.workflow.local import LocalWorkflowAdapter

        cmd = self.sudo().browse(command_id).exists()
        if not cmd:
            _logger.warning("QueueJob handler: command ID %s not found, skipping.", command_id)
            return 'not_found'

        local_adapter = LocalWorkflowAdapter(self.env)
        result = local_adapter.execute_command(cmd)
        status = result.get('status', 'unknown')
        _logger.info(
            "QueueJob handler: command [%s] finished with status=%s.",
            cmd.name, status
        )
        if status == 'failed':
            # إعادة رفع الخطأ حتى يُعيد OCA queue_job المحاولة تلقائياً
            raise Exception(result.get('error', 'Unknown execution error in queue_job handler'))
        return status
