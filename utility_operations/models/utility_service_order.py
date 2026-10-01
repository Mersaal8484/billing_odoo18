from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityServiceOrder(models.Model):
    _name = 'utility.service.order'
    _description = 'أمر خدمة'
    _rec_name = 'order_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_requested desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    def _default_warehouse_id(self):
        warehouses = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)])
        return warehouses[:1] if len(warehouses) == 1 else False

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='المستودع المنفذ',
        default=_default_warehouse_id,
        help='المستودع المعين لتنفيذ حركات الصرف والإرجاع والاستبدال الفيزيائية'
    )
    order_number = fields.Char('رقم الأمر', required=True, index=True, default=lambda self: _('جديد'))
    date_requested = fields.Datetime('تاريخ الطلب', default=fields.Datetime.now)
    date_scheduled = fields.Datetime('التاريخ المجدول')
    date_completed = fields.Datetime('تاريخ الإكمال')
    service_type = fields.Selection([
        ('new_connection', 'توصيلة جديدة'),
        ('meter_replacement', 'استبدال عداد'),
        ('meter_removal', 'إزالة عداد'),
        ('meter_test', 'فحص عداد'),
        ('inspection', 'تفتيش'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة توصيل'),
        ('tamper_investigation', 'تحقيق تلاعب'),
        ('site_survey', 'مسح موقع'),
        ('maintenance', 'صيانة'),
        ('other', 'أخرى'),
    ], string='نوع الخدمة', required=True)
    priority = fields.Selection([
        ('low', 'منخفضة'),
        ('normal', 'عادية'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ], string='الأولوية', default='normal')
    customer_id = fields.Many2one('utility.customer', 'العميل', index=True)
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)
    region_id = fields.Many2one('utility.region', 'المنطقة', related='customer_id.region_id', store=True)
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', related='customer_id.area_id', store=True)
    zone_id = fields.Many2one('utility.region', 'المنطقة التفصيلية', domain="[('type', '=', 'zone')]")

    old_meter_id = fields.Many2one('utility.meter', 'العداد القديم')
    new_meter_id = fields.Many2one('utility.meter', 'العداد الجديد')
    description = fields.Text('الوصف', required=True)
    technician_id = fields.Many2one('res.users', 'الفني')
    team_id = fields.Many2one('utility.team', 'الفريق')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('scheduled', 'مجدول'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', tracking=True)
    findings = fields.Text('الملاحظات')
    meter_reading_before = fields.Float('قراءة العداد قبل')
    meter_reading_after = fields.Float('قراءة العداد بعد')
    seal_number_old = fields.Char('رقم الختم القديم')
    seal_number_new = fields.Char('رقم الختم الجديد')
    tamper_evidence = fields.Boolean('أدلة تلاعب')
    tamper_notes = fields.Text('ملاحظات التلاعب')
    cost_estimate = fields.Monetary('التكلفة التقديرية', currency_field='company_currency_id')
    actual_cost = fields.Monetary('التكلفة الفعلية', currency_field='company_currency_id')
    notes = fields.Text('ملاحظات')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')
    picking_ids = fields.One2many('stock.picking', compute='_compute_picking_ids', string='حركات المخزون')
    picking_count = fields.Integer(compute='_compute_picking_ids', string='عدد حركات المخزون')

    def _compute_picking_ids(self):
        for rec in self:
            pickings = self.env['stock.picking'].search([
                '|',
                ('origin', '=', rec.order_number),
                ('utility_operation_ref', 'ilike', f"SO:{rec.order_number}"),
            ])
            rec.picking_ids = pickings
            rec.picking_count = len(pickings)

    _sql_constraints = [
        ('unique_order_number_company', 'unique(order_number, company_id)',
         'رقم الأمر يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.constrains('customer_id', 'meter_id', 'old_meter_id', 'new_meter_id', 'zone_id', 'service_type')
    def _check_subject_and_meter_consistency(self):
        for order in self:
            customer = order.customer_id
            if customer and order.zone_id and customer.zone_id and order.zone_id != customer.zone_id:
                raise ValidationError(_('موقع أمر الخدمة يجب أن يطابق المنطقة التفصيلية للمشترك.'))
            if customer:
                for meter in (order.meter_id, order.old_meter_id):
                    if meter and meter.customer_id and meter.customer_id != customer:
                        raise ValidationError(_('العداد المحدد لا يتبع المشترك في أمر الخدمة.'))
            if order.service_type == 'meter_replacement' and order.new_meter_id:
                if order.new_meter_id.connection_type != 'not_connected':
                    raise ValidationError(_('عداد الاستبدال الجديد يجب أن يكون غير مرتبط قبل التنفيذ.'))

    def _check_state_transition(self, allowed_states):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state not in allowed_states:
                raise ValidationError(_("لا يمكن تعديل حالة أمر الخدمة من الحالة الحالية '%s'.") % order.state +
                                      _(" الحالات المسموحة: %s") % ", ".join(allowed_states))

    def action_approve(self):
        self._check_state_transition(['draft'])
        self.state = 'approved'

    def action_schedule(self):
        self._check_state_transition(['approved'])
        self.state = 'scheduled'
        self.date_scheduled = fields.Datetime.now()

    def action_start(self):
        self._check_state_transition(['scheduled'])
        self.state = 'in_progress'

    def _validate_completion_requirements(self):
        """فحص الشروط المسبقة الصريحة لاستكمال أمر الخدمة حسب نوع العملية."""
        self.ensure_one()
        if not self.warehouse_id:
            raise ValidationError(_('يجب تحديد المستودع المسؤول (warehouse_id) لإكمال أمر الخدمة الميدانية.'))

        if self.service_type == 'new_connection':
            if not self.customer_id:
                raise ValidationError(_('أمر التوصيل الجديد يتطلب تحديد حساب المشترك (customer_id).'))
            target_meter = self.meter_id or self.new_meter_id
            if not target_meter:
                raise ValidationError(_('أمر التوصيل الجديد يتطلب تحديد العداد الجديد المراد تركيبه (meter_id أو new_meter_id).'))

        elif self.service_type == 'meter_replacement':
            old_meter = self.old_meter_id or self.meter_id
            new_meter = self.new_meter_id
            if not old_meter or not new_meter:
                raise ValidationError(_('أمر استبدال العداد يتطلب تحديد العداد القديم والعداد الجديد صراحة.'))
            if old_meter == new_meter:
                raise ValidationError(_('لا يمكن استبدال العداد بنفس العداد.'))

        elif self.service_type == 'meter_removal':
            target_meter = self.meter_id or self.old_meter_id
            if not target_meter:
                raise ValidationError(_('أمر الفصل/الرفع يتطلب تحديد العداد المراد رفعه (meter_id أو old_meter_id).'))

        elif self.service_type in ('disconnection', 'reconnection'):
            target_meter = self.meter_id or self.old_meter_id or self.new_meter_id
            target_customer = self.customer_id or (target_meter and target_meter.customer_id)
            if not target_customer:
                raise ValidationError(_('أمر الفصل/إعادة التوصيل يتطلب تحديد المشترك صراحة أو اختيار عداد مرتبط بمشترك فعلي.'))

    def action_complete(self):
        self._check_state_transition(['in_progress'])
        self._validate_completion_requirements()
        ctx = dict(self.env.context, skip_implicit_log=True, allow_log_update=True)

        if self.service_type == 'meter_replacement':
            old_meter = self.old_meter_id or self.meter_id
            new_meter = self.new_meter_id
            op_ref = f"SO:{self.order_number}"
            old_meter.inventory_replace_meter(
                new_meter=new_meter,
                old_warehouse=self.warehouse_id,
                new_warehouse=self.warehouse_id,
                origin=self.order_number,
                operation_ref=op_ref,
                old_destination='inspection',
            )
            old_meter.with_context(ctx).write({'customer_id': False})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                old_meter, 'removal',
                _('رفع العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

            new_meter.with_context(ctx).write({'customer_id': self.customer_id.id})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                new_meter, 'replacement',
                _('تركيب عداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'new_connection':
            target_meter = self.meter_id or self.new_meter_id
            op_ref = f"SO:{self.order_number}:INSTALL"
            target_meter.inventory_install_meter(
                customer=self.customer_id,
                warehouse=self.warehouse_id,
                origin=self.order_number,
                operation_ref=op_ref,
            )
            target_meter.with_context(ctx).write({'customer_id': self.customer_id.id})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                target_meter, 'install',
                _('تركيب عداد جديد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'meter_removal':
            target_meter = self.meter_id or self.old_meter_id
            op_ref = f"SO:{self.order_number}:REMOVE"
            target_meter.inventory_remove_meter(
                warehouse=self.warehouse_id,
                origin=self.order_number,
                operation_ref=op_ref,
                destination='inspection',
            )
            target_meter.with_context(ctx).write({'customer_id': False})
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                target_meter, 'removal',
                _('رفع العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        elif self.service_type == 'disconnection':
            target_meter = self.meter_id or self.old_meter_id
            target_customer = self.customer_id or (target_meter and target_meter.customer_id)
            if not target_customer:
                raise ValidationError(_('تعذر تنفيذ الفصل: لم يتم العثور على مشترك مرتبط بأمر الخدمة.'))
            target_customer.with_context(
                lifecycle_service_order=True).action_disconnect(
                    reason=self.description, service_order=self)
            if target_meter:
                self.env['utility.meter.log'].with_context(ctx)._create_log(
                    target_meter, 'disconnection',
                    _('فصل العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                    ref_record=self)
        elif self.service_type == 'reconnection':
            target_meter = self.meter_id or self.new_meter_id or self.old_meter_id
            target_customer = self.customer_id or (target_meter and target_meter.customer_id)
            if not target_customer:
                raise ValidationError(_('تعذر تنفيذ إعادة التوصيل: لم يتم العثور على مشترك مرتبط بأمر الخدمة.'))
            target_customer.with_context(
                lifecycle_service_order=True).action_reconnect(
                    reason=self.description, service_order=self)
            if target_meter:
                self.env['utility.meter.log'].with_context(ctx)._create_log(
                    target_meter, 'reconnection',
                    _('إعادة خدمة العداد عبر أمر خدمة %s: %s') % (self.order_number, self.description),
                    ref_record=self)

        target_meter = self.meter_id or self.new_meter_id or self.old_meter_id
        if target_meter and self.service_type not in ('meter_replacement', 'disconnection', 'reconnection', 'new_connection', 'meter_removal'):
            self.env['utility.meter.log'].with_context(ctx)._create_log(
                target_meter, 'service_order',
                _('أمر خدمة %s: %s') % (self.order_number, self.description),
                ref_record=self)

        self.state = 'completed'
        self.date_completed = fields.Datetime.now()

    def action_cancel(self):
        self._check_state_transition(['draft', 'approved', 'scheduled'])
        self.state = 'cancelled'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('order_number', _('جديد')) == _('جديد'):
                company_id = vals.get('company_id') or self.env.company.id
                while True:
                    seq = self.env['ir.sequence'].next_by_code('utility.service.order') or _('جديد')
                    if seq == _('جديد') or not self.sudo().search_count([('order_number', '=', seq), ('company_id', '=', company_id)]):
                        vals['order_number'] = seq
                        break
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('لا يمكن حذف أمر الخدمة إلا في حالة المسودة.'))
        return super().unlink()

    @api.model
    def cron_detect_zero_consumption_meters(self, batch_limit=500):
        """الكشف التلقائي عن العدادات الخاملة أو المعطلة ذات الاستهلاك الصفري المتكرر."""
        Reading = self.env['utility.reading'].sudo()
        Meter = self.env['utility.meter'].sudo()

        active_meters = Meter.search([
            ('active', '=', True),
            ('customer_id', '!=', False),
            ('customer_id.state', '=', 'active'),
        ], limit=batch_limit)

        created_orders = self.env['utility.service.order']
        for meter in active_meters:
            open_inspection = self.search([
                ('meter_id', '=', meter.id),
                ('service_type', 'in', ('inspection', 'meter_test')),
                ('state', 'in', ('draft', 'approved', 'scheduled', 'in_progress')),
            ], limit=1)
            if open_inspection:
                continue

            readings = Reading.search([
                ('meter_id', '=', meter.id),
                ('state', 'in', ('approved', 'billed')),
            ], order='reading_date desc, id desc', limit=3)

            if len(readings) >= 3 and all(r.consumption == 0.0 for r in readings):
                order = self.create({
                    'service_type': 'inspection',
                    'priority': 'normal',
                    'customer_id': meter.customer_id.id,
                    'meter_id': meter.id,
                    'description': _('تفتيش آلي: العداد يسجل استهلاكاً صفرياً مستمراً لآخر %d قراءات متتالية. يرجى الفحص الميداني للتأكد من سلامة العداد.') % len(readings),
                    'state': 'draft',
                })
                created_orders |= order
        return len(created_orders)
