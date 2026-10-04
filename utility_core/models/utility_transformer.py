from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'محول كهرباء'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المحول', required=True)
    code = fields.Char('رمز المحول', required=True)

    # ===== الموقع في الشبكة =====
    substation_id = fields.Many2one('utility.substation', 'المحطة')
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية', index=True)
    zone_region_id = fields.Many2one(
        'utility.region', 'المنطقة التفصيلية المرتبطة (Zone 1:1)',
        domain="[('type', '=', 'zone')]",
        ondelete='restrict',
        index=True,
        help='التمثيل الجغرافي الواحد-لواحد للمحول في تدرج المناطق.'
    )
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', related='zone_region_id.parent_id', store=True, readonly=False)
    region_id = fields.Many2one('utility.region', 'المنطقة', related='zone_region_id.parent_id.parent_id', store=True, readonly=False)

    is_private = fields.Boolean(string='محول خاص', default=False, help='يُحدد ما إذا كان المحول خاصاً بمشترك واحد')

    # ===== المواصفات الفنية =====
    capacity = fields.Float('القدرة (kVA)')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    manufacturer = fields.Char('الشركة المصنّعة')
    serial_number = fields.Char('الرقم التسلسلي')
    voltage_primary = fields.Float('الجهد الابتدائي (فولت)')
    voltage_secondary = fields.Float('الجهد الثانوي (فولت)')
    address = fields.Text('العنوان')
    status = fields.Selection([
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('fault', 'عطل'),
        ('maintenance', 'صيانة'),
    ], string='الحالة', default='active')

    # ===== الربط بالمشتركين والعدادات =====
    meter_ids = fields.One2many('utility.meter', 'transformer_id', string='العدادات')
    coupling_meter_id = fields.Many2one(
        'utility.meter', 'عداد الربط (المقارنة والرصد)',
        domain="[('transformer_id', '=', id)]",
        help='العداد الذي يقيس إجمالي الطاقة الداخلة إلى المحول أو الفيدر',
    )
    customer_ids = fields.Many2many(
        'utility.customer',
        string='عقود المشتركين',
        compute='_compute_customer_ids',
        compute_sudo=True,
        help='عقود المشتركين المغذاة من هذا المحول عبر مسارات التوزيع المرتبطة به'
    )
    private_customer_id = fields.Many2one(
        'utility.customer', string='الحساب الخاص المالك', readonly=True,
        index=True, copy=False,
        help='المحول الخاص لا يجوز أن يرتبط بأكثر من حساب كهرباء واحد.')
    route_ids = fields.One2many(
        'utility.route', 'transformer_id',
        string='مسارات التوزيع',
        help='مسارات التوزيع المرتبطة بهذا المحول'
    )
    route_count = fields.Integer(
        'عدد المسارات',
        compute='_compute_route_count',
        store=True,
    )
    customer_count = fields.Integer(
        'عدد العقود',
        compute='_compute_customer_count',
        store=True,
        compute_sudo=True,
    )

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_transformer_code_company', 'unique(code, company_id)',
         'رمز المحول يجب أن يكون فريداً!'),
        ('unique_transformer_zone_region', 'unique(zone_region_id)',
         'لا يمكن ربط أكثر من محول واحد بنفس المنطقة التفصيلية (Zone).'),
    ]

    @api.constrains('zone_region_id', 'company_id')
    def _check_zone_region_link(self):
        for transformer in self.filtered('zone_region_id'):
            zone = transformer.zone_region_id
            if zone.type != 'zone':
                raise ValidationError(_('يجب أن يكون الرابط الجغرافي للمحول من نوع Zone فقط.'))
            if zone.company_id != transformer.company_id:
                raise ValidationError(_('شركة الـZone المرتبط يجب أن تطابق شركة المحول.'))
            if zone.transformer_origin_id and zone.transformer_origin_id != transformer:
                raise ValidationError(
                    _('الـZone "%s" مرتبط مسبقًا بالمحول "%s".')
                    % (zone.display_name, zone.transformer_origin_id.display_name)
                )

    @api.constrains('is_private', 'private_customer_id', 'route_ids')
    def _check_private_transformer_owner(self):
        for transformer in self:
            if transformer.is_private and len(transformer.customer_ids) > 1:
                raise ValidationError(
                    _('المحول الخاص %s لا يمكن ربطه بأكثر من حساب كهرباء واحد.')
                    % transformer.display_name
                )
            if (transformer.private_customer_id
                    and transformer.customer_ids
                    and transformer.private_customer_id not in transformer.customer_ids):
                raise ValidationError(
                    _('الحساب المحدد كمُالك للمحول الخاص غير مرتبط به فعليًا.')
                )

    @api.constrains('feeder_id', 'substation_id', 'company_id', 'coupling_meter_id')
    def _check_network_chain_consistency(self):
        for transformer in self:
            feeder = transformer.feeder_id
            station = transformer.substation_id
            if feeder:
                if feeder.company_id != transformer.company_id:
                    raise ValidationError(_('شركة المحول يجب أن تطابق شركة الفيدر.'))
                if station and feeder.substation_id and feeder.substation_id != station:
                    raise ValidationError(_('الفيدر المحدد لا يتبع المحطة المحددة للمحول.'))
            if station and station.company_id != transformer.company_id:
                raise ValidationError(_('شركة المحول يجب أن تطابق شركة المحطة.'))
            meter = transformer.coupling_meter_id
            if meter and (meter.connection_type != 'transformer' or meter.linked_transformer_id != transformer):
                raise ValidationError(_('عداد الربط يجب أن يكون عداد محول مرتبطًا بهذا المحول نفسه.'))

    def _check_general_transformer_geography(self):
        """فرض ربط المحول العام (غير الخاص) بمنطقة وفرع تابع لها؛ المحول الخاص مستثنى."""
        for transformer in self.filtered(lambda rec: not rec.is_private):
            region = transformer.region_id
            area = transformer.area_id
            if not region:
                raise ValidationError(
                    _('يجب ربط المحول "%s" بمنطقة (Region).') % transformer.display_name
                )
            if region.type != 'region':
                raise ValidationError(
                    _('الرابط الجغرافي للمحول "%s" يجب أن يكون منطقة (Region) صحيحة.')
                    % transformer.display_name
                )
            if not area:
                raise ValidationError(
                    _('يجب ربط المحول "%s" بفرع (Area) تابع للمنطقة.') % transformer.display_name
                )
            if area.type != 'area':
                raise ValidationError(
                    _('يجب ربط المحول "%s" بفرع (Area) تابع للمنطقة، وليس منطقة أو منطقة تفصيلية.')
                    % transformer.display_name
                )
            if area.parent_id != region:
                raise ValidationError(
                    _('الفرع "%s" المرتبط بالمحول "%s" لا يتبع المنطقة "%s".')
                    % (area.display_name, transformer.display_name, region.display_name)
                )

    # ===== Compute =====
    @api.depends('route_ids')
    def _compute_route_count(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)

    @api.depends('route_ids.customer_ids')
    def _compute_customer_ids(self):
        for rec in self:
            rec.customer_ids = rec.route_ids.mapped('customer_ids')

    @api.depends('route_ids.customer_ids')
    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = len(rec.route_ids.mapped('customer_ids'))

    # ===== Actions =====
    def _get_or_create_default_route(self):
        """إرجاع المسار الافتراضي للمحول مع إنشائه عند غيابه (مسار واحد لكل محول)."""
        self.ensure_one()
        route = self.env['utility.route'].search([
            ('company_id', '=', self.company_id.id),
            ('transformer_id', '=', self.id),
        ], limit=1)
        if route:
            return route
        return self.env['utility.route'].create({
            'name': _('مسار - %s') % self.name,
            'code': self.code,
            'company_id': self.company_id.id,
            'transformer_id': self.id,
        })

    def action_view_customers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود {self.name}',
            'res_model': 'utility.customer',
            'domain': [('route_id', 'in', self.route_ids.ids)],
            # Odoo 18 renamed the list view type from ``tree`` to ``list``.
            # Returning the legacy type makes the web client reject this
            # smart-button action before the target records can be displayed.
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'default_route_id': self.route_ids[:1].id if self.route_ids else False,
            },
        }

    def action_view_routes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'مسارات {self.name}',
            'res_model': 'utility.route',
            'domain': [('id', 'in', self.route_ids.ids)],
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'context': {'default_transformer_id': self.id},
        }

    def action_create_coupling_meter(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'إضافة عداد ربط',
            'res_model': 'utility.meter',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_transformer_id': self.id,
                'default_feeder_id': self.feeder_id.id if self.feeder_id else False,
                'default_is_coupling_meter': True,
                'default_payment_type': 'manual',
            },
        }

    def action_open_transformer_balance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'توازن - {self.name}',
            'res_model': 'utility.transformer.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transformer_id': self.id},
        }

    # ===== ORM Overrides =====
    @api.model_create_multi
    def create(self, vals_list):
        # Auto-generate the code from dedicated, fully separated sequences:
        # private transformers (محول خاص) use utility.transformer.private
        # (PRV/...), regular transformers use utility.transformer (TRF/...).
        for vals in vals_list:
            feeder_id = vals.get('feeder_id')
            if feeder_id and not vals.get('substation_id'):
                vals['substation_id'] = self.env['utility.feeder'].browse(feeder_id).substation_id.id
            if vals.get('code'):
                continue
            sequence_code = (
                'utility.transformer.private'
                if vals.get('is_private')
                else 'utility.transformer'
            )
            vals['code'] = (
                self.env['ir.sequence'].next_by_code(sequence_code) or _('جديد')
            )

        requested_zone_ids = [vals.get('zone_region_id') for vals in vals_list if vals.get('zone_region_id')]
        if len(requested_zone_ids) != len(set(requested_zone_ids)):
            raise ValidationError(_('لا يمكن ربط أكثر من محول واحد بنفس الـZone في نفس العملية.'))
        linked_zones = self.env['utility.region'].browse(requested_zone_ids)
        occupied_zones = linked_zones.filtered('transformer_origin_id')
        if occupied_zones:
            raise ValidationError(
                _('الـZone "%s" مرتبط مسبقًا بمحول آخر.') % occupied_zones[0].display_name
            )

        # Extract initial area_id or region_id passed in vals
        passed_parents = []
        for vals in vals_list:
            area_id = vals.get('area_id', False)
            region_id = vals.get('region_id', False)
            passed_parents.append(area_id or region_id)

        records = super().create(vals_list)

        for idx, rec in enumerate(records):
            if not rec.zone_region_id:
                parent_id = passed_parents[idx]
                parent_region = self.env['utility.region'].browse(parent_id) if parent_id else False
                recurring_type = parent_region.recurring_rule_type if parent_region and parent_region.recurring_rule_type else False
                if not recurring_type and parent_region:
                    root = parent_region
                    while root.parent_id:
                        root = root.parent_id
                    recurring_type = root.recurring_rule_type
                zone_vals = {
                    'name': rec.name,
                    'code': rec.code,
                    'type': 'zone',
                    'parent_id': parent_id if parent_id else False,
                    'company_id': rec.company_id.id,
                }
                if recurring_type:
                    zone_vals['recurring_rule_type'] = recurring_type
                zone = self.env['utility.region'].create(zone_vals)
                rec.zone_region_id = zone.id
            rec.zone_region_id.write({'transformer_origin_id': rec.id})
        records._check_general_transformer_geography()
        return records

    def write(self, vals):
        vals = dict(vals)
        if vals.get('feeder_id') and 'substation_id' not in vals:
            vals['substation_id'] = self.env['utility.feeder'].browse(
                vals['feeder_id']).substation_id.id
        # region_id/area_id are stored related fields with an automatic inverse
        # (zone_region_id.parent_id[.parent_id]); writing them directly cascades
        # parent_id updates onto utility.region inside super().write() and
        # re-enters the region hierarchy checks mid-write. Route them through
        # the explicit zone synchronisation below instead.
        new_area_id = vals.pop('area_id', None)
        new_region_id = vals.pop('region_id', None)
        geography_changed = new_area_id is not None or new_region_id is not None
        previous_zones = {record.id: record.zone_region_id for record in self}
        if 'zone_region_id' in vals and vals['zone_region_id']:
            target_zone = self.env['utility.region'].browse(vals['zone_region_id'])
            if target_zone.transformer_origin_id and target_zone.transformer_origin_id not in self:
                raise ValidationError(
                    _('الـZone "%s" مرتبط مسبقًا بمحول آخر.') % target_zone.display_name
                )
            if len(self) > 1:
                raise ValidationError(_('غيّر الـZone لمحول واحد في كل مرة للحفاظ على الربط واحد-لواحد.'))
        res = super().write(vals)
        if 'zone_region_id' in vals:
            for rec in self:
                previous_zone = previous_zones[rec.id]
                if previous_zone and previous_zone != rec.zone_region_id and previous_zone.transformer_origin_id == rec:
                    previous_zone.write({'transformer_origin_id': False})
                if rec.zone_region_id:
                    rec.zone_region_id.write({'transformer_origin_id': rec.id})
        if 'name' in vals or 'code' in vals or geography_changed:
            for rec in self:
                if rec.zone_region_id:
                    zone_vals = {}
                    if 'name' in vals:
                        zone_vals['name'] = rec.name
                    if 'code' in vals:
                        zone_vals['code'] = rec.code
                    if geography_changed:
                        if new_area_id is not None:
                            parent = new_area_id
                        else:
                            parent = new_region_id
                        zone_vals['parent_id'] = parent
                    if zone_vals:
                        rec.zone_region_id.write(zone_vals)
        self._check_general_transformer_geography()
        return res

    def unlink(self):
        zones = self.env['utility.region']
        for rec in self:
            if rec.zone_region_id:
                zones |= rec.zone_region_id
        zones.filtered(lambda zone: zone.transformer_origin_id in self).write({
            'transformer_origin_id': False,
        })
        res = super().unlink()
        if zones:
            zones.unlink()
        return res
