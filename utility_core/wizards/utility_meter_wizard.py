from odoo import api, fields, models, _
from odoo.exceptions import AccessError


def _require_groups(env, *group_xmlids):
    if not any(env.user.has_group(group_xmlid) for group_xmlid in group_xmlids):
        raise AccessError(_('ليس لديك صلاحية تنفيذ هذه العملية التشغيلية.'))


class UtilityMeterSubscriberWizard(models.TransientModel):
    _name = 'utility.meter.subscriber.wizard'
    _description = 'إضافة مشترك جديد من العداد'

    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, readonly=True)
    partner_name = fields.Char('اسم المشترك', required=True)
    mobile = fields.Char('رقم الجوال')
    national_id = fields.Char('الرقم الوطني / الهوية')
    street = fields.Char('العنوان')
    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك', required=True)
    subscriber_id = fields.Many2one(
        'utility.subscriber', string='نوع المشترك', required=True,
        domain="[('category_id', '=', category_id)]")
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد')
    customer_number = fields.Char('رقم المشترك', default=lambda self: _('جديد'))

    def action_create(self):
        self.ensure_one()
        _require_groups(
            self.env,
            'utility_core.group_utility_supervisor',
            'utility_core.group_utility_admin',
        )
        meter = self.meter_id
        # Scope guard: verify the meter is within the acting user's organizational scope.
        # Prevents restricted users from creating customers via meters outside their region.
        self.env.user.check_record_scope(meter)
        # Inherit geography from the meter's canonical location into the new partner.
        # This ensures the resulting utility.customer has a resolvable region/area,
        # satisfying the fail-closed scope check in utility.customer.create().
        # For not_connected meters (visible only to global/admin users), meter.region_id
        # and meter.area_id are False — the admin bypass in create() handles that case.
        partner = self.env['res.partner'].create({
            'name': self.partner_name,
            'mobile': self.mobile,
            'street': self.street or False,
            'region_id': meter.region_id.id if meter.region_id else False,
            'area_id': meter.area_id.id if meter.area_id else False,
        })
        vals = {
            'partner_id': partner.id,
            'customer_number': self.customer_number,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_id.id,
            'contract_template_id': self.contract_template_id.id or False,
            'meter_id': meter.id,
            'state': 'active',
        }
        customer = self.env['utility.customer'].create(vals)
        meter.write({
            'connection_type': 'subscriber',
            'customer_id': customer.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'res_id': customer.id,
            'view_mode': 'form',
            'target': 'current',
        }


class UtilityMeterPrivateTransformerWizard(models.TransientModel):
    _name = 'utility.meter.private.transformer.wizard'
    _description = 'إضافة مشترك ومحول خاص جديد'

    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, readonly=True)

    partner_name = fields.Char('اسم المشترك', required=True)
    mobile = fields.Char('رقم الجوال')
    national_id = fields.Char('الرقم الوطني / الهوية')
    street = fields.Char('العنوان')
    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك', required=True)
    subscriber_id = fields.Many2one(
        'utility.subscriber', string='نوع المشترك', required=True,
        domain="[('category_id', '=', category_id)]")
    contract_template_id = fields.Many2one('utility.contract.template', string='قالب العقد')
    customer_number = fields.Char('رقم المشترك', default=lambda self: _('جديد'))

    name = fields.Char('اسم المحول الخاص', required=True)
    code = fields.Char('رمز المحول الخاص', required=True)
    capacity = fields.Float('القدرة (kVA)')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    serial_number = fields.Char('الرقم التسلسلي')
    substation_id = fields.Many2one('utility.substation', 'المحطة')
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية')

    def action_create(self):
        self.ensure_one()
        _require_groups(self.env, 'utility_core.group_utility_admin')
        meter = self.meter_id
        # Scope guard: verify the meter is within the acting user's organizational scope.
        self.env.user.check_record_scope(meter)
        partner = self.env['res.partner'].create({
            'name': self.partner_name,
            'mobile': self.mobile,
            'street': self.street or False,
        })
        transformer = self.env['utility.transformer'].create({
            'name': self.name,
            'code': self.code,
            'substation_id': self.substation_id.id or False,
            'feeder_id': self.feeder_id.id or False,
            'capacity': self.capacity or 0.0,
            'phase': self.phase or False,
            'serial_number': self.serial_number or False,
            'is_private': True,
        })
        customer = self.env['utility.customer'].create({
            'partner_id': partner.id,
            'customer_number': self.customer_number,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_id.id,
            'contract_template_id': self.contract_template_id.id or False,
            'meter_id': meter.id,
            'transformer_id': transformer.id,
            'state': 'active',
        })
        meter.write({
            'connection_type': 'subscriber',
            'customer_id': customer.id,
            'linked_private_transformer_id': transformer.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'res_id': customer.id,
            'view_mode': 'form',
            'target': 'current',
        }


class UtilityMeterTransformerWizard(models.TransientModel):
    _name = 'utility.meter.transformer.wizard'
    _description = 'إضافة محول جديد من العداد'

    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, readonly=True)
    name = fields.Char('اسم المحول', required=True)
    code = fields.Char('رمز المحول', required=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة')
    capacity = fields.Float('القدرة (kVA)')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    serial_number = fields.Char('الرقم التسلسلي')
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية')
    region_id = fields.Many2one('utility.region', 'المنطقة', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', 'الفرع',
                              domain="[('type', '=', 'area'), ('parent_id', '=', region_id)]")

    def action_create(self):
        self.ensure_one()
        _require_groups(self.env, 'utility_core.group_utility_admin')
        meter = self.meter_id
        transformer = self.env['utility.transformer'].create({
            'name': self.name,
            'code': self.code,
            'substation_id': self.substation_id.id or False,
            'feeder_id': self.feeder_id.id or False,
            'capacity': self.capacity or 0.0,
            'phase': self.phase or False,
            'serial_number': self.serial_number or False,
            'is_private': False,
            'region_id': self.region_id.id or False,
            'area_id': self.area_id.id or False,
        })
        meter.write({
            'connection_type': 'transformer',
            'linked_transformer_id': transformer.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.transformer',
            'res_id': transformer.id,
            'view_mode': 'form',
            'target': 'current',
        }


class UtilityMeterFeederWizard(models.TransientModel):
    _name = 'utility.meter.feeder.wizard'
    _description = 'إضافة فيدر / خلية جديد من العداد'

    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, readonly=True)
    name = fields.Char('اسم الفيدر / الخلية', required=True)
    code = fields.Char('الرمز', required=True)
    substation_id = fields.Many2one('utility.substation', 'المحطة')
    voltage_level = fields.Selection([
        ('lv', 'جهد منخفض (LV)'),
        ('mv', 'جهد متوسط (MV)'),
        ('hv', 'جهد عالي (HV)'),
    ], string='مستوى الجهد')
    rated_capacity = fields.Float('الطاقة الاسمية (kVA)')

    def action_create(self):
        self.ensure_one()
        _require_groups(self.env, 'utility_core.group_utility_admin')
        meter = self.meter_id
        feeder = self.env['utility.feeder'].create({
            'name': self.name,
            'code': self.code,
            'substation_id': self.substation_id.id or False,
            'voltage_level': self.voltage_level or False,
            'rated_capacity': self.rated_capacity or 0.0,
        })
        meter.write({
            'connection_type': 'feeder',
            'linked_feeder_id': feeder.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.feeder',
            'res_id': feeder.id,
            'view_mode': 'form',
            'target': 'current',
        }
