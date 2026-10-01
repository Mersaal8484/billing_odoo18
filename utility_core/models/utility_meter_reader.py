from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterReader(models.Model):
    _name = 'utility.meter.reader'
    _description = 'كاشف قراءة العدادات'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    active = fields.Boolean('نشط', default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 'الشركة',
        default=lambda self: self.env.company,
    )
    name = fields.Char('اسم الكاشف', required=True, tracking=True)
    code = fields.Char('رمز الكاشف', tracking=True)
    user_id = fields.Many2one(
        'res.users', 'حساب الدخول',
        required=True, tracking=True,
        help='حساب المستخدم الذي يستخدمه الكاشف لتسجيل الدخول في التطبيق',
    )
    mobile = fields.Char('رقم الجوال', tracking=True)
    staff_id = fields.Many2one(
        'utility.staff', 'سجل الموظف',
        tracking=True,
        help='ربط اختياري بسجل موظف موجود في النظام',
    )
    image_1920 = fields.Image('الصورة', max_width=1920, max_height=1920)
    notes = fields.Text('ملاحظات')
    route_ids = fields.Many2many(
        'utility.route',
        'meter_reader_route_rel',
        'reader_id', 'route_id',
        string='المسارات المخصصة',
        tracking=True,
    )
    route_count = fields.Integer(
        'عدد المسارات',
        compute='_compute_route_count',
        store=False,
    )
    customer_ids = fields.Many2many(
        'utility.customer',
        string='المشتركون التابعون',
        compute='_compute_customers',
        help='قائمة المشتركين التابعين للمسارات المخصصة لهذا الكاشف',
    )
    customer_count = fields.Integer(
        'عدد المشتركين',
        compute='_compute_customers',
        store=False,
    )

    _sql_constraints = [
        ('unique_user_id', 'unique(user_id)',
         'هذا المستخدم مرتبط بكاشف آخر. كل مستخدم يجب أن يرتبط بكاشف واحد فقط.'),
    ]

    @api.depends('route_ids')
    def _compute_route_count(self):
        for reader in self:
            reader.route_count = len(reader.route_ids)

    @api.depends('route_ids')
    def _compute_customers(self):
        for reader in self:
            if reader.route_ids:
                customers = self.env['utility.customer'].search([
                    ('route_id', 'in', reader.route_ids.ids),
                ])
                reader.customer_ids = customers
                reader.customer_count = len(customers)
            else:
                reader.customer_ids = False
                reader.customer_count = 0

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id:
            if not self.name or self.name == _('جديد'):
                self.name = self.user_id.name
            if not self.mobile and self.user_id.phone:
                self.mobile = self.user_id.phone
            elif not self.mobile and self.user_id.mobile:
                self.mobile = self.user_id.mobile
            if self.user_id.image_1920 and not self.image_1920:
                self.image_1920 = self.user_id.image_1920

    @api.onchange('staff_id')
    def _onchange_staff_id(self):
        if self.staff_id:
            if not self.name or self.name == _('جديد'):
                self.name = self.staff_id.name
            if not self.code and self.staff_id.employee_code:
                self.code = self.staff_id.employee_code
            if not self.mobile and self.staff_id.mobile:
                self.mobile = self.staff_id.mobile
            if not self.user_id and self.staff_id.user_id:
                self.user_id = self.staff_id.user_id

    def _sync_user_routes(self):
        """تحديث assigned_route_ids في res.users ليطابق مسارات الكاشف."""
        for reader in self.filtered('user_id'):
            reader.user_id.sudo().write({
                'assigned_route_ids': [(6, 0, reader.route_ids.ids)],
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # تأكد من إضافة مجموعة قارئ العدادات للمستخدم
        meter_reader_group = self.env.ref(
            'utility_core.group_utility_meter_reader', raise_if_not_found=False)
        for reader in records:
            if reader.user_id and meter_reader_group:
                reader.user_id.sudo().write({
                    'groups_id': [(4, meter_reader_group.id)],
                })
        records._sync_user_routes()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'route_ids' in vals:
            self._sync_user_routes()
        if 'user_id' in vals:
            meter_reader_group = self.env.ref(
                'utility_core.group_utility_meter_reader', raise_if_not_found=False)
            for reader in self.filtered('user_id'):
                if meter_reader_group:
                    reader.user_id.sudo().write({
                        'groups_id': [(4, meter_reader_group.id)],
                    })
            self._sync_user_routes()
        return res

    def action_view_customers(self):
        self.ensure_one()
        return {
            'name': _('مشتركو الكاشف: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'view_mode': 'list,form',
            'domain': [('route_id', 'in', self.route_ids.ids)],
            'context': {'default_route_id': self.route_ids[:1].id if self.route_ids else False},
        }

    def action_view_routes(self):
        self.ensure_one()
        return {
            'name': _('مسارات الكاشف: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.route',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.route_ids.ids)],
        }

    def action_sync_routes(self):
        """مزامنة المسارات فورياً مع حساب المستخدم وتطبيق الموبايل"""
        self.ensure_one()
        self._sync_user_routes()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تمت المزامنة بنجاح'),
                'message': _('تم تحديث مسارات الكاشف ومزامنتها بنجاح مع حساب المستخدم وتطبيق الموبايل.'),
                'type': 'success',
                'sticky': False,
            }
        }

