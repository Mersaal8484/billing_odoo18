from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from .utility_date_range import normalize_billing_cadence
import logging

_logger = logging.getLogger(__name__)


class UtilityCustomer(models.Model):
    _name = 'utility.customer'
    _description = 'مشترك كهرباء / حساب كهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'utility.dropdown.mixin']
    _rec_name = 'customer_number'
    _order = 'customer_number asc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    customer_number = fields.Char('رقم العميل', required=True, index=True, default=lambda self: _('جديد'))
    external_qr_reference = fields.Char(
        string='معرف QR الخارجي', index=True, tracking=True,
        help='القيمة المميزة التي يتم استخراجها عند مسح QR الخاص بالمشترك بواسطة تطبيق الموبايل.',
    )
    partner_id = fields.Many2one(
        'res.partner', 'العميل / الشريك المحاسبي', required=True,
        index=True, ondelete='restrict',
        domain="[('utility_partner_type', '=', 'subscriber')]",
        help='شريك مستقل ومخصص لهذا الحساب الكهربائي ويستخدم للهوية والفوترة والتحصيل والمحاسبة.')

    category_id = fields.Many2one('utility.subscriber.category', string='فئة المشترك الرئيسية', required=True)
    mobile = fields.Char(related='partner_id.mobile', string='رقم الجوال', readonly=False)
    subscriber_id = fields.Many2one('utility.subscriber', string='نوع المشترك', required=True, domain="[('category_id', '=', category_id)]")
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('active', 'فعال'),
        ('suspended', 'موقوف'),
        ('disconnected', 'مفصول'),
        ('closed', 'مغلق'),
    ], string='الحالة', default='draft', tracking=True)

    available_contract_template_ids = fields.Many2many('utility.contract.template', compute='_compute_available_contract_template_ids')
    block_tariff_config_id = fields.Many2one(
        'utility.block.tariff.config',
        string='إعداد شرائح التعرفة',
        check_company=True,
        tracking=True,
        domain="[('state', '=', 'active'), ('company_id', '=', company_id)]",
    )
    local_block_ids = fields.One2many(
        'utility.customer.block.line',
        'customer_id',
        string='شرائح التعرفة المحلية',
        readonly=True,
    )
    contract_template_id = fields.Many2one('utility.contract.template', string='نموذج العقد')
    contract_start_date = fields.Date('تاريخ بداية العقد')
    contract_end_date = fields.Date('تاريخ نهاية العقد')
    date_contract = fields.Date(string='تاريخ العقد')
    date_sub_start = fields.Date(string='بداية الاشتراك')
    date_end = fields.Date(string='نهاية الاشتراك')

    company_currency_id = fields.Many2one(related='company_id.currency_id', string='العملة')

    cell_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية',
        domain="[('active', '=', True)]")
    transformer_id = fields.Many2one('utility.transformer', string='المحول',
        domain="[('active', '=', True)]")
    is_private_transformer = fields.Boolean(related='transformer_id.is_private', readonly=True, string='هل المحول خاص؟')
    private_transformer_fee = fields.Monetary(
        string='رسوم المحول الخاص',
        currency_field='company_currency_id',
        default=0.0,
        tracking=True,
        help='رسوم دورية ثابتة للمحول الخاص تضاف تلقائيًا إلى فاتورة الكهرباء في كل دورة فوترة.'
    )
    cell_coupling_meter_id = fields.Many2one('utility.meter', 'عداد الفيدر/الخلية',
        domain="[('feeder_id', '=', cell_id)]")

    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    zone_id = fields.Many2one(related='partner_id.zone_id', store=True, string='المنطقة التفصيلية')

    route_id = fields.Many2one('utility.route', string='خط السير', index=True)
    available_route_ids = fields.Many2many(
        'utility.route', compute='_compute_available_route_ids',
        string='المسارات المتاحة')

    meter_id = fields.Many2one('utility.meter', 'العداد', tracking=True)
    payment_type = fields.Selection(related='meter_id.payment_type', store=True, string='نظام الدفع (آجل/مسبق)', readonly=True)

    @api.depends('region_id', 'area_id', 'zone_id')
    def _compute_available_route_ids(self):
        for customer in self:
            domain = customer._get_route_domain(
                region_id=customer.region_id.id if customer.region_id else False,
                area_id=customer.area_id.id if customer.area_id else False,
                zone_id=customer.zone_id.id if customer.zone_id else False,
            )
            customer.available_route_ids = self.env['utility.route'].search(domain)

    @api.constrains('route_id', 'region_id', 'area_id', 'zone_id')
    def _check_route_geographic_consistency(self):
        for customer in self.filtered('route_id'):
            domain = customer._get_route_domain(
                region_id=customer.region_id.id if customer.region_id else False,
                area_id=customer.area_id.id if customer.area_id else False,
                zone_id=customer.zone_id.id if customer.zone_id else False,
            )
            if customer.route_id not in self.env['utility.route'].search(domain):
                raise ValidationError(_(
                    'المسار المختار لا ينتمي إلى النطاق الجغرافي المحدد للحساب الكهربائي.'
                ))

    # الرصيد المحاسبي (آجل) — من move lines محاسبية
    accounting_balance = fields.Monetary(
        'الرصيد المحاسبي', compute='_compute_accounting_balance',
        currency_field='company_currency_id',
        help='الرصيد المستحق بناءً على القيود المحاسبية (الذمم المدينة)')


    opening_balance = fields.Monetary(
        string='الرصيد الافتتاحي',
        currency_field='company_currency_id',
        related='partner_id.open_balance',
        readonly=True,
    )
    opening_move_id = fields.Many2one('account.move', string="قيد الرصيد الافتتاحي", readonly=True)
    current_balance = fields.Monetary(string='المديونية الحالية', currency_field='company_currency_id', related='accounting_balance', store=False)
    
    last_reading_date = fields.Datetime('آخر تاريخ قراءة')
    last_reading_value = fields.Float('آخر قراءة')
    last_invoice_date = fields.Datetime('آخر تاريخ فاتورة')
    last_invoice_reading = fields.Float('قراءة آخر فاتورة')


    uploaded_reading_ids = fields.One2many(
        'utility.reading', 'account_id',
        domain=[('state', 'in', ['draft', 'under_review', 'approved'])],
        string='Uploaded Readings')
    billed_reading_ids = fields.One2many(
        'utility.reading', 'account_id',
        domain=[('state', '=', 'billed')],
        string='Billed Readings')

    invoice_count = fields.Integer('Bills', compute='_compute_smart_buttons')
    accounting_invoice_count = fields.Integer('Accounting Invoices', compute='_compute_smart_buttons')
    reading_count = fields.Integer('Readings', compute='_compute_smart_buttons')
    payment_count = fields.Integer('Payments', compute='_compute_smart_buttons')
    replacement_count = fields.Integer('Meter Replacements', compute='_compute_smart_buttons')
    tamper_count = fields.Integer('Tamper Cases', compute='_compute_smart_buttons')

    _sql_constraints = [
        ('unique_customer_number_company', 'unique(customer_number, company_id)',
         'رقم العميل يجب أن يكون فريداً لكل شركة!'),
        ('unique_external_qr_reference_company', 'unique(external_qr_reference, company_id)',
         'معرف QR الخارجي يجب أن يكون فريداً لكل شركة!'),
        ('unique_accounting_partner', 'unique(partner_id)',
         'لا يمكن ربط أكثر من حساب كهرباء بنفس الشريك المحاسبي.'),
    ]

    @api.constrains('partner_id')
    def _check_customer_partner_identity(self):
        """Ensure the dedicated partner belongs to exactly one utility account."""
        for customer in self:
            if not customer.partner_id:
                raise ValidationError(_('يجب تحديد العميل / الشريك المحاسبي للحساب الكهربائي.'))
            duplicate = self.search([
                ('partner_id', '=', customer.partner_id.id),
                ('id', '!=', customer.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'الشريك المحاسبي %s مرتبط مسبقًا بالحساب الكهربائي %s.'
                ) % (customer.partner_id.display_name, duplicate.customer_number))

    @api.model_create_multi
    def create(self, vals_list):
        """Create one dedicated partner for every new utility account."""
        for vals in vals_list:
            if 'external_qr_reference' in vals:
                vals['external_qr_reference'] = (
                    vals['external_qr_reference'] or '').strip() or False
            if not vals.get('customer_number') or vals.get('customer_number') in (_('جديد'), 'جديد', 'New'):
                vals['customer_number'] = self.env['ir.sequence'].next_by_code('utility.customer') or _('جديد')

            partner = self.env['res.partner'].browse(vals.get('partner_id')).exists()
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': vals['customer_number'],
                    'utility_partner_type': 'subscriber',
                })
                vals['partner_id'] = partner.id
            elif partner.utility_partner_type in ('employee', 'donor', 'supported_entity'):
                labels = dict(partner._fields['utility_partner_type'].selection)
                raise ValidationError(_(
                    'لا يمكن استخدام الشريك %s كحساب كهرباء لأنه مصنف كـ %s.'
                ) % (partner.display_name, labels.get(
                    partner.utility_partner_type, partner.utility_partner_type)))
            elif partner.utility_partner_type != 'subscriber':
                partner.write({'utility_partner_type': 'subscriber'})
            duplicate = self.search([
                ('partner_id', '=', partner.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'الشريك %s مرتبط مسبقًا بالحساب الكهربائي %s.'
                ) % (partner.display_name, duplicate.customer_number))

        customers = super().create(vals_list)
        for customer in customers:
            customer.partner_id.sudo().write({
                'customer_rank': max(customer.partner_id.customer_rank, 1),
                'utility_partner_type': 'subscriber',
            })
            if customer.transformer_id and customer.transformer_id.is_private:
                owner = customer.transformer_id.private_customer_id
                if owner and owner != customer:
                    raise ValidationError(_(
                        'المحول الخاص %s مرتبط مسبقًا بحساب كهرباء آخر.'
                    ) % customer.transformer_id.display_name)
                customer.transformer_id.sudo().write({'private_customer_id': customer.id})
            # Cross-scope mutation integrity: validate the resulting customer geography
            # against the acting user's organizational scope.
            # region_id and area_id are related-stored from partner_id, so we check
            # their resolved values post-create, not raw vals entries.
            #
            # SECURITY: utility_scope_bypass is ONLY honored when the env is running
            # as superuser (migration scripts) OR the user is a Utility Admin.
            # It CANNOT be used as a Privilege Escalation vector via crafted RPC context.
            _bypass_allowed = (
                self.env.su
                or self.env.user.has_group('utility_core.group_utility_admin')
            )
            if not (
                (self.env.context.get('utility_scope_bypass') and _bypass_allowed)
                or self.env.user._is_global_utility_scope()
            ):
                customer_region = customer.partner_id.region_id
                customer_area = customer.partner_id.area_id
                effective_branches = self.env.user._get_effective_branch_ids()
                effective_regions = self.env.user._get_effective_region_ids()
                in_scope = (
                    (customer_area and customer_area.id in effective_branches)
                    or (customer_region and customer_region.id in effective_regions)
                )
                # FAIL-CLOSED: utility.customer is the organizational anchor.
                # A restricted user MUST create customers with a resolvable region/branch.
                # No geography = no scope = reject. This prevents 'unscoped' record creation.
                if not in_scope:
                    raise AccessError(_(
                        'لا يمكنك إنشاء حساب كهربائي خارج نطاقك التنظيمي المخصص، أو بدون منطقة/فرع محدد. '
                        'يجب أن يكون للشريك المحاسبي منطقة أو فرع ضمن نطاقك.'
                    ))
        return customers

    def _get_geographic_billing_period(self):
        """Return the billing cadence imposed by the customer's geography."""
        self.ensure_one()
        recurring_type = False
        if self.area_id and self.area_id.recurring_rule_type:
            recurring_type = self.area_id.recurring_rule_type
        elif self.region_id and self.region_id.recurring_rule_type:
            recurring_type = self.region_id.recurring_rule_type
        return normalize_billing_cadence(recurring_type)

    def _get_effective_billing_period(self):
        """Return the mandatory billing cadence using geography then the contract template."""
        self.ensure_one()
        recurring_type = self._get_geographic_billing_period()
        if not recurring_type and self.contract_template_id and self.contract_template_id.recurring_rule_type:
            recurring_type = self.contract_template_id.recurring_rule_type
        return normalize_billing_cadence(recurring_type)

    def _validate_local_block_layout(self):
        for customer in self:
            lines = customer.local_block_ids.sorted(
                key=lambda line: (line.from_kwh, line.sequence, line.id)
            )
            expected_from = 0.0
            for index, line in enumerate(lines):
                if abs(line.from_kwh - expected_from) > 0.000001:
                    raise ValidationError(
                        _(
                            'الشرائح المحلية للعميل يجب أن تبدأ من 0 وتتصل '
                            'بدون فجوات أو تداخل.'
                        )
                    )
                if not line.to_kwh:
                    if index != len(lines) - 1:
                        raise ValidationError(
                            _('الشريحة المحلية المفتوحة يجب أن تكون الأخيرة.')
                        )
                    continue
                if line.to_kwh <= line.from_kwh:
                    raise ValidationError(
                        _('يجب أن يكون حد نهاية الشريحة أكبر من حد بدايتها.')
                    )
                expected_from = line.to_kwh
            if not lines or lines[-1].to_kwh:
                raise ValidationError(
                    _('يجب أن تنتهي شرائح العميل بشريحة مفتوحة.')
                )

    def action_apply_block_tariff(self):
        self.ensure_one()
        if not (
            self.env.user.has_group('utility_core.group_utility_admin')
            or self.env.user.has_group('utility_core.group_utility_billing_manager')
        ):
            raise AccessError(_('ليس لديك صلاحية تطبيق تعرفة العميل.'))
        self.check_access_rights('write')
        self.check_access_rule('write')

        config = self.block_tariff_config_id
        if not config or config.state != 'active':
            raise UserError(_('اختر إعداد تعرفة نشطاً أولاً.'))
        if config.company_id != self.company_id:
            raise ValidationError(_('يجب أن تتبع التعرفة شركة العميل نفسها.'))
        if not self.contract_template_id:
            raise UserError(_('يجب تحديد قالب عقد للعميل قبل تطبيق التعرفة.'))
        if self.contract_template_id.pricing_mode not in ('block', 'tier'):
            raise UserError(
                _('يمكن تطبيق شرائح التعرفة فقط على عقود التسعير بالشرائح.')
            )

        cadence = self._get_effective_billing_period()
        if cadence not in ('semi_monthly', 'monthly'):
            raise ValidationError(_('تعذر تحديد دورية الفوترة الفعالة للعميل.'))
        if config.billing_cycle != cadence:
            raise ValidationError(
                _(
                    'دورية إعداد التعرفة لا تطابق دورية الفوترة الفعالة '
                    'للعميل.'
                )
            )

        config._validate_block_layout(require_complete=True)
        mutation_context = dict(
            self.env.context, _allow_customer_tariff_block_mutation=True
        )
        self.local_block_ids.with_context(mutation_context).unlink()
        self.env['utility.customer.block.line'].with_context(
            mutation_context
        ).create([
            {
                'customer_id': self.id,
                'source_config_id': config.id,
                'billing_cycle': cadence,
                'sequence': line.sequence,
                'name': line.name,
                'from_kwh': line.from_kwh,
                'to_kwh': line.to_kwh,
                'price_per_kwh': line.price_per_kwh,
            }
            for line in config.line_ids.sorted(
                key=lambda line: (line.from_kwh, line.sequence, line.id)
            )
        ])
        self._validate_local_block_layout()
        self.message_post(
            body=_(
                'تم تطبيق إعداد شرائح التعرفة «%(config)s» على هذا العميل.'
            ) % {'config': config.display_name}
        )
        return True

    def write(self, vals):
        vals = dict(vals)
        if 'external_qr_reference' in vals:
            vals['external_qr_reference'] = (vals['external_qr_reference'] or '').strip() or False
        if 'partner_id' in vals and not self.env.context.get(
                'allow_utility_account_partner_change'):
            for customer in self:
                if customer.partner_id and vals['partner_id'] != customer.partner_id.id:
                    raise ValidationError(_(
                        'لا يمكن تغيير الشريك المحاسبي بعد إنشاء الحساب. '
                        'استخدم إجراء نقل حساب معتمد.'
                    ))
        old_private_transformers = {
            customer.id: customer.transformer_id
            for customer in self if customer.transformer_id and customer.transformer_id.is_private
        }
        if 'partner_id' in vals:
            new_partner = self.env['res.partner'].browse(vals['partner_id']).exists()
            for customer in self:
                if not new_partner:
                    raise ValidationError(_('الشريك المحاسبي المحدد غير موجود.'))
                duplicate = self.search([
                    ('partner_id', '=', new_partner.id),
                    ('id', 'not in', self.ids),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'لا يمكن استخدام الشريك المحاسبي %s؛ فهو مرتبط بالحساب %s.'
                    ) % (new_partner.display_name, duplicate.customer_number))
        res = super().write(vals)
        if 'partner_id' in vals:
            for customer in self:
                if customer.partner_id:
                    customer.partner_id.sudo().write({
                        'customer_rank': max(customer.partner_id.customer_rank, 1),
                        'is_subscriber': True,
                    })
        if 'transformer_id' in vals:
            for customer in self:
                old_transformer = old_private_transformers.get(customer.id)
                if old_transformer and old_transformer != customer.transformer_id:
                    if old_transformer.private_customer_id == customer:
                        old_transformer.sudo().write({'private_customer_id': False})
                transformer = customer.transformer_id
                if transformer and transformer.is_private:
                    if (transformer.private_customer_id
                            and transformer.private_customer_id != customer):
                        raise ValidationError(_(
                            'المحول الخاص %s مرتبط مسبقًا بحساب كهرباء آخر.'
                        ) % transformer.display_name)
                    transformer.sudo().write({'private_customer_id': customer.id})
        # Cross-scope mutation integrity on write:
        # If route_id is being changed, validate the customer geography is in scope.
        # SECURITY: bypass gated to superuser / Utility Admin only.
        _bypass_allowed = (
            self.env.su
            or self.env.user.has_group('utility_core.group_utility_admin')
        )
        if 'route_id' in vals and not (
            (self.env.context.get('utility_scope_bypass') and _bypass_allowed)
            or self.env.user._is_global_utility_scope()
        ):
            effective_branches = self.env.user._get_effective_branch_ids()
            effective_regions = self.env.user._get_effective_region_ids()
            for customer in self:
                customer_area = customer.partner_id.area_id
                customer_region = customer.partner_id.region_id
                in_scope = (
                    (customer_area and customer_area.id in effective_branches)
                    or (customer_region and customer_region.id in effective_regions)
                )
                # FAIL-CLOSED: reject even when customer has no geography
                if not in_scope:
                    raise AccessError(_(
                        'لا يمكنك تعديل خط سير لحساب خارج نطاقك التنظيمي المخصص.'
                    ))
        return res

    @api.constrains('private_transformer_fee')
    def _check_private_transformer_fee_non_negative(self):
        for customer in self:
            if customer.private_transformer_fee < 0:
                raise ValidationError(_(
                    'رسوم المحول الخاص يجب ألا تكون قيمة سالبة.'
                ))

    @api.constrains('transformer_id')
    def _check_private_transformer_assignment(self):
        for customer in self.filtered(lambda rec: rec.transformer_id and rec.transformer_id.is_private):
            other_accounts = customer.transformer_id.customer_ids - customer
            if other_accounts:
                raise ValidationError(_(
                    'المحول الخاص %s مرتبط مسبقًا بحساب كهرباء آخر.'
                ) % customer.transformer_id.display_name)

    @api.constrains('cell_id', 'meter_id')
    def _check_cell_meter_consistency(self):
        for rec in self:
            if rec.cell_id and rec.meter_id:
                cell = rec.cell_id
                cell_meters = cell.meter_ids | cell.coupling_meter_ids
                if rec.meter_id not in cell_meters:
                    raise ValidationError(
                        f"العداد {rec.meter_id.meter_number} لا يتبع المحول/الخلية {cell.name}! "
                        "يرجى اختيار عداد مرتبط بهذا المحول."
                    )

    @api.depends('category_id', 'subscriber_id', 'region_id', 'area_id')
    def _compute_available_contract_template_ids(self):
        for rec in self:
            domain = self._get_contract_template_domain(
                category_id=rec.category_id.id if rec.category_id else False,
                subscriber_id=rec.subscriber_id.id if rec.subscriber_id else False,
                region_id=rec.region_id.id if rec.region_id else False,
                area_id=rec.area_id.id if rec.area_id else False,
                billing_cadence=rec._get_geographic_billing_period(),
            )
            rec.available_contract_template_ids = self.env['utility.contract.template'].search(domain)

    def _find_matching_contract_template(self):
        self.ensure_one()
        if self.subscriber_id and self.subscriber_id.default_contract_template_id:
            default_template = self.subscriber_id.default_contract_template_id
            if default_template in self.available_contract_template_ids:
                return default_template
        if self.available_contract_template_ids:
            return self.available_contract_template_ids[0]
        return self.env['utility.contract.template']

    @api.onchange('category_id', 'subscriber_id', 'region_id', 'area_id')
    def _onchange_contract_template_domain(self):
        available_templates = self.available_contract_template_ids
        if self.contract_template_id and self.contract_template_id not in available_templates:
            self.contract_template_id = False
        if not self.contract_template_id and self.subscriber_id:
            self.contract_template_id = self._find_matching_contract_template()
        return {'domain': {'contract_template_id': [('id', 'in', available_templates.ids)]}}

    @api.constrains('category_id', 'subscriber_id')
    def _check_subscriber_category_compatibility(self):
        for rec in self:
            if rec.category_id and rec.subscriber_id:
                if rec.subscriber_id.category_id != rec.category_id:
                    raise ValidationError(
                        _("نوع المشترك '%s' يجب أن ينتمي إلى فئة المشترك الرئيسية المحددة '%s'.")
                        % (rec.subscriber_id.name, rec.category_id.name)
                    )

    @api.constrains('contract_template_id', 'category_id', 'subscriber_id', 'region_id', 'area_id')
    def _check_contract_subscriber_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            subscriber = rec.subscriber_id
            category = rec.category_id
            if template:
                if category and category not in template.subscriber_category_ids:
                    raise ValidationError(
                        _("قالب العقد '%s' لا يدعم فئة المشترك الرئيسية '%s'.")
                        % (template.name, category.name)
                    )
                if subscriber and subscriber not in template.subscriber_ids:
                    raise ValidationError(
                        _("قالب العقد '%s' لا يدعم نوع المشترك '%s'.")
                        % (template.name, subscriber.name)
                    )
                geographic_cadence = rec._get_geographic_billing_period()
                if (
                    geographic_cadence
                    and normalize_billing_cadence(template.recurring_rule_type) != geographic_cadence
                ):
                    raise ValidationError(
                        _("دورية قالب العقد '%s' لا تطابق دورية منطقة الحساب '%s'.")
                        % (template.name, geographic_cadence)
                    )
                if template.scope == 'restricted':
                    allowed_region_ids = template.region_ids.ids
                    allowed_area_ids = template.area_ids.ids
                    customer_region_id = rec.region_id.id if rec.region_id else False
                    customer_area_id = rec.area_id.id if rec.area_id else False
                    is_region_allowed = customer_region_id in allowed_region_ids if customer_region_id else False
                    is_area_allowed = customer_area_id in allowed_area_ids if customer_area_id else False
                    if not (is_region_allowed or is_area_allowed):
                        raise ValidationError(
                            _("قالب العقد المختار '%s' مخصص لمناطق محددة ولا يدعم المنطقة أو المنطقة الفرعية لهذا المشترك.")
                            % template.name
                        )

    @api.depends('customer_number', 'partner_id', 'partner_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.customer_number}] {rec.partner_id.name or ""}'

    @api.model
    def _search_display_name(self, operator, value):
        """Search relational fields and the external QR reference by display name."""
        if not value:
            return super()._search_display_name(operator, value)
        domains = [[(field, operator, value)] for field in (
            'customer_number',
            'external_qr_reference',
            'partner_id.name',
            'partner_id.national_id',
            'meter_id.meter_number',
        )]
        aggregator = expression.AND if operator in expression.NEGATIVE_TERM_OPERATORS else expression.OR
        return aggregator(domains)

    @api.model
    def _resolve_identifiers(self, customer_id=None, customer_number=None,
                             external_qr_reference=None, meter_id=None,
                             meter_number=None, operational_number=None,
                             lookup_value=None, scope_ids=None):
        """Resolve exact customer identifiers within this recordset scope.

        ``scope_ids`` optionally limits resolution to an authorized customer
        scope. When more than one identifier is supplied, every identifier
        must resolve to one customer.
        """
        scope = [('id', 'in', scope_ids)] if scope_ids is not None else []
        identifiers = []

        def add_exact(domain):
            identifiers.append(self.search(scope + domain, limit=1))
        if customer_id not in (None, '', False):
            try:
                customer_id = int(customer_id)
            except (TypeError, ValueError):
                return self.browse(), 'CUSTOMER_NOT_FOUND'
            add_exact([('id', '=', customer_id)])
        if customer_number not in (None, '', False):
            add_exact([('customer_number', '=', str(customer_number).strip())])
        if external_qr_reference not in (None, '', False):
            add_exact([('external_qr_reference', '=', str(external_qr_reference).strip())])
        if meter_id not in (None, '', False):
            try:
                meter_id = int(meter_id)
            except (TypeError, ValueError):
                return self.browse(), 'CUSTOMER_NOT_FOUND'
            add_exact([('meter_id', '=', meter_id)])
        if meter_number not in (None, '', False):
            add_exact([('meter_id.meter_number', '=', str(meter_number).strip())])
        if operational_number not in (None, '', False):
            add_exact([('meter_id.operational_number', '=', str(operational_number).strip())])
        if lookup_value not in (None, '', False):
            value = str(lookup_value).strip()
            lookup_domain = ['|', '|', '|',
                             ('customer_number', '=', value),
                             ('external_qr_reference', '=', value),
                             ('meter_id.meter_number', '=', value),
                             ('meter_id.operational_number', '=', value)]
            if value.isdigit():
                lookup_domain = ['|', ('id', '=', int(value))] + lookup_domain
            matches = self.search(scope + lookup_domain, limit=2)
            if len(matches) > 1:
                return self.browse(), 'CUSTOMER_IDENTIFIER_AMBIGUOUS'
            identifiers.append(matches)
        if not identifiers:
            return self.browse(), 'CUSTOMER_IDENTIFIER_REQUIRED'
        if any(not customer for customer in identifiers):
            return self.browse(), 'CUSTOMER_NOT_FOUND'
        if len({customer.id for customer in identifiers}) > 1:
            return self.browse(), 'CUSTOMER_IDENTIFIER_MISMATCH'
        return identifiers[0], False

    @api.depends('partner_id')
    def _compute_accounting_balance(self):
        MoveLine = self.env.get('account.move.line')
        if MoveLine is None:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        partner_map = {rec.id: rec.partner_id.id for rec in self if rec.partner_id}
        if not partner_map:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        balance_map = {cid: 0.0 for cid in partner_map}

        company_ids = list(set(rec.company_id.id for rec in self if rec.company_id))
        receivable_accounts = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', company_ids),
        ])
        if not receivable_accounts:
            for rec in self:
                rec.accounting_balance = 0.0
            return

        partner_ids = list(set(partner_map.values()))
        groups = MoveLine.sudo().read_group([
            ('partner_id', 'in', partner_ids),
            ('account_id', 'in', receivable_accounts.ids),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ], ['amount_residual:sum'], ['partner_id'])

        for group in groups:
            partner_id = group['partner_id'][0] if group['partner_id'] else False
            customer_id = next((cid for cid, pid in partner_map.items() if pid == partner_id), False)
            if customer_id:
                balance_map[customer_id] = group.get('amount_residual', 0.0)

        for rec in self:
            rec.accounting_balance = balance_map.get(rec.id, 0.0)

    def _get_receivable_balance(self, exclude_move_ids=None):
        """Return posted unreconciled receivables for this account partner only."""
        self.ensure_one()
        if not self.partner_id:
            return 0.0
        accounts = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_ids', 'in', [self.company_id.id]),
        ])
        if not accounts:
            return 0.0
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('account_id', 'in', accounts.ids),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
        ]
        if exclude_move_ids:
            domain.append(('move_id', 'not in', list(exclude_move_ids)))
        result = self.env['account.move.line'].sudo().read_group(
            domain, ['amount_residual:sum'], [])
        return result[0].get('amount_residual', 0.0) if result else 0.0

    @api.depends('partner_id', 'meter_id')
    def _compute_smart_buttons(self):
        So = self.env.get('sale.order')
        Reading = self.env.get('utility.reading')
        Payment = self.env.get('account.payment')
        Move = self.env.get('account.move')
        Replacement = self.env.get('utility.meter.replacement')
        Tamper = self.env.get('utility.tamper.case')

        customer_ids = self.ids
        partner_map = {rec.id: rec.partner_id.id for rec in self if rec.partner_id}

        counts = {cid: {'invoice': 0, 'accounting_invoice': 0, 'reading': 0,
                         'payment': 0, 'replacement': 0, 'tamper': 0} for cid in customer_ids}

        if So is not None and 'customer_id' in So._fields and customer_ids:
            groups = So.sudo().read_group(
                [('customer_id', 'in', customer_ids)],
                ['customer_id'],
                ['customer_id'],
            )
            for group in groups:
                customer_id = group['customer_id'][0] if group['customer_id'] else False
                if customer_id in counts:
                    counts[customer_id]['invoice'] = group['customer_id_count']
        if Reading is not None and 'account_id' in Reading._fields and customer_ids:
            groups = Reading.sudo().read_group(
                [('account_id', 'in', customer_ids)],
                ['account_id'],
                ['account_id'],
            )
            for g in groups:
                cid = g['account_id'][0] if g['account_id'] else False
                if cid in counts:
                    counts[cid]['reading'] = g['account_id_count']

        if (
            Payment is not None
            and 'utility_sale_order_id' in Payment._fields
            and customer_ids
        ):
            sale_order_ids = self.env['sale.order'].sudo().search([
                ('customer_id', 'in', customer_ids),
            ]).ids
            if sale_order_ids:
                groups = Payment.sudo().read_group(
                    [('utility_sale_order_id', 'in', sale_order_ids)],
                    ['utility_sale_order_id'],
                    ['utility_sale_order_id'],
                )
                so_to_customer = {}
                if sale_order_ids:
                    so_recs = self.env['sale.order'].sudo().browse(sale_order_ids)
                    so_to_customer = {so.id: so.customer_id.id for so in so_recs if so.customer_id}
                for g in groups:
                    so_id = g['utility_sale_order_id'][0] if g['utility_sale_order_id'] else False
                    cid = so_to_customer.get(so_id, False)
                    if cid in counts:
                        counts[cid]['payment'] += g['utility_sale_order_id_count']

        if Move is not None and partner_map:
            partner_ids = list(set(partner_map.values()))
            groups = Move.sudo().read_group([
                ('partner_id', 'in', partner_ids),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ], ['partner_id'], ['partner_id'])
            partner_to_customer_ids = {}
            for customer_id, partner_id in partner_map.items():
                partner_to_customer_ids.setdefault(partner_id, []).append(customer_id)
            for group in groups:
                partner_id = group['partner_id'][0] if group['partner_id'] else False
                for customer_id in partner_to_customer_ids.get(partner_id, []):
                    counts[customer_id]['accounting_invoice'] = group['partner_id_count']

        if Replacement is not None and customer_ids:
            groups = Replacement.sudo().read_group(
                [('utility_account_id', 'in', customer_ids)],
                ['utility_account_id'],
                ['utility_account_id'],
            )
            for g in groups:
                cid = g['utility_account_id'][0] if g['utility_account_id'] else False
                if cid in counts:
                    counts[cid]['replacement'] = g['utility_account_id_count']

        if Tamper is not None and customer_ids:
            groups = Tamper.sudo().read_group(
                [('account_id', 'in', customer_ids)],
                ['account_id'],
                ['account_id'],
            )
            for group in groups:
                customer_id = group['account_id'][0] if group['account_id'] else False
                if customer_id in counts:
                    counts[customer_id]['tamper'] = group['account_id_count']
        for rec in self:
            c = counts.get(rec.id, {})
            rec.invoice_count = c.get('invoice', 0)
            rec.accounting_invoice_count = c.get('accounting_invoice', 0)
            rec.reading_count = c.get('reading', 0)
            rec.payment_count = c.get('payment', 0)
            rec.replacement_count = c.get('replacement', 0)
            rec.tamper_count = c.get('tamper', 0)

    def action_view_replacements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('استبدالات العداد'),
            'res_model': 'utility.meter.replacement',
            'domain': [('utility_account_id', '=', self.id)],
            'context': {'default_utility_account_id': self.id},
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_tampers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('حالات التلاعب'),
            'res_model': 'utility.tamper.case',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفواتير'),
            'res_model': 'sale.order',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_accounting_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفواتير المحاسبية'),
            'res_model': 'account.move',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('القراءات'),
            'res_model': 'utility.reading',
            'domain': [('customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الدفعات'),
            'res_model': 'account.payment',
            'domain': [('utility_sale_order_id.customer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }
