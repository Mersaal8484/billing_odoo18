import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class UtilityCronExecution(models.Model):
    _name = 'utility.cron.execution'
    _description = 'سجل تنفيذ المهمة المجدولة / Utility Cron Execution Log'
    _order = 'started_at desc, id desc'
    _rec_name = 'display_name'

    cron_id = fields.Many2one(
        'ir.cron',
        string='المهمة المجدولة / Cron Job',
        required=True,
        ondelete='cascade',
        index=True,
    )
    utility_code = fields.Char(
        string='رمز المهمة / Utility Code',
        index=True,
    )
    utility_category = fields.Selection(
        related='cron_id.utility_category',
        string='التصنيف / Category',
        store=True,
        index=True,
    )

    started_at = fields.Datetime(
        string='وقت البدء / Started At',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    finished_at = fields.Datetime(
        string='وقت الانتهاء / Finished At',
    )
    duration_seconds = fields.Float(
        string='المدة (ثواني) / Duration (s)',
        digits=(12, 3),
        readonly=True,
    )
    trigger_type = fields.Selection([
        ('scheduled', 'مجدول آلياً / Scheduled'),
        ('manual', 'تشغيل يدوي / Manual'),
    ], string='نوع المشغل / Trigger Type', required=True, default='scheduled', index=True)

    triggered_by = fields.Many2one(
        'res.users',
        string='تم التشغيل بواسطة / Triggered By',
        default=lambda self: self.env.user,
        index=True,
    )
    status = fields.Selection([
        ('running', 'قيد التنفيذ / Running'),
        ('success', 'ناجح / Success'),
        ('partial', 'ناجح جزئياً / Partial'),
        ('failed', 'فاشل / Failed'),
        ('skipped', 'تم التخطي (قفل التزامن) / Skipped (Lock)'),
        ('reset', 'تصفير عداد الأخطاء / Counter Reset'),
    ], string='الحالة / Status', required=True, default='running', index=True)

    processed_count = fields.Integer(
        string='إجمالي المعالج / Processed',
        default=0,
    )
    success_count = fields.Integer(
        string='الناجح / Success',
        default=0,
    )
    failure_count = fields.Integer(
        string='الفاشل / Failed',
        default=0,
    )
    skipped_count = fields.Integer(
        string='المتخطى / Skipped',
        default=0,
    )

    error_message = fields.Text(
        string='رسالة الخطأ / Error Message',
    )
    error_details = fields.Text(
        string='تفاصيل الخطأ / Error Details',
    )
    company_id = fields.Many2one(
        'res.company',
        string='الشركة / Company',
        default=lambda self: self.env.company,
    )

    display_name = fields.Char(
        string='اسم السجل / Display Name',
        compute='_compute_display_name',
        store=False,
    )

    @api.depends('cron_id.name', 'utility_code', 'started_at', 'status')
    def _compute_display_name(self):
        for rec in self:
            code = rec.utility_code or (rec.cron_id.name if rec.cron_id else _('غير محدد'))
            start_str = fields.Datetime.to_string(rec.started_at) if rec.started_at else ''
            rec.display_name = f"[{code}] {start_str} ({rec.status})"

    def write(self, vals):
        """Immutability guard: prevents arbitrary manual mutation of audit execution records."""
        if not self._context.get('_cron_internal_write') and not self._context.get('install_mode'):
            raise AccessError(_('سجلات تنفيذ المهام المجدولة غير قابلة للتعديل حفاظاً على مسار التدقيق / Execution logs are immutable.'))
        return super().write(vals)

    def unlink(self):
        """Allow unlink only for administrators or via retention cleanup."""
        is_admin = self.env.user.has_group('utility_core.group_utility_admin') or self.env.user.has_group('base.group_system')
        if not is_admin and not self._context.get('_cron_cleanup_mode'):
            raise AccessError(_('حذف سجلات التنفيذ مقتصر على مدراء النظام / Only Utility Administrators can delete execution history.'))
        return super().unlink()

    @api.model
    def cron_cleanup_execution_history(self, retention_days=90, batch_size=5000):
        """حذف دفعة محدودة من سجلات التنفيذ القديمة بناء على سياسة الاحتفاظ.

        The scheduled job runs daily and removes a bounded batch so cleanup
        cannot monopolize the Odoo worker. Running records are deliberately
        excluded because they are still part of the execution audit trail.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        days = int(ICP.get_param('utility.cron_history_retention_days', retention_days))
        batch_limit = int(ICP.get_param('utility.cron_history_cleanup_batch_size', batch_size))
        days = max(days, 1)
        batch_limit = max(batch_limit, 1)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        records = self.search([
            ('started_at', '<', cutoff),
            ('status', '!=', 'running'),
        ], order='started_at asc, id asc', limit=batch_limit)
        count = len(records)
        if records:
            records.with_context(_cron_cleanup_mode=True).unlink()
        _logger.info(
            "Utility Cron Cleanup: removed %d execution records older than %d days (batch limit %d)",
            count, days, batch_limit,
        )
        return {'processed': count, 'success': count, 'failed': 0, 'skipped': 0}
