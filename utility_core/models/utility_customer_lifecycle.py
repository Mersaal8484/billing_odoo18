from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError


CUSTOMER_STATE_SELECTION = [
    ('draft', 'مسودة'), ('active', 'فعال'), ('suspended', 'موقوف'),
    ('disconnected', 'مفصول'), ('closed', 'مغلق'),
]


class UtilityCustomerMeterAssignment(models.Model):
    _name = 'utility.customer.meter.assignment'
    _description = 'تاريخ تخصيص عداد الحساب الكهربائي'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    customer_id = fields.Many2one(
        'utility.customer', required=True, ondelete='cascade', index=True,
        tracking=True)
    meter_id = fields.Many2one(
        'utility.meter', required=True, ondelete='restrict', index=True,
        tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    date_from = fields.Datetime('من تاريخ', required=True, default=fields.Datetime.now)
    date_to = fields.Datetime('إلى تاريخ')
    initial_reading = fields.Float('القراءة الافتتاحية', digits=(12, 3))
    final_reading = fields.Float('القراءة الختامية', digits=(12, 3))
    assignment_type = fields.Selection([
        ('initial_installation', 'تركيب أولي'),
        ('replacement', 'استبدال'),
        ('temporary', 'مؤقت'),
        ('reinstallation', 'إعادة تركيب'),
        ('migration', 'ترحيل'),
        ('other', 'أخرى'),
    ], string='نوع التخصيص', required=True, default='initial_installation')
    installed_by_id = fields.Many2one('res.users', string='ركّب بواسطة', default=lambda self: self.env.user)
    removed_by_id = fields.Many2one('res.users', string='أزيل بواسطة')
    reason = fields.Char('السبب')
    notes = fields.Text('ملاحظات')
    state = fields.Selection([
        ('open', 'حالي'), ('closed', 'مغلق'), ('cancelled', 'ملغى'),
    ], string='الحالة', required=True, default='open', tracking=True, index=True)

    _sql_constraints = [
        ('assignment_dates_valid',
         'CHECK(date_to IS NULL OR date_to >= date_from)',
         'تاريخ إغلاق تخصيص العداد يجب ألا يسبق تاريخ بدايته.'),
        ('assignment_readings_valid',
         'CHECK(final_reading IS NULL OR final_reading >= initial_reading)',
         'القراءة الختامية يجب ألا تقل عن القراءة الافتتاحية.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        # Serialize the assignment decision: lock the customer AND the meter
        # rows before inserting, so two concurrent transactions cannot both
        # pass the open-assignment uniqueness checks in _validate_assignment.
        customers = self.env['utility.customer'].browse(
            [vals['customer_id'] for vals in vals_list if vals.get('customer_id')])
        meters = self.env['utility.meter'].browse(
            [vals['meter_id'] for vals in vals_list if vals.get('meter_id')])
        customers._lock_lifecycle()
        meters._lock_meter()
        records = super().create(vals_list)
        for record in records:
            record._validate_assignment()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'customer_id', 'meter_id', 'state', 'date_from', 'date_to'} & set(vals):
            for record in self:
                record._validate_assignment()
        return result

    def _validate_assignment(self):
        self.ensure_one()
        if self.company_id != self.customer_id.company_id:
            raise ValidationError(_('شركة تخصيص العداد يجب أن تطابق شركة الحساب.'))
        if self.meter_id.company_id != self.company_id:
            raise ValidationError(_('عداد التخصيص يجب أن ينتمي إلى نفس الشركة.'))
        # Re-lock the involved rows (no-op when already locked by create/write)
        # so the uniqueness checks below read a consistent, serialized state.
        if self.customer_id:
            self.customer_id._lock_lifecycle()
        if self.meter_id:
            self.meter_id._lock_meter()
        open_domain = [
            ('id', '!=', self.id), ('state', '=', 'open'),
            ('date_to', '=', False),
        ]
        if self.customer_id:
            if self.search(open_domain + [('customer_id', '=', self.customer_id.id)], limit=1):
                raise ValidationError(_('لا يمكن أن يكون للحساب أكثر من عداد حالي واحد.'))
        if self.meter_id and self.search(
                open_domain + [('meter_id', '=', self.meter_id.id)], limit=1):
            raise ValidationError(_('العداد مستخدم حاليًا في حساب كهربائي آخر.'))

    def action_close(self, final_reading=False, reason=False, notes=False):
        for record in self:
            if record.state != 'open':
                continue
            vals = {
                'state': 'closed',
                'date_to': fields.Datetime.now(),
                'removed_by_id': self.env.user.id,
            }
            if final_reading is not False:
                vals['final_reading'] = final_reading
            if reason:
                vals['reason'] = reason
            if notes:
                vals['notes'] = notes
            record.write(vals)
        return True


class UtilityCustomerLifecycleEvent(models.Model):
    _name = 'utility.customer.lifecycle.event'
    _description = 'حدث دورة حياة الحساب الكهربائي'
    _order = 'event_date desc, id desc'

    customer_id = fields.Many2one('utility.customer', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='customer_id.company_id', store=True, index=True)
    event_date = fields.Datetime('التاريخ', required=True, default=fields.Datetime.now)
    event_type = fields.Selection([
        ('created', 'إنشاء'), ('activated', 'تفعيل'), ('suspended', 'تعليق'),
        ('reactivated', 'إعادة تفعيل'), ('disconnected', 'فصل الخدمة'),
        ('reconnected', 'إعادة التوصيل'), ('meter_installed', 'تركيب عداد'),
        ('meter_replaced', 'استبدال عداد'), ('meter_removed', 'إزالة عداد'),
        ('configuration_changed', 'تغيير إعدادات'), ('closed', 'إغلاق الحساب'),
    ], required=True)
    old_state = fields.Selection(CUSTOMER_STATE_SELECTION, string='الحالة القديمة', readonly=True)
    new_state = fields.Selection(CUSTOMER_STATE_SELECTION, string='الحالة الجديدة', readonly=True)
    reason = fields.Char('السبب')
    notes = fields.Text('ملاحظات')
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    reference = fields.Char('المرجع')
    old_meter_id = fields.Many2one('utility.meter', string='العداد السابق')
    new_meter_id = fields.Many2one('utility.meter', string='العداد الجديد')

class UtilityCustomerLifecycle(models.Model):
    _inherit = 'utility.customer'

    meter_assignment_ids = fields.One2many(
        'utility.customer.meter.assignment', 'customer_id', string='سجل العدادات', readonly=True)
    current_meter_assignment_id = fields.Many2one(
        'utility.customer.meter.assignment', compute='_compute_current_meter_assignment',
        string='تخصيص العداد الحالي')
    lifecycle_event_ids = fields.One2many(
        'utility.customer.lifecycle.event', 'customer_id', string='سجل دورة الحياة', readonly=True)
    meter_assignment_count = fields.Integer('تخصيصات العدادات', compute='_compute_lifecycle_counts')
    lifecycle_event_count = fields.Integer('أحداث دورة الحياة', compute='_compute_lifecycle_counts')
    service_start_date = fields.Datetime('تاريخ بدء الخدمة', readonly=True)
    latest_lifecycle_event = fields.Char('آخر حدث', compute='_compute_lifecycle_counts')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft' and not self.env.context.get('lifecycle_operation'):
                raise ValidationError(_('يجب إنشاء الحساب في حالة مسودة ثم تفعيله بإجراء معتمد.'))
        return super().create(vals_list)

    @api.depends('meter_assignment_ids.state', 'meter_assignment_ids.date_from', 'meter_assignment_ids.date_to')
    def _compute_current_meter_assignment(self):
        for customer in self:
            customer.current_meter_assignment_id = customer.meter_assignment_ids.filtered(
                lambda assignment: assignment.state == 'open' and not assignment.date_to
            ).sorted('date_from', reverse=True)[:1]

    @api.depends('lifecycle_event_ids', 'lifecycle_event_ids.event_date', 'meter_assignment_ids')
    def _compute_lifecycle_counts(self):
        for customer in self:
            events = customer.lifecycle_event_ids.sorted('event_date', reverse=True)
            customer.lifecycle_event_count = len(events)
            customer.meter_assignment_count = len(customer.meter_assignment_ids)
            customer.latest_lifecycle_event = events[:1].event_type if events else False

    def _lock_lifecycle(self):
        self.env.flush_all()
        if self.ids:
            self.env.cr.execute(
                'SELECT id FROM utility_customer WHERE id IN %s ORDER BY id FOR UPDATE',
                [tuple(self.ids)])
        self.invalidate_recordset()

    def _log_lifecycle_event(self, event_type, old_state=False, reason=False,
                             notes=False, service_order=False, old_meter=False,
                             new_meter=False):
        self.ensure_one()
        event = self.env['utility.customer.lifecycle.event'].create({
            'customer_id': self.id,
            'event_type': event_type,
            'old_state': old_state,
            'new_state': self.state,
            'reason': reason,
            'notes': notes,
            'reference': self.customer_number,
            **({'service_order_id': service_order.id} if service_order
               and 'service_order_id' in self.env['utility.customer.lifecycle.event']._fields else {}),
            'old_meter_id': old_meter.id if old_meter else False,
            'new_meter_id': new_meter.id if new_meter else False,
        })
        self.message_post(body=_('تم تسجيل حدث دورة الحياة: %s') % event_type)
        return event

    def _ensure_current_meter_assignment(self, assignment_type='initial_installation'):
        self.ensure_one()
        if not self.meter_id:
            raise ValidationError(_('يجب تخصيص عداد قبل تفعيل الحساب.'))
        assignment = self.current_meter_assignment_id
        if assignment and assignment.meter_id == self.meter_id:
            return assignment
        if assignment:
            assignment.action_close(reason=_('تحديث تخصيص العداد الحالي'))
        return self.env['utility.customer.meter.assignment'].create({
            'customer_id': self.id,
            'meter_id': self.meter_id.id,
            'company_id': self.company_id.id,
            'initial_reading': self.last_reading_value or 0.0,
            'assignment_type': assignment_type,
        })

    def _validate_activation(self):
        self.ensure_one()
        for field_name, label in (
                ('partner_id', 'العميل'), ('category_id', 'فئة المشترك'),
                ('subscriber_id', 'نوع المشترك'), ('company_id', 'الشركة'),
                ('region_id', 'المنطقة'), ('meter_id', 'العداد')):
            if not getattr(self, field_name):
                raise ValidationError(_('لا يمكن تفعيل الحساب قبل تحديد %s.') % label)
        if not self.meter_id.active:
            raise ValidationError(_('لا يمكن تفعيل الحساب بعداد غير نشط.'))
        if self.meter_id.customer_id and self.meter_id.customer_id != self:
            raise ValidationError(_('العداد مرتبط مسبقًا بحساب كهربائي آخر.'))
        other = self.env['utility.customer'].search([
            ('id', '!=', self.id), ('meter_id', '=', self.meter_id.id),
            ('state', 'in', ('active', 'suspended', 'disconnected')),
        ], limit=1)
        if other:
            raise ValidationError(_('العداد مستخدم حاليًا في الحساب %s.') % other.customer_number)
        self._ensure_current_meter_assignment()

    def _transition(self, expected, target, event_type, reason=False, effective_date=False,
                    notes=False, service_order=False):
        for customer in self:
            customer._lock_lifecycle()
            if customer.state not in expected:
                raise ValidationError(_('لا يمكن تنفيذ الإجراء من حالة الحساب الحالية.'))
            old_state = customer.state
            customer.with_context(lifecycle_operation=True).write({'state': target})
            if target == 'active' and not customer.service_start_date:
                customer.service_start_date = effective_date or fields.Datetime.now()
            customer._log_lifecycle_event(
                event_type, old_state, reason, notes, service_order)
        return True

    def action_activate(self):
        for customer in self:
            customer._validate_activation()
        return self._transition(('draft',), 'active', 'activated')

    def action_suspend(self, reason=False, effective_date=False, notes=False):
        if not reason:
            raise ValidationError(_('سبب تعليق الحساب مطلوب.'))
        return self._transition(('active',), 'suspended', 'suspended', reason, effective_date, notes)

    def action_reactivate(self, reason=False, notes=False):
        return self._transition(('suspended',), 'active', 'reactivated', reason, False, notes)

    def action_disconnect(self, reason=False, effective_date=False, notes=False, service_order=False):
        if not reason:
            raise ValidationError(_('سبب فصل الخدمة مطلوب.'))
        if not (self.env.context.get('lifecycle_override')
                or self.env.context.get('lifecycle_service_order')):
            if not service_order or service_order.state != 'completed':
                raise ValidationError(_('لا يمكن فصل الخدمة قبل إكمال أمر الخدمة الميداني.'))
        return self._transition(('active',), 'disconnected', 'disconnected', reason, effective_date, notes, service_order)

    def action_reconnect(self, reason=False, notes=False, service_order=False):
        if not (self.env.context.get('lifecycle_override')
                or self.env.context.get('lifecycle_service_order')):
            if not service_order or service_order.state != 'completed':
                raise ValidationError(_('لا يمكن إعادة التوصيل قبل إكمال أمر الخدمة الميداني.'))
        return self._transition(('disconnected',), 'active', 'reconnected', reason, False, notes, service_order)

    def action_close(self, reason=False, effective_date=False, notes=False,
                     final_reading=False, require_field_removal=False,
                     service_order=False):
        """إغلاق الحساب بسياسة اكتمال تشغيلية كاملة.

        Policy:
          Close Account
            ├─ Final reading available (explicit or recorded on the meter)?
            ├─ Current meter assignment closed/released?
            ├─ Meter released/removed from the account?
            └─ (Optional) completed field-removal service order when required?
          → Closed

        لا يقوم Core بإنشاء الفاتورة النهائية بنفسه — هذا مسؤولية وحدة الفوترة —
        لكنه يمنع إغلاق حساب لا تزال لديه تخصيص عداد مفتوح أو عداد مرتبط.
        """
        if not reason:
            raise ValidationError(_('سبب إغلاق الحساب مطلوب.'))
        for customer in self:
            customer._lock_lifecycle()
            if customer.state not in ('active', 'suspended', 'disconnected'):
                raise ValidationError(_('لا يمكن إغلاق الحساب من حالته الحالية.'))
            effective = effective_date or fields.Datetime.now()
            old_state = customer.state
            meter = customer.meter_id
            assignment = customer.current_meter_assignment_id

            final_value = final_reading
            if meter:
                if final_value is False:
                    if meter.last_read_date:
                        final_value = meter.last_reading_value
                    else:
                        raise ValidationError(_(
                            'لا يمكن إغلاق الحساب [%s] قبل تسجيل القراءة الختامية للعداد.'
                        ) % customer.customer_number)
                if require_field_removal and not (
                        self.env.context.get('lifecycle_override')
                        or self.env.context.get('lifecycle_service_order')):
                    if not service_order or service_order.state != 'completed':
                        raise ValidationError(_(
                            'لا يمكن إغلاق الحساب مع طلب إزالة العداد ميدانياً '
                            'قبل إكمال أمر الخدمة الميداني.'))

            if assignment and assignment.state == 'open':
                assignment.action_close(
                    final_reading=final_value if final_value is not False else False,
                    reason=_('إغلاق الحساب: %s') % reason,
                    notes=notes)
            if meter:
                meter.write({'customer_id': False, 'connection_type': 'not_connected'})
                customer.with_context(lifecycle_operation=True).write({'meter_id': False})
                customer._log_lifecycle_event(
                    'meter_removed', old_state=old_state, reason=reason,
                    notes=notes, service_order=service_order, old_meter=meter)
            customer.with_context(lifecycle_operation=True).write({
                'state': 'closed',
                'date_end': effective.date(),
                'contract_end_date': effective.date(),
            })
            customer._log_lifecycle_event(
                'closed', old_state=old_state, reason=reason,
                notes=notes, service_order=service_order)
        return True

    def write(self, vals):
        protected = {'state', 'meter_id'}
        if protected.intersection(vals) and not self.env.context.get('lifecycle_operation'):
            for customer in self:
                if 'state' in vals and vals['state'] != customer.state:
                    raise ValidationError(_('استخدم إجراء دورة الحياة لتغيير حالة الحساب.'))
                if 'meter_id' in vals and vals['meter_id'] != customer.meter_id.id:
                    raise ValidationError(_('استخدم إجراء تخصيص أو استبدال العداد.'))
        return super().write(vals)

    def action_view_meter_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('سجل العدادات'),
            'res_model': 'utility.customer.meter.assignment', 'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
        }

    def action_view_lifecycle_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('سجل دورة الحياة'),
            'res_model': 'utility.customer.lifecycle.event', 'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
        }

    def action_open_meter_replacement(self):
        self.ensure_one()
        action = self.env.ref('utility_core.action_utility_meter_replacement').read()[0]
        action['context'] = dict(
            self.env.context,
            default_target_type='subscriber',
            default_utility_account_id=self.id,
            default_old_closing_reading=self.last_reading_value or 0.0,
        )
        return action

    def action_open_lifecycle_wizard(self):
        self.ensure_one()
        action = self.env.ref(
            'utility_core.action_utility_customer_lifecycle_wizard').read()[0]
        action['context'] = dict(
            self.env.context,
            active_model='utility.customer',
            active_id=self.id,
            active_ids=[self.id],
            lifecycle_action=self.env.context.get('lifecycle_action'),
        )
        return action
