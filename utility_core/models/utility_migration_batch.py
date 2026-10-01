import logging
from datetime import timedelta
from psycopg2 import OperationalError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityMigrationBatch(models.Model):
    _name = 'utility.migration.batch'
    _description = 'دفعة تنفيذ الميجريشن (Execution Batch)'
    _order = 'id desc'

    name = fields.Char(
        'رقم الدفعة', required=True, copy=False, readonly=True,
        default=lambda self: _('جديد'), index=True)
    
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)

    migration_type = fields.Selection([
        ('customer', 'عملاء'),
        ('feeder', 'فيدرات/خلايا'),
        ('transformer', 'محولات')
    ], string='نوع الميجريشن', required=True, index=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('queued', 'في الانتظار'),
        ('processing', 'قيد المعالجة'),
        ('done', 'مكتمل'),
        ('partial', 'مكتمل بنجاح جزئي'),
        ('failed', 'فشل فني'),
        ('cancelled', 'ملغى')
    ], string='الحالة', default='queued', required=True, index=True)

    chunk_size = fields.Integer(
        'حجم الدفعة الجزئية', default=200, required=True,
        help='عدد السجلات المعالجة في كل دفعة جزئية لتفادي التجاوز المفرط للذاكرة.')

    record_count = fields.Integer('إجمالي السجلات', compute='_compute_counts', store=True)
    processed_count = fields.Integer('السجلات المعالجة', compute='_compute_counts', store=True)
    success_count = fields.Integer('السجلات الناجحة', compute='_compute_counts', store=True)
    error_count = fields.Integer('سجلات الأخطاء', compute='_compute_counts', store=True)

    queued_at = fields.Datetime('تاريخ الإضافة للانتظار', default=fields.Datetime.now, readonly=True)
    started_at = fields.Datetime('تاريخ بداية المعالجة', readonly=True)
    finished_at = fields.Datetime('تاريخ انتهاء المعالجة', readonly=True)

    last_error = fields.Text('آخر خطأ فني', readonly=True)
    job_reference = fields.Char('مرجع المهمة', readonly=True)

    customer_ids = fields.One2many(
        'utility.migration.customer', 'last_batch_id', string='سجلات العملاء')
    feeder_ids = fields.One2many(
        'utility.migration.feeder', 'last_batch_id', string='سجلات الفيدرات')
    transformer_ids = fields.One2many(
        'utility.migration.transformer', 'last_batch_id', string='سجلات المحولات')

    @api.depends(
        'migration_type',
        'customer_ids.state', 'feeder_ids.state', 'transformer_ids.state'
    )
    def _compute_counts(self):
        for batch in self:
            records = batch._get_batch_records()
            batch.record_count = len(records)
            batch.success_count = len(records.filtered(lambda r: r.state == 'imported'))
            batch.error_count = len(records.filtered(lambda r: r.state == 'error'))
            batch.processed_count = batch.success_count + batch.error_count

    def _get_batch_records(self):
        self.ensure_one()
        if self.migration_type == 'customer':
            return self.customer_ids
        elif self.migration_type == 'feeder':
            return self.feeder_ids
        elif self.migration_type == 'transformer':
            return self.transformer_ids
        return self.env['utility.migration.customer']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('جديد'):
                mtype = vals.get('migration_type', 'customer')
                prefix_map = {
                    'customer': 'MIG-CUST-',
                    'feeder': 'MIG-FDR-',
                    'transformer': 'MIG-TRF-'
                }
                prefix = prefix_map.get(mtype, 'MIG-')
                seq = self.env['ir.sequence'].next_by_code('utility.migration.batch')
                if not seq:
                    count = self.search_count([('migration_type', '=', mtype)]) + 1
                    seq = f"{prefix}{count:05d}"
                vals['name'] = seq
        return super().create(vals_list)

    def _search_batch_records(self, domain=None, order='id asc', limit=None):
        """بحث في سجلات الميجريشن التابعة للدفعة باستخدام الاستعلام المباشر لقاعدة البيانات بدلاً من تحميل العلاقات كاملة للذاكرة."""
        self.ensure_one()
        model_map = {
            'customer': 'utility.migration.customer',
            'feeder': 'utility.migration.feeder',
            'transformer': 'utility.migration.transformer',
        }
        model_name = model_map.get(self.migration_type)
        if not model_name:
            return self.env['utility.migration.customer']

        base_domain = [('last_batch_id', '=', self.id)]
        if domain:
            base_domain += domain

        return self.env[model_name].search(base_domain, order=order, limit=limit)

    def action_process_batch(self, max_records_per_run=1000):
        """معالجة الدفعة في خلفية النظام على دفعات جزئية (Chunked execution) محددة لكل دورة لتجنب تجاوز المهلة."""
        for batch in self:
            if batch.state in ('done', 'cancelled'):
                continue

            if not batch.started_at:
                batch.started_at = fields.Datetime.now()
            batch.state = 'processing'

            # Query strictly the pending records intended for this run via ORM search with limit
            run_records = batch._search_batch_records(
                domain=[('state', 'in', ('queued', 'processing'))],
                order='id asc',
                limit=max_records_per_run
            )

            if not run_records:
                has_pending = bool(batch._search_batch_records(
                    domain=[('state', 'in', ('queued', 'processing'))],
                    limit=1
                ))
                if not has_pending:
                    records = batch._get_batch_records()
                    err_count = len(records.filtered(lambda r: r.state == 'error'))
                    imp_count = len(records.filtered(lambda r: r.state == 'imported'))

                    if err_count == 0 and imp_count > 0:
                        batch.state = 'done'
                    elif imp_count > 0 and err_count > 0:
                        batch.state = 'partial'
                    elif imp_count == 0 and err_count > 0:
                        batch.state = 'partial'
                    else:
                        batch.state = 'done'
                    batch.finished_at = fields.Datetime.now()
                continue

            chunk_size = max(1, batch.chunk_size or 200)

            try:
                for i in range(0, len(run_records), chunk_size):
                    chunk = run_records[i:i + chunk_size]
                    for rec in chunk:
                        with self.env.cr.savepoint():
                            rec.state = 'processing'
                            rec.action_import_data()

            except Exception as e:
                batch.last_error = str(e)
                batch.state = 'failed'
                batch.finished_at = fields.Datetime.now()
                continue

            # Re-evaluate remaining pending records in batch via fast search (limit=1)
            has_remaining_pending = bool(batch._search_batch_records(
                domain=[('state', 'in', ('queued', 'processing'))],
                limit=1
            ))

            if has_remaining_pending:
                # Still pending records left for subsequent cron runs -> reset state to queued
                batch.state = 'queued'
            else:
                # All records evaluated
                records = batch._get_batch_records()
                err_count = len(records.filtered(lambda r: r.state == 'error'))
                imp_count = len(records.filtered(lambda r: r.state == 'imported'))

                if err_count == 0 and imp_count > 0:
                    batch.state = 'done'
                elif imp_count > 0 and err_count > 0:
                    batch.state = 'partial'
                elif imp_count == 0 and err_count > 0:
                    batch.state = 'partial'
                else:
                    batch.state = 'done'
                batch.finished_at = fields.Datetime.now()

    # TEMPORARY TEST-ONLY:
    # Manual synchronous execution for migration verification.
    # Normal production execution must remain queued/background via Cron.
    # Remove or disable before final Production Release Gate.
    def action_run_now(self):
        """تنفيذ الدفعة فوراً ⚠ للاختبار فقط."""
        if not self.env.user.has_group('utility_core.group_utility_admin'):
            raise UserError(_('هذا الإجراء مخصص لمدراء النظام فقط لأغراض الاختبار اليدوي.'))
        for batch in self:
            if batch.state in ('done', 'cancelled', 'processing'):
                raise UserError(_('لا يمكن تنفيذ الدفعة اليدوي في حالتها الحالية (%s).') % batch.state)
            batch.action_process_batch()
        return True

    def action_open_records(self):
        self.ensure_one()
        records = self._get_batch_records()
        model_map = {
            'customer': 'utility.migration.customer',
            'feeder': 'utility.migration.feeder',
            'transformer': 'utility.migration.transformer',
        }
        res_model = model_map[self.migration_type]
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجلات الدفعة (%s)') % self.name,
            'res_model': res_model,
            'domain': [('id', 'in', records.ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_open_errors(self):
        self.ensure_one()
        records = self._get_batch_records().filtered(lambda r: r.state == 'error')
        model_map = {
            'customer': 'utility.migration.customer',
            'feeder': 'utility.migration.feeder',
            'transformer': 'utility.migration.transformer',
        }
        res_model = model_map[self.migration_type]
        return {
            'type': 'ir.actions.act_window',
            'name': _('سجلات الأخطاء للدفعة (%s)') % self.name,
            'res_model': res_model,
            'domain': [('id', 'in', records.ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_retry_errors(self):
        self.ensure_one()
        errored_records = self._get_batch_records().filtered(lambda r: r.state == 'error')
        if not errored_records:
            raise UserError(_('لا توجد سجلات أخطاء لإعادة محاولتها في هذه الدفعة.'))
        return errored_records.action_queue_migration()

    def action_cancel(self):
        for batch in self:
            if batch.state == 'done':
                raise UserError(_('لا يمكن إلغاء دفعة مكتملة بالفعل.'))
            pending_records = batch._get_batch_records().filtered(
                lambda r: r.state in ('queued', 'processing')
            )
            pending_records.write({
                'state': 'draft',
                'error_message': _('تم إلغاء عملية الدفعة (%s)') % batch.name
            })
            batch.write({
                'state': 'cancelled',
                'finished_at': fields.Datetime.now(),
            })

    @api.model
    def cron_process_pending_batches(self):
        """Cron function processing queued or stuck processing migration batches in background."""
        stuck_threshold = fields.Datetime.now() - timedelta(minutes=15)
        domain = [
            '|',
            ('state', '=', 'queued'),
            '&', ('state', '=', 'processing'), ('started_at', '<', stuck_threshold)
        ]
        pending = self.search(domain, order='id asc', limit=10)
        for batch in pending:
            try:
                self.env.cr.execute(
                    "SELECT id FROM utility_migration_batch WHERE id = %s FOR UPDATE NOWAIT",
                    (batch.id,)
                )
                # Keep cron transactions short. Customer migration creates a
                # partner, account, meter, reading and accounting entry per row.
                # Processing 1,000 rows in one cron transaction can prevent the
                # scheduler from reaching its next cycle on Windows/PostgreSQL.
                batch.action_process_batch(max_records_per_run=100)
            except OperationalError as e:
                if getattr(e, 'pgcode', None) == '55P03':
                    _logger.debug("Batch %s (%s) is currently locked by another worker process (55P03).", batch.id, batch.name)
                else:
                    _logger.warning("OperationalError locking batch %s (%s): %s", batch.id, batch.name, e)
                continue
            except Exception as e:
                _logger.error("Unexpected error processing migration batch %s (%s): %s", batch.id, batch.name, e)
                continue

