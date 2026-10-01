"""
محول مسارات العمل المبني على OCA Queue Job (queue_job Workflow Adapter)
==========================================================================
يوفر توزيع أوامر رفع القراءات والفوترة على قنوات منفصلة لكل منطقة/فرع
(Geographic Channel Distribution) مع عدم التكرار الحتمي والمراجعة الكاملة.

نمط التكامل:
- عند dispatch: يُنشئ سجل utility.workflow.command بـ backend='queue_job'
  ثم يُدفع الأمر لـ OCA queue.job بقناة جغرافية = 'utility_region_<region_id>'
- عند تنفيذ الـ job: يستدعي _execute_via_queue_job_handler ←
  utility.workflow.service._execute_workflow_handler
- الفشل والإعادة تُدار بواسطة قاعدة إعادة المحاولة في OCA queue_job.

الأقسام:
1. dispatch  — بناء الأمر وتخصيص القناة الجغرافية ودفعه للطابور
2. cancel    — إلغاء الأمر المعلق
3. get_status — استعلام الحالة
4. execute_command — تنفيذ مباشر (local fallback عند اختبار)
"""

import json
import logging
from psycopg2 import IntegrityError

from odoo import fields, _
from odoo.exceptions import UserError, ValidationError
from .base import AbstractWorkflowAdapter

_logger = logging.getLogger(__name__)

# الطابور الافتراضي إذا لم تُحدد منطقة
DEFAULT_CHANNEL = 'root'

# بادئة اسم القناة الجغرافية
REGION_CHANNEL_PREFIX = 'utility_region'


def _build_geo_channel(payload: dict | None, fallback_channel: str | None = None) -> str:
    """
    بناء اسم قناة OCA queue_job الجغرافية من الـ payload.

    الأولوية:
    1. region_id   ← لعزل كل منطقة على قناتها الخاصة
    2. branch_id   ← الفرع كمستوى ثانوي (نوع منطقة area)
    3. fallback_channel ← قناة مخصصة مُمررة من الخارج
    4. DEFAULT_CHANNEL

    أمثلة:
    - {'region_id': 5}   → 'utility_region.5'
    - {'branch_id': 12}  → 'utility_region.12'
    - None               → 'root'
    """
    if payload:
        if payload.get('region_id'):
            return f"{REGION_CHANNEL_PREFIX}.{payload['region_id']}"
        if payload.get('branch_id'):
            return f"{REGION_CHANNEL_PREFIX}.{payload['branch_id']}"
    return fallback_channel or DEFAULT_CHANNEL


