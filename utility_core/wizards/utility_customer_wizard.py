from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class UtilityCustomerWizard(models.TransientModel):
    _name = 'utility.customer.wizard'
    _inherit = ['utility.dropdown.mixin']
    _description = 'معالج تسجيل مشترك وعداد موحد'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'res.partner' and self.env.context.get('active_id'):
            partner = self.env['res.partner'].browse(self.env.context.get('active_id'))
            res.update({
                'name': partner.name,
                'mobile': partner.mobile,
                'national_id': getattr(partner, 'national_id', False),
                'street': partner.street,
                'utility_region_id': partner.region_id.id if partner.region_id else False,
                'utility_area_id': partner.area_id.id if partner.area_id else False,
                'transformer_zone_id': partner.zone_id.id if partner.zone_id else False,
                'subscriber_id': partner.subscriber_id.id if partner.subscriber_id else False,
                'category_id': partner.subscriber_id.category_id.id if partner.subscriber_id and partner.subscriber_id.category_id else False,
            })
        return res

    name = fields.Char(string='اسم المشترك / الجهة', required=True)
    mobile = fields.Char(string='رقم الجوال', size=9)
    national_id = fields.Char(string='الرقم الوطني / الهوية')
    external_qr_reference = fields.Char(
        string='معرف QR الخارجي',
        help='القيمة الناتجة فعلياً من مسح QR بواسطة تطبيق الموبايل؛ يمررها المعالج إلى الحساب فقط.',
    )
    
    street = fields.Char(string='العنوان (الشارع)')
    
    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك الرئيسية', required=True)
    available_subscriber_ids = fields.Many2many('utility.subscriber', compute='_compute_available_subscriber_ids')
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True)
    
    available_contract_template_ids = fields.Many2many('utility.contract.template', compute='_compute_available_contract_template_ids')
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب العقد الافتراضي',
        required=True,
    )
    
    available_route_ids = fields.Many2many('utility.route', compute='_compute_available_route_ids')
    route_id = fields.Many2one('utility.route', string='مسار القراءة الميداني')

    @api.constrains('route_id', 'utility_region_id', 'utility_area_id', 'transformer_zone_id')
    def _check_route_geographic_consistency(self):
        for wizard in self.filtered('route_id'):
            domain = wizard._get_route_domain(
                region_id=wizard.utility_region_id.id if wizard.utility_region_id else False,
                area_id=wizard.utility_area_id.id if wizard.utility_area_id else False,
                zone_id=wizard.transformer_zone_id.id if wizard.transformer_zone_id else False,
            )
            if wizard.route_id not in self.env['utility.route'].search(domain):
                raise ValidationError(_('المسار المختار لا ينتمي إلى النطاق الجغرافي المحدد.'))

    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية", domain="[('type', '=', 'region')]")
    available_area_ids = fields.Many2many('utility.region', compute='_compute_available_area_ids')
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي",
                                      domain="[('type', '=', 'area')]")

    available_zone_ids = fields.Many2many('utility.region', compute='_compute_available_zone_ids')
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول",
                                          domain="[('type', '=', 'zone')]")

    # Private Transformer Fields
    use_private_transformer = fields.Boolean(
        string='محول خاص (المحول للمشترك وحده)',
        default=False,
        help='عند التفعيل: ينشئ المعالج محولاً خاصاً جديداً في utility.transformer ويربطه بالمشترك كخلية خاصة. عدّاد الربط يُنشأ تلقائياً.'
    )
    private_transformer_existing_id = fields.Many2one(
        'utility.transformer', string='محول قائم',
        domain="[('active', '=', True)]",
        help='يمكنك اختيار محول قائم لربطه بهذا المشترك.'
    )
    transformer_name = fields.Char(string='اسم المحول')
    transformer_code = fields.Char(string='كود المحول')
    transformer_capacity = fields.Float(string='السعة (kVA)')
    transformer_phase = fields.Selection([
        ('single', 'أحادي'),
        ('three', 'ثلاثي'),
    ], string='طور المحول')
    transformer_manufacturer = fields.Char(string='الشركة المصنعة للمحول')
    transformer_serial = fields.Char(string='الرقم التسلسلي للمحول')
    voltage_primary = fields.Float(string='الجهد الابتدائي (V)')
    voltage_secondary = fields.Float(string='الجهد الثانوي (V)')
    transformer_substation_id = fields.Many2one('utility.substation', string='المحطة الفرعية')
    transformer_feeder_id = fields.Many2one('utility.feeder', string='المغذي')

    # Optional Meter Creation
    create_meter = fields.Boolean(string='إنشاء وربط عداد جديد فوراً', default=True)
    meter_number = fields.Char(string='رقم العداد', readonly=True, default=lambda self: _('جديد'))
    operational_number = fields.Char(string='الرقم التشغيلي')
    payment_type = fields.Selection([
        ('postpaid', 'آجل الدفع'),
        ('prepaid', 'دفع مسبق'),
        ('manual', 'يدوي')
    ], string='نظام العداد', default='manual', required=True)

    def _get_dynamic_domains(self):
        """Return UI domains without relying on helper field names in JS eval."""
        self.ensure_one()
        area_domain = [('type', '=', 'area')]
        if self.utility_region_id:
            area_domain.append(('parent_id', '=', self.utility_region_id.id))
        zone_domain = [('type', '=', 'zone')]
        if self.utility_area_id:
            zone_domain.append(('parent_id', '=', self.utility_area_id.id))
        return {
            'subscriber_id': self._get_subscriber_domain(self.category_id.id if self.category_id else False),
            'contract_template_id': self._get_contract_template_domain(
                category_id=self.category_id.id if self.category_id else False,
                subscriber_id=self.subscriber_id.id if self.subscriber_id else False,
                region_id=self.utility_region_id.id if self.utility_region_id else False,
                area_id=self.utility_area_id.id if self.utility_area_id else False,
            ),
            'route_id': self._get_route_domain(
                region_id=self.utility_region_id.id if self.utility_region_id else False,
                area_id=self.utility_area_id.id if self.utility_area_id else False,
                zone_id=self.transformer_zone_id.id if self.transformer_zone_id else False,
            ),
            'utility_area_id': area_domain,
            'transformer_zone_id': zone_domain,
        }

    @api.onchange(
        'category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id',
        'transformer_zone_id', 'create_meter'
    )
    def _onchange_dynamic_domains(self):
        for wizard in self:
            return {'domain': wizard._get_dynamic_domains()}

    @api.depends('category_id')
    def _compute_available_subscriber_ids(self):
        for rec in self:
            domain = self._get_subscriber_domain(rec.category_id.id if rec.category_id else False)
            rec.available_subscriber_ids = self.env['utility.subscriber'].search(domain)

    @api.depends('category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _compute_available_contract_template_ids(self):
        for rec in self:
            domain = self._get_contract_template_domain(
                category_id=rec.category_id.id if rec.category_id else False,
                subscriber_id=rec.subscriber_id.id if rec.subscriber_id else False,
                region_id=rec.utility_region_id.id if rec.utility_region_id else False,
                area_id=rec.utility_area_id.id if rec.utility_area_id else False,
            )
            rec.available_contract_template_ids = self.env['utility.contract.template'].search(domain)

    @api.depends('utility_region_id', 'utility_area_id', 'transformer_zone_id')
    def _compute_available_route_ids(self):
        for rec in self:
            domain = self._get_route_domain(
                region_id=rec.utility_region_id.id if rec.utility_region_id else False,
                area_id=rec.utility_area_id.id if rec.utility_area_id else False,
                zone_id=rec.transformer_zone_id.id if rec.transformer_zone_id else False,
            )
            rec.available_route_ids = self.env['utility.route'].search(domain)

    @api.depends('utility_region_id')
    def _compute_available_area_ids(self):
        for rec in self:
            domain = [('type', '=', 'area')]
            if rec.utility_region_id:
                domain.append(('parent_id', '=', rec.utility_region_id.id))
            rec.available_area_ids = self.env['utility.region'].search(domain)

    @api.depends('utility_area_id')
    def _compute_available_zone_ids(self):
        for rec in self:
            domain = [('type', '=', 'zone')]
            if rec.utility_area_id:
                domain.append(('parent_id', '=', rec.utility_area_id.id))
            rec.available_zone_ids = self.env['utility.region'].search(domain)

    def _find_matching_contract_template(self):
        self.ensure_one()
        if self.subscriber_id and self.subscriber_id.default_contract_template_id:
            default_template = self.subscriber_id.default_contract_template_id
            if default_template in self.available_contract_template_ids:
                return default_template
        if self.available_contract_template_ids:
            return self.available_contract_template_ids[0]
        return self.env['utility.contract.template']

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.subscriber_id and self.subscriber_id not in self.available_subscriber_ids:
            self.subscriber_id = False
        if not self.subscriber_id and len(self.available_subscriber_ids) == 1:
            self.subscriber_id = self.available_subscriber_ids[0]

    @api.onchange('category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _onchange_contract_template_cascade(self):
        if self.contract_template_id and self.contract_template_id not in self.available_contract_template_ids:
            self.contract_template_id = False
        if not self.contract_template_id and self.subscriber_id:
            self.contract_template_id = self._find_matching_contract_template()

    @api.onchange('utility_region_id')
    def _onchange_utility_region_id(self):
        if self.utility_area_id and self.utility_area_id not in self.available_area_ids:
            self.utility_area_id = False

    @api.onchange('utility_area_id')
    def _onchange_utility_area_id(self):
        if self.transformer_zone_id and self.transformer_zone_id not in self.available_zone_ids:
            self.transformer_zone_id = False
        if self.route_id and self.route_id not in self.available_route_ids:
            self.route_id = False

    @api.onchange('transformer_zone_id')
    def _onchange_transformer_zone_id(self):
        if self.route_id and self.route_id not in self.available_route_ids:
            self.route_id = False

    @api.onchange('use_private_transformer', 'name')
    def _onchange_use_private_transformer(self):
        if self.use_private_transformer:
            if not self.transformer_name and self.name:
                self.transformer_name = f"محول خاص - {self.name}"

    @api.onchange('transformer_feeder_id')
    def _onchange_transformer_feeder_id(self):
        substation = self.transformer_feeder_id.substation_id
        if substation and substation.zone_id:
            self.transformer_zone_id = substation.zone_id

    @api.constrains('contract_template_id', 'category_id', 'subscriber_id', 'utility_region_id', 'utility_area_id')
    def _check_wizard_contract_template_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            if template and rec.category_id and rec.category_id not in template.subscriber_category_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                    % (template.name, rec.category_id.name)
                )
            if template and rec.subscriber_id and rec.subscriber_id not in template.subscriber_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                    % (template.name, rec.subscriber_id.name)
                )
            if template and template.scope == 'restricted':
                allowed_region_ids = template.region_ids.ids
                allowed_area_ids = template.area_ids.ids
                
                region_id = rec.utility_region_id.id
                area_id = rec.utility_area_id.id
                
                is_region_allowed = region_id in allowed_region_ids if region_id else False
                is_area_allowed = area_id in allowed_area_ids if area_id else False
                
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد الافتراضي المختار '%s' لا يدعم المنطقة أو المنطقة الفرعية المحددة.")
                        % template.name
                    )

    def _get_or_create_private_transformer(self, partner):
        if self.private_transformer_existing_id:
            t = self.private_transformer_existing_id
            if len(t.customer_ids) > 0:
                raise ValidationError('المحول المختار مرتبط بمشتركين مسبقاً.')
            return t

        transformer_code = self.transformer_code or self.env['ir.sequence'].next_by_code(
            'utility.transformer.private')
        if not transformer_code:
            raise ValidationError(_('تعذر توليد كود المحول الخاص.'))

        if self.env['utility.transformer'].search([
            ('company_id', '=', self.env.company.id),
            ('code', '=', transformer_code),
        ], limit=1):
            raise ValidationError(_('كود المحول مستخدم بالفعل.'))

        return self.env['utility.transformer'].create({
            'name': self.transformer_name or f"محول خاص - {partner.name}",
            'code': transformer_code,
            'capacity': self.transformer_capacity,
            'phase': self.transformer_phase or 'single',
            'manufacturer': self.transformer_manufacturer,
            'serial_number': self.transformer_serial,
            'voltage_primary': self.voltage_primary,
            'voltage_secondary': self.voltage_secondary,
            'substation_id': self.transformer_substation_id.id if self.transformer_substation_id else False,
            'feeder_id': self.transformer_feeder_id.id if self.transformer_feeder_id else False,
            'zone_region_id': self.transformer_zone_id.id if self.transformer_zone_id else False,
            'is_private': True,
        })

    def _validate_operational_number_required_for_new_meter(self):
        """Subscriber onboarding requires the logical operational number when a
        new meter is created; the physical serial (stock.lot) is never required
        here and stays under Odoo Inventory control."""
        self.ensure_one()
        if self.create_meter and not (self.operational_number or '').strip():
            raise ValidationError(_('الرقم التشغيلي للعداد مطلوب عند إنشاء وربط عداد للمشترك.'))

    def action_create_customer(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('utility_core.group_utility_supervisor')
            or self.env.user.has_group('utility_core.group_utility_admin')
        ):
            raise AccessError(_('ليس لديك صلاحية إنشاء مشترك من هذا المعالج.'))
        if self.use_private_transformer and not self.env.user.has_group(
            'utility_core.group_utility_admin'
        ):
            raise AccessError(_('إنشاء محول خاص يتطلب صلاحية مدير النظام.'))
        self._validate_operational_number_required_for_new_meter()

        if self.subscriber_id and self.category_id and self.subscriber_id.category_id != self.category_id:
            raise ValidationError(
                _("نوع المشترك '%s' يجب أن ينتمي إلى فئة المشترك الرئيسية المحددة '%s'.")
                % (self.subscriber_id.name, self.category_id.name)
            )

        if self.contract_template_id:
            if self.category_id and self.category_id not in self.contract_template_id.subscriber_category_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                    % (self.contract_template_id.name, self.category_id.name)
                )
            if self.subscriber_id and self.subscriber_id not in self.contract_template_id.subscriber_ids:
                raise ValidationError(
                    _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                    % (self.contract_template_id.name, self.subscriber_id.name)
                )
            if self.contract_template_id.scope == 'restricted':
                allowed_region_ids = self.contract_template_id.region_ids.ids
                allowed_area_ids = self.contract_template_id.area_ids.ids
                
                region_id = self.utility_region_id.id
                area_id = self.utility_area_id.id
                
                is_region_allowed = region_id in allowed_region_ids if region_id else False
                is_area_allowed = area_id in allowed_area_ids if area_id else False
                
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد المختار '%s' مخصص لمناطق محددة ولا يدعم المنطقة أو المنطقة الفرعية المحددة.")
                        % self.contract_template_id.name
                    )

        # 1. Get or Create res.partner
        partner_vals = {
            'name': self.name,
            'mobile': self.mobile,
            'national_id': self.national_id,
            'street': self.street,
            'is_subscriber': True,
            'subscriber_id': self.subscriber_id.id,
            'region_id': self.utility_region_id.id if self.utility_region_id else False,
            'area_id': self.utility_area_id.id if self.utility_area_id else False,
            'zone_id': self.transformer_zone_id.id if self.transformer_zone_id else False,
        }
        
        partner = False
        if self.env.context.get('active_model') == 'res.partner' and self.env.context.get('active_id'):
            partner = self.env['res.partner'].browse(self.env.context.get('active_id'))
            partner.write(partner_vals)
        else:
            partner = self.env['res.partner'].create(partner_vals)

        # 2. Handle Private Transformer before customer creation
        transformer = False
        if self.use_private_transformer:
            transformer = self._get_or_create_private_transformer(partner)

        # 3. Create utility.meter before customer if create_meter is True
        meter = False
        if self.create_meter:
            status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)
            meter_vals = {
                'status_id': status_active.id if status_active else False,
                'meter_number': self.meter_number if self.meter_number and self.meter_number not in (_('جديد'), 'جديد', 'New') else _('جديد'),
                'operational_number': self.operational_number or False,
                'transformer_id': transformer.id if transformer else False,
                'feeder_id': transformer.feeder_id.id if transformer and transformer.feeder_id else False,
                'payment_type': self.payment_type,
            }
            meter_vals.update(self._prepare_meter_vals())
            meter = self.env['utility.meter'].create(meter_vals)

        # 4. Create utility.customer
        customer_vals = {
            'partner_id': partner.id,
            'external_qr_reference': self.external_qr_reference or False,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_id.id,
            'contract_template_id': self.contract_template_id.id,
            'route_id': self.route_id.id if self.route_id else False,
            'state': 'draft',
            'meter_id': meter.id if meter else False,
            'transformer_id': transformer.id if transformer else False,
            'cell_id': transformer.feeder_id.id if transformer and transformer.feeder_id else False,
        }
        customer = self.env['utility.customer'].create(customer_vals)
        
        if meter:
            customer.with_context(lifecycle_operation=True).write({'meter_id': meter.id})
            meter_write_vals = {
                'customer_id': customer.id,
                'connection_type': 'subscriber',
            }
            if transformer and transformer.is_private:
                meter_write_vals['is_coupling_meter'] = True
            meter.write(meter_write_vals)

        customer.action_activate()

        # 5. Link meter as coupling meter for the private transformer
        if transformer and meter:
            transformer.write({'coupling_meter_id': meter.id})

        # 6. Return action to open the newly created customer form
        return {
            'name': _('بطاقة المشترك'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer',
            'view_mode': 'form',
            'res_id': customer.id,
            'target': 'current',
        }

    def _prepare_meter_vals(self):
        """Return optional module-owned values for a newly created meter."""
        self.ensure_one()
        return {}
