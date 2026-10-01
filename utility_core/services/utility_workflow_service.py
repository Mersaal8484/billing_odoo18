import json
import logging
from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityWorkflowService(models.AbstractModel):
    _name = 'utility.workflow.service'
    _description = 'مخدم وسيط إدارة ومحولات مسارات العمل (Central Workflow Service & Registry)'

    # =========================================================================
    # Workflow Type Registry
    # =========================================================================
    WORKFLOW_REGISTRY = {
        'reading_batch_process': {
            'model': 'utility.reading.batch',
            'desc': 'معالجة دفعات قراءات العدادات',
            'service_model': 'utility.reading.batch.service',
            'service_method': 'process_batch',
        },
        'open_reading_window': {
            'model': 'date.range',
            'desc': 'فتح نافذة رفع القراءات',
            'service_model': 'date.range',
            'service_method': 'action_open_reading',
        },
        'close_reading_window': {
            'model': 'date.range',
            'desc': 'إغلاق نافذة رفع القراءات',
            'service_model': 'date.range',
            'service_method': 'action_close_reading',
        },
        'open_payment_window': {
            'model': 'date.range',
            'desc': 'فتح نافذة السداد والتحصيل',
            'service_model': 'date.range',
            'service_method': 'action_open_payment',
        },
        'close_payment_window': {
            'model': 'date.range',
            'desc': 'إغلاق نافذة السداد والتحصيل',
            'service_model': 'date.range',
            'service_method': 'action_close_payment',
        },
        'reconcile_payment': {
            'model': 'date.range',
            'desc': 'مطابقة المقبوضات والتحصيل',
            'service_model': 'date.range',
            'service_method': 'action_reconcile_payment',
        },
        'start_billing': {
            'model': 'date.range',
            'desc': 'بدء الفوترة الدورية للفترة',
            'service_model': 'date.range',
            'service_method': 'action_start_billing',
        },
        'reconcile_and_close': {
            'model': 'date.range',
            'desc': 'المطابقة والإغلاق النهائي للفترة',
            'service_model': 'date.range',
            'service_method': 'action_close_period',
        },
        'trigger_reading_workflow': {
            'model': 'date.range',
            'desc': 'بدء مسار عمل فترة القراءة',
            'service_model': 'date.range',
            'service_method': 'action_open_reading',
        },
        'trigger_payment_workflow': {
            'model': 'date.range',
            'desc': 'بدء مسار عمل فترة السداد والتحصيل',
            'service_model': 'date.range',
            'service_method': 'action_open_payment',
        },
    }

    @api.model
    def _get_workflow_adapter(self):
        """
        الحصول على المحول النشط دون fallback صامت.
        - local     : LocalWorkflowAdapter     (الافتراضي)
        - queue_job : QueueJobWorkflowAdapter  (OCA Queue Job الموزع)
        - temporal  : TemporalWorkflowAdapter  (Placeholder غير جاهز)
        """
        adapter_type = self.env['ir.config_parameter'].sudo().get_param('utility.workflow_adapter', 'local')
        if adapter_type == 'local':
            from ..adapters.workflow.local import LocalWorkflowAdapter
            return LocalWorkflowAdapter(self.env)
        elif adapter_type == 'queue_job':
            from ..adapters.workflow.queue_job import QueueJobWorkflowAdapter
            return QueueJobWorkflowAdapter(self.env)
        elif adapter_type == 'temporal':
            from ..adapters.workflow.temporal import TemporalWorkflowAdapter
            if not getattr(TemporalWorkflowAdapter, 'PRODUCTION_READY', False):
                raise UserError(_(
                    "محول Temporal Workflow غير جاهز للإنتاج حالياً (Placeholder Contract). "
                    "يُرجى استخدام Local Odoo Outbox أو OCA Queue Job."
                ))
            return TemporalWorkflowAdapter(self.env)
        else:
            raise UserError(_("نوع محول مسارات العمل غير معروف: %s") % adapter_type)

    @api.model
    def dispatch(self, workflow_type, reference_model, reference_id, payload=None, idempotency_key=None, priority=10):
        """
        المدخل المركزي المعتمد لإطلاق أوامر مسارات العمل:
        1. التحقق الصارم من وجود نوع المسار ومطابقة النموذج المرجعي المعتمد في السجل (Registry Validation).
        2. التحقق من وجود السجل المستهدف في قاعدة البيانات.
        3. تمرير الأمر إلى المحول النشط مع ضمان عدم التكرار.
        """
        reg = self.WORKFLOW_REGISTRY.get(workflow_type)
        if not reg:
            raise ValidationError(_("نوع مسار العمل غير مسجل في النظام: %s") % workflow_type)

        allowed_model = reg.get('model')
        if allowed_model and allowed_model != reference_model:
            raise ValidationError(
                _("النموذج المرجعي (%s) غير مطابق للنموذج المعتمد (%s) لمسار العمل (%s).")
                % (reference_model, allowed_model, workflow_type)
            )

        record = self.env[reference_model].browse(reference_id).exists()
        if not record:
            raise ValidationError(_("السجل المرجعي المستهدف (%s, ID: %s) غير موجود في النظام.") % (reference_model, reference_id))

        if not idempotency_key:
            idempotency_key = f"{workflow_type.upper()}:{reference_model}:{reference_id}"

        adapter = self._get_workflow_adapter()
        return adapter.dispatch(
            workflow_type=workflow_type,
            reference_model=reference_model,
            reference_id=reference_id,
            payload=payload,
            idempotency_key=idempotency_key,
            priority=priority,
        )

    @api.model
    def _execute_workflow_handler(self, workflow_type, reference_model, reference_id, payload_json=None):
        """
        استدعاء خدمة الأعمال القابلة لإعادة الاستخدام (Reusable Business Service):
        - إذا كان service_model هو نفسه reference_model: يتم جلب السجل المحدد واستدعاء الدالة على الـ Recordset مباشرة.
        - إذا كان service_model مخدم أعمال مستقل: يتم استدعاء دالة المخدم وتمرير reference_id كمعامل أساسي.
        """
        reg = self.WORKFLOW_REGISTRY.get(workflow_type)
        if not reg:
            raise ValidationError(_("لا توجد خدمة أعمال مسجلة لمعالجة نوع مسار العمل: %s") % workflow_type)

        target_model = reg.get('service_model') or reference_model
        method_name = reg.get('service_method')

        if target_model == reference_model:
            rec = self.env[reference_model].browse(reference_id).exists()
            if not rec:
                raise ValidationError(_("السجل المرجعي المستهدف (%s, ID: %s) غير موجود.") % (reference_model, reference_id))
            if not hasattr(rec, method_name):
                raise ValidationError(_("الدالة التنفيذية (%s) غير موجودة في النموذج (%s).") % (method_name, reference_model))
            return getattr(rec, method_name)()
        else:
            service = self.env[target_model]
            if not hasattr(service, method_name):
                raise ValidationError(_("الدالة التنفيذية (%s) غير موجودة في مخدم الأعمال (%s).") % (method_name, target_model))
            return getattr(service, method_name)(reference_id)

    # -------------------------------------------------------------------------
    # Backward Compatibility Forwarders
    # -------------------------------------------------------------------------
    @api.model
    def trigger_reading_period_workflow(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        if not period:
            raise ValidationError(_("الفترة المطلوبة غير موجودة."))
        return self.dispatch(
            workflow_type='trigger_reading_workflow',
            reference_model='date.range',
            reference_id=period.id,
            payload={'period_id': period.id, 'period_code': period.period_code},
            idempotency_key=f"TRIGGER_READING_WORKFLOW:{period.period_code}"
        )

    @api.model
    def trigger_payment_period_workflow(self, payment_period_id):
        payment_period = self.env['date.range'].browse(payment_period_id).exists()
        if not payment_period:
            raise ValidationError(_("فترة السداد المطلوبة غير موجودة."))
        return self.dispatch(
            workflow_type='trigger_payment_workflow',
            reference_model='date.range',
            reference_id=payment_period.id,
            payload={'period_id': payment_period.id, 'period_code': payment_period.period_code},
            idempotency_key=f"TRIGGER_PAYMENT_WORKFLOW:{payment_period.period_code}"
        )

    @api.model
    def execute_open_reading_window(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='open_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"OPEN_READING_WINDOW:{period.period_code}"
        )

    @api.model
    def execute_close_reading_window(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='close_reading_window',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"CLOSE_READING_WINDOW:{period.period_code}"
        )

    @api.model
    def execute_start_billing(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='start_billing',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"START_BILLING:{period.period_code}"
        )

    @api.model
    def execute_reconcile_and_close(self, period_id):
        period = self.env['date.range'].browse(period_id).exists()
        return self.dispatch(
            workflow_type='reconcile_and_close',
            reference_model='date.range',
            reference_id=period.id,
            idempotency_key=f"RECONCILE_AND_CLOSE:{period.period_code}"
        )

    @api.model
    def dispatch_batch_command(self, batch, payload_func=None, is_retry=False):
        adapter = self._get_workflow_adapter()
        return adapter.dispatch_batch_command(batch, payload_func=payload_func, is_retry=is_retry)
