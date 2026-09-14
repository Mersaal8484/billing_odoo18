import logging
from psycopg2 import IntegrityError
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.utility_core.models.utility_date_range import normalize_billing_cadence

_logger = logging.getLogger(__name__)


class UtilityReading(models.Model):
    _inherit = 'utility.reading'

    batch_id = fields.Many2one('utility.reading.batch', 'الدفعة', readonly=True, index=True)
    is_billable = fields.Boolean(
        string='قراءة قابلة للفوترة',
        compute='_compute_is_billable',
        store=True,
        index=True,
    )
    billing_anchor_id = fields.Many2one(
        'utility.reading', 'القراءة الدورية المرتبطة', index=True,
        readonly=True, copy=False, ondelete='restrict',
    )
    billing_component_ids = fields.One2many(
        'utility.reading', 'billing_anchor_id', 'قراءات الإغلاق المضمّنة',
    )
    included_sale_order_id = fields.Many2one(
        'sale.order', 'الفاتورة المتضمنة', index=True, readonly=True,
        copy=False, ondelete='restrict',
    )
    carried_consumption = fields.Float(
        'استهلاك مرحل', compute='_compute_billing_consumption', store=True,
    )
    billing_consumption = fields.Float(
        'استهلاك الفاتورة', compute='_compute_billing_consumption', store=True,
    )
    billing_error = fields.Text('خطأ الفوترة', readonly=True)

    def init(self):
        """Keep core performance and review query indexes."""
        super().init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_review_state_billable_date_idx
            ON utility_reading (state, is_billable, reading_date DESC, id DESC);
        """)

    def _is_commercial_subject(self):
        """Return whether the reading belongs to a billable subject."""
        self.ensure_one()
        return (
            self.reading_category == 'customer'
            or (
                self.reading_category == 'transformer'
                and self.is_private_transformer
            )
        )

    def _canonical_reading_purpose(self):
        self.ensure_one()
        return 'closing' if self.reading_purpose == 'replacement_closing' else self.reading_purpose

    def _is_replacement_reading(self):
        self.ensure_one()
        return self.reading_event == 'replacement' or self.reading_purpose == 'replacement_closing'

    def _is_billable_reading(self):
        """Return whether this reading directly creates a postpaid bill."""
        self.ensure_one()
        return self._is_commercial_subject() and self.reading_purpose == 'periodic'

    def _requires_billing_review(self):
        self.ensure_one()
        return self.is_billable

    @api.depends('reading_category', 'reading_purpose', 'is_private_transformer')
    def _compute_is_billable(self):
        for reading in self:
            reading.is_billable = reading._is_billable_reading()

    @api.depends('consumption', 'reading_purpose', 'billing_component_ids.consumption')
    def _compute_billing_consumption(self):
        for reading in self:
            if reading.reading_purpose == 'periodic':
                reading.carried_consumption = sum(reading.billing_component_ids.mapped('consumption'))
                reading.billing_consumption = reading.consumption + reading.carried_consumption
            else:
                reading.carried_consumption = 0.0
                reading.billing_consumption = 0.0

    @api.constrains('account_id', 'date_range_id', 'state', 'reading_category', 'reading_purpose', 'active')
    def _check_unique_billable_reading_per_period(self):
        """Prevent duplicate active periodic readings for one account and period."""
        for reading in self.filtered(lambda rec: rec.is_billable and rec.date_range_id and rec.active):
            duplicate = self.search([
                ('account_id', '=', reading.account_id.id),
                ('date_range_id', '=', reading.date_range_id.id),
                ('reading_purpose', '=', 'periodic'),
                ('reading_category', '=', reading.reading_category),
                ('active', '=', True),
                ('id', '!=', reading.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'يوجد قراءة دورية أخرى للحساب [%s] في فترة الفوترة [%s].'
                ) % (reading.account_id.display_name, reading.date_range_id.name))

    @api.constrains('reading_purpose', 'date_range_id', 'billing_anchor_id', 'account_id', 'reading_date')
    def _check_billing_reading_rules(self):
        """Validate billing-specific period and component invariants."""
        for reading in self:
            if reading.is_billable:
                if not reading.account_id:
                    raise ValidationError(_('القراءة القابلة للفوترة تتطلب حساب مشترك.'))
                if not reading.date_range_id:
                    raise ValidationError(_('القراءة الدورية تتطلب تحديد الفترة المفتوحة للقراءة بحسب العقد.'))
                period = reading.date_range_id
                expected = reading.account_id._get_effective_billing_period()
                if period.period_role and period.period_role != 'reading':
                    raise ValidationError(_('فترة القراءة الدورية يجب أن تكون من نوع قراءات.'))
                cadence = period.billing_cadence or getattr(period, 'billing_period', False)
                if expected and cadence and normalize_billing_cadence(cadence) != normalize_billing_cadence(expected):
                    raise ValidationError(_(
                        'دورية الفترة المختارة (%s) لا تطابق دورية المشترك (%s).'
                    ) % (cadence, expected))
            anchor = reading.billing_anchor_id
            if anchor and (
                    anchor.reading_purpose != 'periodic'
                    or anchor.account_id != reading.account_id
                    or anchor.reading_date < reading.reading_date):
                raise ValidationError(_('يجب أن تكون قراءة الربط دورية ولاحقة ومن حساب المشترك نفسه.'))

    def _check_billing_period_mutation(self, vals=None):
        """Prevent ordinary reading changes after the billing period is closed."""
        if (self.env.context.get('allow_billing_adjustment')
                or self.env.context.get('_bypass_reading_protection')):
            return
        if self.filtered(lambda reading: getattr(reading.date_range_id, 'reading_state', False) in ('closed', 'locked') or reading.date_range_id.state in ('closed', 'locked')):
            raise ValidationError(_(
                'لا يمكن تعديل قراءة مرتبطة بفترة مغلقة أو مقفلة. '
                'استخدم مسار تعديل الفوترة المعتمد.'))

    @api.model_create_multi
    def create(self, vals_list):
        period_ids = [vals.get('date_range_id') for vals in vals_list if vals.get('date_range_id')]
        if period_ids and not self.env.context.get('allow_billing_adjustment'):
            closed = self.env['date.range'].search([
                ('id', 'in', period_ids),
                '|',
                ('reading_state', 'in', ('closed', 'locked')),
                ('state', 'in', ('closed', 'locked')),
            ], limit=1)
            if closed:
                raise ValidationError(_(
                    'لا يمكن إنشاء قراءة في الفترة المغلقة أو المقفلة [%s].') % closed.name)
        try:
            with self.env.cr.savepoint():
                return super().create(vals_list)
        except IntegrityError as e:
            err_str = f"{str(e)} {getattr(e, 'pgerror', '')}"
            if 'utility_reading_unique_periodic_account_period_idx' in err_str:
                raise ValidationError(_('يوجد قراءة دورية أخرى مسجلة مسبقاً لنفس الحساب والفترة.'))
            raise

    def write(self, vals):
        self._check_billing_period_mutation(vals)
        return super().write(vals)

    def _queue_approved_billable_readings(self):
        """Transition eligible approved periodic readings into the queued billing state
        and immediately generate bills for each reading.

        Bill generation is performed synchronously so the customer receives
        their bill without waiting for the next cron cycle.
        """
        billable_readings = self.filtered(
            lambda reading: reading.state == 'approved'
            and reading.reading_purpose == 'periodic'
            and reading.is_billable
            and (
                reading.reading_category == 'customer'
                or (
                    reading.reading_category == 'transformer'
                    and reading.is_private_transformer
                )
            )
        )
        if not billable_readings:
            return self

        for reading in billable_readings:
            if not reading.date_range_id:
                period = reading._resolve_eligible_billing_date_range()
                reading.sudo().with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({'date_range_id': period.id})

            reading.sudo().with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                'state': 'queued',
                'billing_error': False,
            })

            try:
                with self.env.cr.savepoint():
                    reading.sudo().action_generate_bill()
            except (UserError, ValidationError, AccessError) as exc:
                reading.sudo().with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                    'state': 'error',
                    'billing_error': str(exc),
                })
                _logger.warning(
                    'Immediate bill generation failed for reading %s: %s',
                    reading.display_name,
                    exc,
                )

        return self

    def action_approve(self):
        """Approve readings and immediately enqueue billable periodic readings."""
        result = super().action_approve()
        self._queue_approved_billable_readings()
        return result

    def _get_billing_period_type(self):
        self.ensure_one()
        recurring_type = (
            self.account_id._get_effective_billing_period()
            if self.account_id else False
        )
        return normalize_billing_cadence(recurring_type)

    def _get_current_billing_date_range(self):
        self.ensure_one()
        billing_period = self._get_billing_period_type()
        domain = [
            ('is_current_period', '=', True),
            ('work_type', '=', 'readings'),
            ('state', '=', 'open'),
        ]
        if billing_period:
            domain.append(('billing_period', '=', billing_period))
        period = self.env['date.range'].search(domain, limit=1)
        return period

    def _resolve_eligible_billing_date_range(self):
        """Find the exact matching open date range for this reading's date and scope.

        Replaces broad/arbitrary fallbacks with a strict domain search matching:
        - work_type == 'readings'
        - state == 'open' (strictly open)
        - company_id matches reading's company or env.company
        - date_start <= reading_date <= date_end
        - billing_period matching account's billing period if configured
        - strict geographic scoping: must belong to the reading's region or be global (region_ids is empty).
          NEVER falls back to picking another region's period.
        """
        self.ensure_one()
        DateRange = self.env['date.range']
        reading_date = self.reading_date.date() if self.reading_date else fields.Date.today()
        billing_period = self._get_billing_period_type()

        base_domain = [
            ('work_type', '=', 'readings'),
            ('state', '=', 'open'),
            ('company_id', 'in', (False, self.company_id.id or self.env.company.id)),
        ]
        if billing_period:
            base_domain.append(('billing_period', '=', billing_period))

        covering_domain = base_domain + [
            ('date_start', '<=', reading_date),
            ('date_end', '>=', reading_date),
        ]

        # 1. Match region if reading has region
        reading_region = getattr(self, 'region_id', False) or (self.customer_id and getattr(self.customer_id, 'region_id', False)) or (self.account_id and getattr(self.account_id, 'region_id', False))
        if reading_region:
            # First match period explicitly assigned to this region
            period = DateRange.search(covering_domain + [('region_ids', 'in', reading_region.id)], order='date_start desc', limit=1)
            if period:
                return period
            # Fallback only to a truly global period with no regional restriction
            period = DateRange.search(covering_domain + [('region_ids', '=', False)], order='date_start desc', limit=1)
            if period:
                return period
        else:
            # If reading has no region, match global period only
            period = DateRange.search(covering_domain + [('region_ids', '=', False)], order='date_start desc', limit=1)
            if period:
                return period

        # 2. Check current open period if it covers the date and region
        current_domain = base_domain + [('is_current_period', '=', True)]
        if reading_region:
            current_domain += ['|', ('region_ids', '=', False), ('region_ids', 'in', reading_region.id)]
        else:
            current_domain += [('region_ids', '=', False)]

        period = DateRange.search(current_domain, order='date_start desc', limit=1)
        if period and period.date_start and period.date_end and period.date_start <= reading_date <= period.date_end:
            return period

        raise ValidationError(_(
            'لا توجد فترة قراءات مفتوحة ومؤهلة تغطي تاريخ القراءة (%(date)s) للعميل (%(customer)s). '
            'يرجى فتح أو تهيئة فترة قراءات مناسبة قبل إنشاء الفاتورة.'
        ) % {
            'date': reading_date,
            'customer': self.account_id.display_name if self.account_id else (self.customer_id.display_name if self.customer_id else self.display_name),
        })

    def _get_unbilled_closing_components(self):
        """Return approved replacement closings eligible for this periodic bill."""
        self.ensure_one()
        last_periodic = self.search([
            ('account_id', '=', self.account_id.id),
            ('reading_purpose', '=', 'periodic'),
            ('state', '=', 'billed'),
            ('reading_date', '<', self.reading_date),
            ('id', '!=', self.id),
        ], order='reading_date desc, id desc', limit=1)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', self.account_id.id),
            ('reading_purpose', '=', 'replacement_closing'),
            ('state', '=', 'approved'),
            ('billing_anchor_id', '=', False),
            ('included_sale_order_id', '=', False),
            ('reading_date', '<=', self.reading_date),
        ]
        if last_periodic:
            domain.append(('reading_date', '>', last_periodic.reading_date))
        return self.search(domain, order='reading_date, id')

    def _lock_closing_components(self, closings):
        """Serialize closing components so two concurrent bills cannot both claim them."""
        if not closings:
            return closings
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM utility_reading WHERE id IN %s FOR UPDATE',
            [tuple(closings.ids)],
        )
        closings.invalidate_cache(['billing_anchor_id', 'included_sale_order_id'])
        claimed = closings.filtered(lambda reading: reading.billing_anchor_id or reading.included_sale_order_id)
        if claimed:
            raise ValidationError(_('تم تضمين قراءة استبدال في فاتورة أخرى بالفعل.'))
        return closings

    def _prepare_component_vals(self, order, readings):
        self.ensure_one()
        return [{
            'sale_order_id': order.id,
            'reading_id': reading.id,
            'account_id': self.account_id.id,
            'meter_id': reading.meter_id.id,
            'period_start': self.date_range_id.date_start or (
                self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today()),
            'period_end': self.date_range_id.date_end or (
                self.reading_date.date() if self.reading_date else fields.Date.today()),
            'previous_reading': reading.previous_reading,
            'current_reading': reading.reading_value,
            'meter_multiplier': reading.meter_multiplier or 1.0,
            'consumption': reading.consumption,
            'company_id': reading.company_id.id,
        } for reading in readings]

    def _action_generate_periodic_bill(self):
        """Create one bill from a periodic reading and pending closing segments."""
        if not (self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_revenue_manager')
                or self.env.user.has_group('utility_core.group_utility_supervisor')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية إصدار فواتير الكهرباء. يتطلب صلاحية مشرف أو مدير فوترة أو مدير النظام.'))

        self.ensure_one()
        if self.state == 'billed' or self.included_sale_order_id:
            if self.included_sale_order_id and self.included_sale_order_id.state != 'cancel':
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sale.order',
                    'res_id': self.included_sale_order_id.id,
                    'views': [(False, 'form')],
                }
            raise ValidationError(_('هذه القراءة مفوترة بالفعل مسبقاً.'))

        if self.reading_purpose != 'periodic':
            raise ValidationError(_('لا يمكن إنشاء فاتورة إلا من قراءة دورية.'))
        if self.state not in ('approved', 'queued'):
            raise ValidationError(_('يجب اعتماد القراءة الدورية قبل إنشاء الفاتورة.'))
        if not self.date_range_id:
            period = self._resolve_eligible_billing_date_range()
            self.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({'date_range_id': period.id})
        
        if self.date_range_id.state in ('closed', 'locked'):
            raise ValidationError(_('فترة القراءة (%s) في حالة (%s) وتمنع إنشاء فواتير جديدة.') % (self.date_range_id.name, self.date_range_id.state))

        # Serialize the check-and-create sequence so two billing workers cannot
        # both pass the duplicate search for the same periodic reading.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM utility_reading WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.invalidate_recordset(['state', 'included_sale_order_id'])
        existing = self.env['sale.order'].search([
            ('reading_id', '=', self.id), ('state', '!=', 'cancel')], limit=1)
        if existing:
            raise ValidationError(_('تم إنشاء فاتورة لهذه القراءة مسبقاً.'))

        closings = self._lock_closing_components(
            self._get_unbilled_closing_components())
        total_consumption = self.consumption + sum(closings.mapped('consumption'))
        template = self.account_id.contract_template_id
        version = template._get_or_create_active_version() if template else False
        try:
            with self.env.cr.savepoint():
                order = self.env['sale.order'].create({
                    'partner_id': self.account_id.partner_id.id or self.env.company.partner_id.id,
                    'customer_id': self.account_id.id,
                    'meter_id': self.meter_id.id,
                    'reading_id': self.id,
                    'date_range_id': self.date_range_id.id,
                    'date_order': fields.Datetime.now(),
                    'period_start': self.date_range_id.date_start or (
                        self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today()),
                    'period_end': self.date_range_id.date_end or (
                        self.reading_date.date() if self.reading_date else fields.Date.today()),
                    'previous_reading': self.previous_reading,
                    'current_reading': self.reading_value,
                    'consumption': total_consumption,
                    'contract_template_id': template.id if template else False,
                    'contract_template_version_id': version.id if version else False,
                })
        except IntegrityError as e:
            err_str = f"{str(e)} {getattr(e, 'pgerror', '')}"
            if 'utility_sale_order_unique_active_reading_idx' in err_str:
                raise ValidationError(_('تم إنشاء فاتورة نشطة لهذه القراءة مسبقاً.'))
            raise
        all_components = closings | self
        self.env['utility.bill.reading.component'].create(
            self._prepare_component_vals(order, all_components))
        if closings:
            closings.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                'billing_anchor_id': self.id,
                'included_sale_order_id': order.id,
                'state': 'billed',
            })
        self.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'included_sale_order_id': order.id,
        })
        if template:
            order._calculate_amounts()
        order.action_confirm()
        invoices = order._create_invoices()
        invoices.action_post()
        if self.image_asset_id and self.image_asset_id.original_attachment_id:
            order.attachment_id = self.image_asset_id.original_attachment_id
        elif self.attachment_id:
            order.attachment_id = self.attachment_id
        self.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'billed', 'billing_error': False,
        })
        self.account_id.write({
            'last_invoice_date': fields.Datetime.now(),
            'last_invoice_reading': self.reading_value,
            'last_reading_date': self.reading_date,
            'last_reading_value': self.reading_value,
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order',
            'res_id': order.id, 'views': [(False, 'form')],
        }

    def action_generate_bill(self):
        return self._action_generate_periodic_bill()

    def action_generate_bills_batch(self):
        if not (self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية إصدار فواتير الكهرباء. يتطلب صلاحية مدير الفوترة أو مدير النظام.'))

        readings = self.filtered(lambda r: r.reading_purpose == 'periodic' and r.date_range_id and r.state == 'approved' and r.is_billable and (
            r.reading_category == 'customer' or
            (r.reading_category == 'transformer' and r.is_private_transformer)
        ))
        if not readings:
            raise ValidationError('لا توجد قراءات معتمدة قابلة للفوترة!')
        readings.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
            'state': 'queued',
            'billing_error': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'طابور الفوترة',
                'message': f'تم إرسال {len(readings)} قراءة إلى طابور الفوترة. سيتم معالجتها تلقائياً.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_queue_approved_readings(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_queue_batch_size', 1000))
        readings = self.search([
            ('state', '=', 'approved'),
            ('reading_purpose', '=', 'periodic'),
            ('date_range_id', '!=', False),
            ('is_billable', '=', True),
            '|',
            ('reading_category', '=', 'customer'),
            '&',
            ('reading_category', '=', 'transformer'),
            ('is_private_transformer', '=', True),
        ], limit=batch_size, order='reading_date asc, id asc')
        if readings:
            readings.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                'state': 'queued',
                'billing_error': False,
            })
        return len(readings)

    def action_requeue(self):
        for r in self:
            if r.state != 'error':
                raise ValidationError('يمكن إعادة المحاولة فقط للقراءات التي بها خطأ!')
            r.with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                'state': 'queued',
                'billing_error': False,
            })

    @api.model
    def _cron_generate_bills(self):
        batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
            'utility.billing_batch_size', 500))
        readings = self.search([('state', '=', 'queued'), ('reading_purpose', '=', 'periodic')], limit=batch_size)
        if not readings:
            return

        success_count = 0
        error_count = 0
        for reading in readings:
            try:
                with self.env.cr.savepoint():
                    reading.sudo().action_generate_bill()
                success_count += 1
            except (UserError, ValidationError, AccessError) as exc:
                reading.sudo().with_context(_reading_state_transition=True, _bypass_reading_protection=True).write({
                    'state': 'error',
                    'billing_error': str(exc),
                })
                _logger.warning(
                    'Bill generation business failure for reading %s: %s',
                    reading.display_name,
                    exc,
                )
                error_count += 1
        _logger.info(
            'Billing cron processed %d readings: %d success, %d failed',
            len(readings),
            success_count,
            error_count,
        )
