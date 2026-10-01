from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityWorkOrder(models.Model):
    _name = 'utility.work.order'
    _description = 'أمر عمل'
    _rec_name = 'work_order_number'
    _order = 'date_created desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    work_order_number = fields.Char('رقم أمر العمل', required=True, index=True, default=lambda self: _('جديد'))
    service_order_id = fields.Many2one('utility.service.order', 'أمر الخدمة')
    customer_id = fields.Many2one('utility.customer', 'العميل')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    work_type = fields.Selection([
        ('installation', 'تركيب'),
        ('maintenance', 'صيانة'),
        ('repair', 'إصلاح'),
        ('inspection', 'تفتيش'),
        ('disconnection', 'فصل'),
        ('reconnection', 'إعادة توصيل'),
        ('meter_reading', 'قراءة عداد'),
        ('site_visit', 'زيارة موقع'),
        ('other', 'أخرى'),
    ], string='نوع العمل', required=True)
    description = fields.Text('الوصف', required=True)
    assigned_technician_id = fields.Many2one('res.users', 'الفني المُعيّن')
    team_id = fields.Many2one('utility.team', 'الفريق')
    date_created = fields.Datetime('تاريخ الإنشاء', default=fields.Datetime.now)
    date_scheduled = fields.Datetime('التاريخ المجدول')
    date_started = fields.Datetime('تاريخ البدء')
    date_completed = fields.Datetime('تاريخ الإكمال')
    priority = fields.Selection([
        ('low', 'منخفضة'),
        ('normal', 'عادية'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ], string='الأولوية', default='normal')
    gps_check_in = fields.Char('إحداثيات الحضور')
    gps_check_out = fields.Char('إحداثيات الانصراف')
    customer_signature = fields.Binary('توقيع العميل')
    parts_used = fields.Text('القطع المستخدمة')
    labor_hours = fields.Float('ساعات العمل')
    cost_estimate = fields.Monetary('التكلفة التقديرية', currency_field='company_currency_id')
    actual_cost = fields.Monetary('التكلفة الفعلية', currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='العملة')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('assigned', 'مُعيّن'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('verified', 'مُتحقّق'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft')
    notes = fields.Text('ملاحظات')

    @api.constrains('date_started', 'date_completed')
    def _check_work_order_dates(self):
        for order in self:
            if order.date_started and order.date_completed and order.date_started > order.date_completed:
                raise ValidationError(_('تاريخ البدء لا يمكن أن يكون بعد تاريخ الإكمال.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('work_order_number', _('جديد')) == _('جديد'):
                company_id = vals.get('company_id') or self.env.company.id
                while True:
                    seq = self.env['ir.sequence'].next_by_code('utility.work.order') or _('جديد')
                    if seq == _('جديد') or not self.sudo().search_count([('work_order_number', '=', seq), ('company_id', '=', company_id)]):
                        vals['work_order_number'] = seq
                        break
        return super().create(vals_list)

    def action_assign(self):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state != 'draft':
                raise UserError(_('لا يمكن تعيين أمر العمل إلا من حالة المسودة.'))
            if not order.assigned_technician_id and not order.team_id:
                raise ValidationError(_('يجب تحديد الفني أو الفريق المُعيّن قبل التعيين.'))
            order.state = 'assigned'

    def action_start(self):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state != 'assigned':
                raise UserError(_('لا يمكن بدء أمر العمل إلا بعد التعيين (مُعيّن).'))
            if not order.date_started:
                order.date_started = fields.Datetime.now()
            order.state = 'in_progress'

    def action_complete(self):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state != 'in_progress':
                raise UserError(_('لا يمكن إكمال أمر العمل إلا عندما يكون قيد التنفيذ.'))
            if not order.date_completed:
                order.date_completed = fields.Datetime.now()
            if order.date_started and order.date_started > order.date_completed:
                raise ValidationError(_('تاريخ البدء لا يمكن أن يكون بعد تاريخ الإكمال.'))
            order.state = 'completed'

    def action_verify(self):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state != 'completed':
                raise UserError(_('لا يمكن التحقق من أمر العمل إلا بعد إكتماله (مكتمل).'))
            order.state = 'verified'

    def action_cancel(self):
        for order in self:
            self.env.user.check_record_scope(order)
            if order.state not in ('draft', 'assigned', 'in_progress', 'completed'):
                raise UserError(_('لا يمكن إلغاء أمر العمل في حالته الحالية.'))
            order.state = 'cancelled'