class QueueJobWorkflowAdapter(AbstractWorkflowAdapter):
    """
    محول مسارات العمل عبر OCA Queue Job (queue_job).

    يتطلب وجود وحدة `queue_job` من OCA مثبتة على الخادم.
    عند غيابها يُرفع UserError فوراً دون fallback صامت.
    """

    PRODUCTION_READY = True

    def __init__(self, env):
        self.env = env
        self._assert_queue_job_installed()

    def _assert_queue_job_installed(self):
        """التحقق من تثبيت OCA queue_job قبل أي عملية."""
        if 'queue.job' not in self.env:
            raise UserError(_(
                "وحدة OCA Queue Job (queue_job) غير مثبتة على هذا الخادم.\n"
                "يُرجى تثبيتها أولاً أو الرجوع إلى محول Local Odoo Outbox."
            ))

    # -------------------------------------------------------------------------
    # AbstractWorkflowAdapter — dispatch
    # -------------------------------------------------------------------------
    def dispatch(self, workflow_type, reference_model, reference_id,
                 payload=None, idempotency_key=None, priority=10):
        """
        توجيه أمر مسار العمل إلى OCA queue_job بقناة جغرافية.

        الخطوات:
        1. بناء/جلب سجل utility.workflow.command (idempotent).
        2. اختيار قناة جغرافية من payload (region_id / branch_id).
        3. دفع delayed job إلى queue_job بالقناة المناسبة.
        4. تخزين معرف الـ job في external_workflow_ref للتتبع.
        """
        if not idempotency_key:
            idempotency_key = f"{workflow_type.upper()}:{reference_model}:{reference_id}"

        cmd_model = self.env['utility.workflow.command'].sudo()
        payload_str = (json.dumps(payload, ensure_ascii=False)
                       if isinstance(payload, (dict, list)) else (payload or False))

        # --- Idempotent command creation ---
        existing = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)
        if existing:
            cmd = existing
        else:
            try:
                with self.env.cr.savepoint():
                    cmd = cmd_model.create({
                        'name': f"QJ-{workflow_type.upper()}-{reference_id}",
                        'idempotency_key': idempotency_key,
                        'workflow_type': workflow_type,
                        'reference_model': reference_model,
                        'reference_id': reference_id,
                        'state': 'pending',
                        'backend': 'queue_job',
                        'priority': priority,
                        'payload_json': payload_str,
                    })
            except IntegrityError as exc:
                if getattr(exc, 'pgcode', None) != '23505':
                    raise
                cmd = cmd_model.search([('idempotency_key', '=', idempotency_key)], limit=1)
                if not cmd:
                    raise

        if not cmd:
            raise ValidationError(_("فشل إنشاء أو استرجاع أمر مسار العمل."))

        # إذا كان الأمر مكتملاً أو قيد المعالجة لا نُعيد دفعه
        if cmd.state in ('completed', 'processing'):
            _logger.info(
                "QueueJob dispatch: command [%s] already in state=%s, skipping re-enqueue.",
                cmd.name, cmd.state
            )
            return cmd

        # --- Geographic channel selection ---
        payload_dict = (json.loads(payload_str) if payload_str else {}) if isinstance(payload_str, str) else (payload or {})
        channel = _build_geo_channel(payload_dict)

        # --- Enqueue to OCA queue_job ---
        try:
            job = (
                self.env['utility.workflow.command']
                .sudo()
                .with_delay(
                    channel=channel,
                    description=f"[{workflow_type}] {reference_model}:{reference_id}",
                    priority=priority,
                    identity_key=idempotency_key,
                )
                ._execute_via_queue_job_handler(cmd.id)
            )
            # تخزين UUID الـ job في السجل للتتبع
            if hasattr(job, 'uuid'):
                cmd.write({'external_workflow_ref': job.uuid})
            _logger.info(
                "QueueJob dispatch: command [%s] enqueued on channel '%s' (job_uuid=%s).",
                cmd.name, channel, getattr(job, 'uuid', 'N/A')
            )
        except Exception as exc:
            _logger.error(
                "QueueJob dispatch: failed to enqueue command [%s]: %s", cmd.name, exc
            )
            raise

        return cmd

    # -------------------------------------------------------------------------
    # AbstractWorkflowAdapter — cancel / get_status / execute_command
    # -------------------------------------------------------------------------
    def cancel(self, workflow_id, reason=None):
        """إلغاء أمر مسار العمل."""
        cmd = self.env['utility.workflow.command'].sudo().search([
            '|', ('idempotency_key', '=', workflow_id),
            '|', ('command_uuid', '=', workflow_id),
            ('id', '=', int(workflow_id) if str(workflow_id).isdigit() else 0),
        ], limit=1)
        if not cmd:
            raise ValidationError(_("أمر مسار العمل (%s) غير موجود.") % workflow_id)
        return cmd.action_cancel(reason=reason)

    def get_status(self, workflow_id):
        """الاستعلام عن حالة الأمر ومعرف الـ job الخارجي."""
        cmd = self.env['utility.workflow.command'].sudo().search([
            '|', ('idempotency_key', '=', workflow_id),
            '|', ('command_uuid', '=', workflow_id),
            ('id', '=', int(workflow_id) if str(workflow_id).isdigit() else 0),
        ], limit=1)
        if not cmd:
            return {'status': 'not_found', 'workflow_id': workflow_id}
        return {
            'status': cmd.state,
            'workflow_id': cmd.command_uuid,
            'external_job_ref': cmd.external_workflow_ref,
            'idempotency_key': cmd.idempotency_key,
            'attempt_count': cmd.attempt_count,
            'started_at': cmd.started_at,
            'completed_at': cmd.completed_at,
            'result': cmd.result_summary,
            'last_error': cmd.last_error,
        }

    def execute_command(self, command, payload_func=None, summary_func=None):
        """
        تنفيذ مباشر للأمر (يُستخدم في الاختبارات أو عند fallback يدوي).
        في الإنتاج يُنفَّذ الأمر عبر queue_job handler.
        """
        from .local import LocalWorkflowAdapter
        local = LocalWorkflowAdapter(self.env)
        return local.execute_command(command, payload_func=payload_func, summary_func=summary_func)
