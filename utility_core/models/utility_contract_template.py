from datetime import date
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from .utility_date_range import normalize_billing_cadence

_logger = logging.getLogger(__name__)


class UtilityContractTemplate(models.Model):
    _name = 'utility.contract.template'
    _description = 'قالب عقد الكهرباء'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الرمز', required=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )

    # تكوين التكرار والفوترة
    recurring_rule_type = fields.Selection([
        ('monthly', 'شهري'),
        ('semi_monthly', 'نصف شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
    ], default='monthly', required=True)
    recurring_invoicing_type = fields.Selection([
        ('postpaid', 'آجل'),
    ], default='postpaid', required=True)

    recurring_interval = fields.Integer(default=1, string='الفاصل الزمني للدورة')

    # البنود
    line_ids = fields.One2many('utility.contract.template.line', 'template_id', copy=True, string='بنود العقد')
    subscriber_category_ids = fields.Many2many('utility.subscriber.category', string='فئات المشتركين الرئيسية', required=True)
    subscriber_ids = fields.Many2many('utility.subscriber', string='انواع المشتركين', required=True)
    scope = fields.Selection([
        ('global', 'عام على جميع المناطق'),
        ('restricted', 'مخصص لمناطق محددة')
    ], string='نطاق التغطية الجغرافية', default='global', required=True)
    region_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_region_rel',
        'template_id',
        'region_id',
        string='المناطق الرئيسية المسموح بها',
        domain="[('type', '=', 'region')]",
        help="المناطق الرئيسية المسموح بها لهذا القالب"
    )
    area_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_area_rel',
        'template_id',
        'region_id',
        string='المناطق الفرعية المسموح بها',
        domain="[('type', '=', 'area')]",
        help="المناطق الفرعية/الفروع المسموح بها لهذا القالب"
    )

    # إعدادات الحسابات والتعرفة
    pricelist_id = fields.Many2one(
        'product.pricelist', 'قائمة الأسعار',
        default=lambda self: self.env.company.utility_default_pricelist_id,
        help='تُحدد تلقائياً من الإعداد العام للشركة ولا تحتاج إلى اختيار داخل العقد.')
    journal_id = fields.Many2one(
        'account.journal', 'اليومية',
        domain="[('type', 'in', ['sale', 'general'])]",
        default=lambda self: self.env.company.sales_journal_id,
        help='اليومية الافتراضية لفواتير هذا القالب؛ يتم ضبطها تلقائياً على يومية مبيعات الكهرباء.')

    # ── تسعير (دمج utility.tariff) ──────────────────────────────────────
    pricing_mode = fields.Selection([
        ('flat', 'سعر موحّد بدون شرائح'),
        ('tier', 'Flat Tier / سعر شريحة واحدة'),
        ('block', 'Progressive Tier / شرائح تصاعدية'),
        ('seasonal', 'موسمي'),
        ('tou', 'حسب وقت الاستخدام'),
    ], string='نمط التسعير', default='flat',
        help=(
            'سعر موحّد: سعر ثابت لكل الاستهلاك بدون شرائح. '
            'Flat Tier: اختيار شريحة واحدة حسب إجمالي الاستهلاك وتطبيق سعرها على كامل الاستهلاك. '
            'Progressive Tier: تقسيم الاستهلاك على الشرائح وتطبيق سعر كل شريحة على الجزء الواقع داخلها.'
        ))
    price_per_kwh = fields.Monetary('سعر الكيلوواط/ساعة', default=0.0, currency_field='currency_id')
    service_charge = fields.Monetary('رسم الخدمة الثابت', default=0.0, currency_field='currency_id',
        help='مبلغ شهري ثابت لا يتأثر بالاستهلاك (رسوم الاشتراك والصيانة)')
    fixed_charge = fields.Monetary(
        string='رسم ثابت (مرادف)',
        related='service_charge',
        currency_field='currency_id',
        help='حقل مرادف لـ service_charge — للقراءة فقط. سيتم إزالته في الإصدارات القادمة.'
    )
    min_charge = fields.Monetary('الحد الأدنى للفوترة', default=0.0, currency_field='currency_id')
    max_charge = fields.Monetary('الحد الأقصى للفوترة', default=0.0, currency_field='currency_id')
    effective_date = fields.Date('تاريخ السريان')
    end_date = fields.Date('تاريخ الانتهاء')
    is_active = fields.Boolean('فعّال', compute='_compute_is_active', store=True)

    # رسوم محلية (معلم/نظافة/مجلس محلي) — تُحسب على أساس الاستهلاك
    local_fee_per_kwh = fields.Monetary('رسم محلي لكل kWh (افتراضي)', default=0.0, currency_field='currency_id',
        help='السعر الموحد للرسوم المحلية عند استخدام نوع بند العداد = رسوم محلية')
    local_fee_mu_allim = fields.Monetary('رسم المعلم لكل kWh', default=0.0, currency_field='currency_id')
    local_fee_cleaning = fields.Monetary('رسم النظافة لكل kWh', default=0.0, currency_field='currency_id')

    # خصم الدعم — أول N وحدة تُخصم على الجهة الداعمة
    subsidy_enabled = fields.Boolean(
        string='يخضع لخصم الدعم',
        default=False,
        help='عند التفعيل يتم احتساب بند خصم الدعم للمشتركين المؤهلين فقط.')
    sponsor_id = fields.Many2one(
        'res.partner', string='الجهة الداعمة',
        domain="[('utility_partner_type', '=', 'donor')]",
        default=lambda self: self.env.company.utility_default_sponsor_id,
        help='الجهة التي سيتم تقييد الخصم عليها')

    def _get_effective_sponsor(self):
        self.ensure_one()
        return self.sponsor_id or self.company_id.utility_default_sponsor_id
    discount_formula_id = fields.Many2one('utility.formula', string='معادلة الخصم',
        help='معادلة ديناميكية لحساب كمية الخصم')
    discount_block_ids = fields.One2many('utility.contract.template.block', 'template_id',
        domain=[('is_discount', '=', True)], string='شرائح الخصم التدريجية', copy=True)

    # شرائح التسعير: tier = شريحة واحدة لكامل الاستهلاك، block = توزيع تصاعدي على الشرائح.
    block_ids = fields.One2many('utility.contract.template.block', 'template_id',
        domain=[('is_discount', '=', False)], string='شرائح التسعير', copy=True)
    history_ids = fields.One2many('utility.contract.template.history', 'template_id',
        string='سجل التغييرات', readonly=True)

    # إصدارات قالب العقد الثابتة تاريخياً
    version_ids = fields.One2many(
        'utility.contract.template.version',
        'template_id',
        string='إصدارات القالب',
        readonly=True,
    )
    current_version_id = fields.Many2one(
        'utility.contract.template.version',
        string='الإصدار التجاري الحالي',
        compute='_compute_current_version',
        store=True,
    )
    version_count = fields.Integer(
        string='عدد الإصدارات',
        compute='_compute_version_count',
    )

    # ── تتبع الاستنساخ (Clone Provenance) ──────────────────────────────────
    cloned_from_template_id = fields.Many2one(
        'utility.contract.template',
        string='مستنسخ من قالب',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='قالب العقد الأصلي الذي تم استنساخ هذه التهيئة منه.',
    )
    cloned_at = fields.Datetime(
        string='وقت الاستنساخ',
        readonly=True,
        copy=False,
    )
    cloned_by = fields.Many2one(
        'res.users',
        string='المستنسخ بواسطة',
        readonly=True,
        copy=False,
    )

    # سير العمل الآلي
    sale_autoconfirm = fields.Boolean(default=True, string='تأكيد أمر البيع تلقائياً')
    create_invoice_automatically = fields.Boolean(default=True, string='إنشاء الفاتورة تلقائياً')
    validate_invoice_automatically = fields.Boolean(default=False, string='التحقق من الفاتورة تلقائياً')

    # الدفع التلقائي
    is_auto_pay = fields.Boolean(string='دفع تلقائي')
    auto_pay_retries = fields.Integer('عدد محاولات الدفع الافتراضي', default=3)
    auto_pay_retry_hours = fields.Integer('ساعات الانتظار بين المحاولات', default=1)
    active = fields.Boolean('نشط', default=True)

    _sql_constraints = [
        ('unique_code_company',
         'unique(code, company_id)',
         'رمز قالب العقد موجود مسبقاً في هذه الشركة. يجب أن يكون الرمز فريداً.'),
    ]

    @api.depends('version_ids', 'version_ids.version_number')
    def _compute_current_version(self):
        for rec in self:
            latest = rec.version_ids.sorted('version_number', reverse=True)[:1]
            rec.current_version_id = latest.id if latest else False

    @api.depends('version_ids')
    def _compute_version_count(self):
        for rec in self:
            rec.version_count = len(rec.version_ids)

    @api.depends('effective_date', 'end_date')
    def _compute_is_active(self):
        today = date.today()
        for r in self:
            if r.effective_date and r.effective_date > today:
                r.is_active = False
            elif r.end_date and r.end_date < today:
                r.is_active = False
            else:
                r.is_active = True

    # ── قيود منطقية على التسعير والأنماط المدعومة ──────────────────────────────
    @api.constrains('pricing_mode')
    def _check_pricing_mode_supported(self):
        for rec in self:
            if rec.pricing_mode == 'seasonal':
                raise ValidationError(_(
                    "نمط التسعير 'الموسمي' (Seasonal) غير مدعوم في الإصدار الحالي لعدم اكتمال دورة التسعير الشهرية/الموسمية في قراءات العدادات. "
                    "يُرجى استخدام 'Flat' أو 'Flat Tier' أو 'Progressive Tier'."
                ))
            elif rec.pricing_mode == 'tou':
                raise ValidationError(_(
                    "نمط التسعير 'حسب وقت الاستخدام' (TOU) غير مدعوم في الإصدار الحالي ويتطلب توفر بيانات القراءات الفترية اللحظية (AMI/Interval Data). "
                    "يُرجى استخدام 'Flat' أو 'Flat Tier' أو 'Progressive Tier'."
                ))

    @api.constrains('min_charge', 'max_charge')
    def _check_min_max_charge(self):
        for r in self:
            if r.min_charge and r.max_charge and r.min_charge > r.max_charge:
                raise ValidationError(
                    'الحد الأدنى للفوترة (%.2f) يجب أن يكون أقل من '
                    'الحد الأقصى (%.2f).'
                    % (r.min_charge, r.max_charge)
                )

    @api.constrains('price_per_kwh', 'service_charge')
    def _check_positive_prices(self):
        for r in self:
            if r.price_per_kwh < 0:
                raise ValidationError('سعر الكيلووات/ساعة لا يمكن أن يكون سالباً.')
            if r.service_charge < 0:
                raise ValidationError('رسم الخدمة الثابت لا يمكن أن يكون سالباً.')

    @api.onchange('pricing_mode')
    def _onchange_pricing_mode(self):
        """تهيئة شريحة أولية تلقائياً عند اختيار نمط شرائح لتسهيل الإدخال ومنع رسائل الخطأ المفاجئة."""
        if self.pricing_mode in ('tier', 'block') and not self.block_ids:
            self.block_ids = [(0, 0, {
                'sequence': 10,
                'name': _('الشريحة الأولى (0-1,000)'),
                'from_kwh': 0,
                'to_kwh': 1000,
                'price_per_kwh': self.price_per_kwh or 150.0,
                'is_discount': False,
            })]

    def _get_pricing_blocks(self):
        self.ensure_one()
        return self.block_ids.filtered(lambda b: not b.is_discount).sorted(
            lambda b: (b.from_kwh or 0.0, b.sequence or 0, b.id or 0)
        )

    def _get_discount_blocks(self):
        self.ensure_one()
        return self.discount_block_ids.filtered(lambda b: b.is_discount).sorted(
            lambda b: (b.from_kwh or 0.0, b.sequence or 0, b.id or 0)
        )

    def _validate_contract_template_tiers(self):
        """Validate complete pricing and discount tier configuration."""
        for rec in self:
            pricing_blocks = rec._get_pricing_blocks()
            discount_blocks = rec._get_discount_blocks()
            pricing_label = dict(rec._fields['pricing_mode'].selection).get(rec.pricing_mode)

            if rec.pricing_mode in ('tier', 'block'):
                if not pricing_blocks:
                    raise ValidationError(
                        _("نمط التسعير '%s' يتطلب تعريف شرائح تسعير مرتبة على قالب العقد '%s'.")
                        % (pricing_label, rec.name)
                    )

            has_discount_line = rec.line_ids.filtered(lambda line: line.meter_line_type == 'discount')
            if rec.discount_formula_id and has_discount_line:
                if not discount_blocks:
                    raise ValidationError(
                        _("قالب العقد '%s' يحتوي خصم دعم بمعادلة، لذلك يجب تعريف شرائح الخصم التصاعدية.")
                        % rec.name
                    )

    @api.constrains('pricing_mode', 'discount_formula_id', 'block_ids', 'discount_block_ids', 'line_ids')
    def _check_contract_template_tiers(self):
        if (
            self.env.context.get('install_mode')
            or self.env.context.get('install_module')
            or self.env.context.get('skip_tier_validation')
        ):
            return
        self._validate_contract_template_tiers()

    @api.constrains('subscriber_category_ids', 'subscriber_ids')
    def _check_categories_and_types_compatibility(self):
        for rec in self:
            if not rec.subscriber_category_ids:
                raise ValidationError(_('يجب اختيار فئات المشتركين الرئيسية لقالب العقد!'))
            if not rec.subscriber_ids:
                raise ValidationError(_('يجب اختيار انواع المشتركين لقالب العقد!'))
            for sub in rec.subscriber_ids:
                if sub.category_id not in rec.subscriber_category_ids:
                    raise ValidationError(
                        _("نوع المشترك '%s' لا يتبع أي من فئات المشتركين الرئيسية المحددة لقالب العقد.")
                        % sub.name
                    )

    @api.onchange('subscriber_category_ids')
    def _onchange_subscriber_category_ids(self):
        """Keep subscriber types limited to the selected main categories."""
        self.ensure_one()
        allowed_subscribers = self.subscriber_ids.filtered(
            lambda subscriber: subscriber.category_id in self.subscriber_category_ids
        )
        if allowed_subscribers != self.subscriber_ids:
            self.subscriber_ids = allowed_subscribers

        return {
            'domain': {
                'subscriber_ids': [('category_id', 'in', self.subscriber_category_ids.ids)],
            },
        }

    @api.constrains('scope', 'region_ids', 'area_ids')
    def _check_scope_regions(self):
        for rec in self:
            if rec.scope == 'restricted' and not rec.region_ids and not rec.area_ids:
                raise ValidationError(_("يجب اختيار منطقة رئيسية أو منطقة فرعية واحدة على الأقل عند تحديد نطاق التغطية كمخصص!"))
            if rec.scope == 'restricted' and rec.area_ids and not rec.region_ids:
                raise ValidationError(
                    _("يجب اختيار المنطقة الرئيسية قبل اختيار الفروع في قالب العقد.")
                )
            invalid_cadence_regions = rec.region_ids.filtered(
                lambda region: normalize_billing_cadence(region.recurring_rule_type)
                != normalize_billing_cadence(rec.recurring_rule_type)
            )
            invalid_cadence_areas = rec.area_ids.filtered(
                lambda area: normalize_billing_cadence(area.recurring_rule_type)
                != normalize_billing_cadence(rec.recurring_rule_type)
            )
            if invalid_cadence_regions or invalid_cadence_areas:
                raise ValidationError(
                    _("يجب أن تطابق دورية فواتير المناطق والفروع دورية قالب العقد.")
                )
            invalid_areas = rec.area_ids.filtered(
                lambda area: rec.region_ids and area.parent_id not in rec.region_ids
            )
            if invalid_areas:
                raise ValidationError(
                    _("الفروع المحددة يجب أن تتبع المناطق الرئيسية المختارة في قالب العقد.")
                )

    @api.onchange('region_ids')
    def _onchange_region_ids(self):
        """Limit branches to the selected regions and discard stale selections."""
        self.ensure_one()
        allowed_areas = self.area_ids.filtered(
            lambda area: area.parent_id in self.region_ids
        )
        if allowed_areas != self.area_ids:
            self.area_ids = allowed_areas

        domain = [('type', '=', 'area')]
        if self.region_ids:
            domain.append(('parent_id', 'in', self.region_ids.ids))
        return {'domain': {'area_ids': domain}}

    @api.onchange('recurring_rule_type')
    def _onchange_recurring_rule_type_scope(self):
        """Keep the geographic scope compatible with the template cadence."""
        self.ensure_one()
        cadence = normalize_billing_cadence(self.recurring_rule_type)
        self.region_ids = self.region_ids.filtered(
            lambda region: normalize_billing_cadence(region.recurring_rule_type) == cadence
        )
        self.area_ids = self.area_ids.filtered(
            lambda area: (
                normalize_billing_cadence(area.recurring_rule_type) == cadence
                and area.parent_id in self.region_ids
            )
        )
        return {
            'domain': {
                'region_ids': [
                    ('type', '=', 'region'),
                    ('recurring_rule_type', '=', cadence),
                ],
                'area_ids': [
                    ('type', '=', 'area'),
                    ('parent_id', 'in', self.region_ids.ids),
                    ('recurring_rule_type', '=', cadence),
                ],
            },
        }

    # ── إدارة وتوليد الإصدارات التجارية (Version Management) ──────────────────
    def _generate_version_snapshot_data(self):
        """تجميع لقطة البيانات التجارية المسعرة بصيغة JSON قابلة للتدقيق التاريخي الكامل."""
        self.ensure_one()
        blocks_data = []
        for b in self.block_ids.sorted(lambda x: (x.from_kwh, x.sequence, x.id)):
            blocks_data.append({
                'id': b.id,
                'name': b.name or '',
                'sequence': b.sequence,
                'from_kwh': b.from_kwh or 0.0,
                'to_kwh': b.to_kwh or 0.0,
                'price_per_kwh': b.price_per_kwh or 0.0,
                'is_discount': False,
            })
        discount_blocks_data = []
        for db in self.discount_block_ids.sorted(lambda x: (x.from_kwh, x.sequence, x.id)):
            discount_blocks_data.append({
                'id': db.id,
                'name': db.name or '',
                'sequence': db.sequence,
                'from_kwh': db.from_kwh or 0.0,
                'to_kwh': db.to_kwh or 0.0,
                'price_per_kwh': db.price_per_kwh or 0.0,
                'is_discount': True,
            })
        lines_data = []
        for l in self.line_ids.sorted('sequence'):
            lines_data.append({
                'id': l.id,
                'sequence': l.sequence,
                'name': l.name or '',
                'meter_line_type': l.meter_line_type,
                'specific_price': l.specific_price or 0.0,
                'product_id': l.product_id.id if l.product_id else False,
                'product_name': l.product_id.display_name if l.product_id else '',
                'qty_formula_id': l.qty_formula_id.id if l.qty_formula_id else False,
                'qty_formula_code': l.qty_formula_id.code if l.qty_formula_id else '',
            })

        return {
            'template_id': self.id,
            'template_code': self.code,
            'template_name': self.name,
            'recurring_rule_type': self.recurring_rule_type,
            'pricing_mode': self.pricing_mode,
            'price_per_kwh': self.price_per_kwh or 0.0,
            'service_charge': self.service_charge or 0.0,
            'min_charge': self.min_charge or 0.0,
            'max_charge': self.max_charge or 0.0,
            'local_fee_per_kwh': self.local_fee_per_kwh or 0.0,
            'local_fee_mu_allim': self.local_fee_mu_allim or 0.0,
            'local_fee_cleaning': self.local_fee_cleaning or 0.0,
            'subsidy_enabled': self.subsidy_enabled,
            'sponsor_id': self._get_effective_sponsor().id if self._get_effective_sponsor() else False,
            'sponsor_name': self._get_effective_sponsor().name if self._get_effective_sponsor() else '',
            'discount_formula_id': self.discount_formula_id.id if self.discount_formula_id else False,
            'discount_formula_code': self.discount_formula_id.code if self.discount_formula_id else '',
            'discount_formula_name': self.discount_formula_id.name if self.discount_formula_id else '',
            'pricing_blocks': blocks_data,
            'discount_blocks': discount_blocks_data,
            'contract_lines': lines_data,
        }

    def _get_or_create_active_version(self):
        """الحصول على الإصدار التجاري النشط أو إنشاء إصدار جديد إذا كان الإصدار السابق مستخدماً في فواتير."""
        self.ensure_one()
        latest = self.version_ids.sorted('version_number', reverse=True)[:1]
        snapshot_dict = self._generate_version_snapshot_data()
        snapshot_json = json.dumps(snapshot_dict, ensure_ascii=False, sort_keys=True)

        if not latest:
            version_num = 1
            version_code = f"{self.code or 'CT'}-V{version_num}"
            return self.env['utility.contract.template.version'].create({
                'template_id': self.id,
                'version_number': version_num,
                'version_code': version_code,
                'pricing_mode': self.pricing_mode,
                'price_per_kwh': self.price_per_kwh,
                'service_charge': self.service_charge,
                'min_charge': self.min_charge,
                'max_charge': self.max_charge,
                'local_fee_per_kwh': self.local_fee_per_kwh,
                'local_fee_mu_allim': self.local_fee_mu_allim,
                'local_fee_cleaning': self.local_fee_cleaning,
                'sponsor_id': self._get_effective_sponsor().id if self._get_effective_sponsor() else False,
                'discount_formula_id': self.discount_formula_id.id if self.discount_formula_id else False,
                'discount_formula_name': self.discount_formula_id.name if self.discount_formula_id else False,
                'pricing_snapshot_json': snapshot_json,
            })

        # فحص ما إذا كان هناك تغيير في التكوين التجاري مقارنة بأحدث إصدار
        is_changed = (
            latest.pricing_mode != self.pricing_mode or
            latest.price_per_kwh != self.price_per_kwh or
            latest.service_charge != self.service_charge or
            latest.min_charge != self.min_charge or
            latest.max_charge != self.max_charge or
            latest.local_fee_per_kwh != self.local_fee_per_kwh or
            latest.local_fee_mu_allim != self.local_fee_mu_allim or
            latest.local_fee_cleaning != self.local_fee_cleaning or
            latest.sponsor_id != self._get_effective_sponsor() or
            latest.discount_formula_id != self.discount_formula_id or
            latest.pricing_snapshot_json != snapshot_json
        )

        if not is_changed:
            return latest

        # إذا كان الإصدار الأخير مستخدماً في فواتير كهرباء سابقة -> ننشئ إصداراً جديداً برقم تصاعدي
        if latest._is_actually_used_in_billing():
            next_num = latest.version_number + 1
            version_code = f"{self.code or 'CT'}-V{next_num}"
            return self.env['utility.contract.template.version'].create({
                'template_id': self.id,
                'version_number': next_num,
                'version_code': version_code,
                'pricing_mode': self.pricing_mode,
                'price_per_kwh': self.price_per_kwh,
                'service_charge': self.service_charge,
                'min_charge': self.min_charge,
                'max_charge': self.max_charge,
                'local_fee_per_kwh': self.local_fee_per_kwh,
                'local_fee_mu_allim': self.local_fee_mu_allim,
                'local_fee_cleaning': self.local_fee_cleaning,
                'sponsor_id': self._get_effective_sponsor().id if self._get_effective_sponsor() else False,
                'discount_formula_id': self.discount_formula_id.id if self.discount_formula_id else False,
                'discount_formula_name': self.discount_formula_id.name if self.discount_formula_id else False,
                'pricing_snapshot_json': snapshot_json,
            })
        else:
            # إذا لم يُستخدم الإصدار بعد في أي فاتورة -> نحدثه في مكانه
            latest.with_context(_force_version_update=True).write({
                'pricing_mode': self.pricing_mode,
                'price_per_kwh': self.price_per_kwh,
                'service_charge': self.service_charge,
                'min_charge': self.min_charge,
                'max_charge': self.max_charge,
                'local_fee_per_kwh': self.local_fee_per_kwh,
                'local_fee_mu_allim': self.local_fee_mu_allim,
                'local_fee_cleaning': self.local_fee_cleaning,
                'sponsor_id': self._get_effective_sponsor().id if self._get_effective_sponsor() else False,
                'discount_formula_id': self.discount_formula_id.id if self.discount_formula_id else False,
                'discount_formula_name': self.discount_formula_id.name if self.discount_formula_id else False,
                'pricing_snapshot_json': snapshot_json,
            })
            return latest

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._get_or_create_active_version()
        return records

    def write(self, vals):
        """عند تغيير الأسعار أو التكوين التجاري، نسجل التاريخ ونحدث الإصدار التجاري."""
        commercial_fields = {
            'recurring_rule_type', 'pricing_mode', 'price_per_kwh', 'service_charge', 'min_charge', 'max_charge',
            'local_fee_per_kwh', 'local_fee_mu_allim', 'local_fee_cleaning', 'subsidy_enabled',
            'sponsor_id', 'discount_formula_id', 'block_ids', 'discount_block_ids', 'line_ids'
        }
        needs_version_sync = bool(commercial_fields & set(vals))
        price_fields = {'price_per_kwh', 'service_charge'}
        needs_history = bool(price_fields & set(vals))

        # التقاط القيم القديمة قبل الكتابة
        old_prices = {}
        if needs_history:
            old_prices = {
                r.id: {
                    'price_per_kwh': r.price_per_kwh,
                    'service_charge': r.service_charge,
                }
                for r in self
            }

        res = super().write(vals)

        # تسجيل التاريخ إذا تغيرت الأسعار
        if needs_history:
            for r in self:
                old = old_prices.get(r.id, {})
                new_price = vals.get('price_per_kwh', old.get('price_per_kwh', r.price_per_kwh))
                new_service = vals.get('service_charge', old.get('service_charge', r.service_charge))
                if (old.get('price_per_kwh') != new_price or
                        old.get('service_charge') != new_service):
                    self.env['utility.contract.template.history'].create({
                        'template_id': r.id,
                        'old_price': old.get('price_per_kwh', 0),
                        'new_price': new_price,
                        'old_service_charge': old.get('service_charge', 0),
                        'new_service_charge': new_service,
                        'changed_by': self.env.user.id,
                        'reason': 'تغيير تلقائي عبر النموذج',
                    })

        if needs_version_sync and not self.env.context.get('_bypass_version_sync'):
            for r in self:
                r._get_or_create_active_version()

        return res

    def action_sync_lines_with_template(self):
        # البحث عن المنتجات الافتراضية
        Product = self.env['product.product']
        kwh_product = (
            self.env.ref('utility_core.utility_product_kwh', raise_if_not_found=False)
            or Product.search([('type', '=', 'service')], limit=1)
        )
        service_product = (
            self.env.ref('utility_core.utility_product_service_charge', raise_if_not_found=False)
            or Product.search([('type', '=', 'service')], limit=1)
        )
        discount_product = (
            self.env.ref('utility_core.utility_product_discount', raise_if_not_found=False)
            or Product.search([('name', 'like', 'خصم')], limit=1)
            or service_product
        )

        if not kwh_product:
            raise ValidationError(
                'لا يوجد منتج kWh محدد. المسار: '
                'utility_core.utility_product_kwh أو أي منتج خدمة.'
            )

        for template in self:
            existing_types = template.line_ids.mapped('meter_line_type')

            # مزامنة أو إنشاء بند الاستهلاك
            if 'consumption' not in existing_types and template.price_per_kwh > 0:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 10,
                    'product_id': kwh_product.id if kwh_product else False,
                    'name': 'استهلاك كهرباء',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'consumption',
                    'specific_price': template.price_per_kwh,
                })

            # مزامنة أو إنشاء بند رسم الخدمة الثابت
            if 'service_charge' not in existing_types and template.service_charge > 0:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 25,
                    'product_id': service_product.id if service_product else False,
                    'name': 'رسوم خدمات إضافية',
                    'price_type': 'fixed',
                    'meter_line_type': 'service_charge',
                    'specific_price': template.service_charge,
                })

            # المعلم
            if 'mu_allim' not in existing_types and template.local_fee_mu_allim > 0:
                mu_allim_prod = template.company_id.mu_allim_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 30,
                    'product_id': mu_allim_prod.id,
                    'name': 'رسم المعلم',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'mu_allim',
                    'specific_price': template.local_fee_mu_allim,
                })

            # النظافة
            if 'cleaning' not in existing_types and template.local_fee_cleaning > 0:
                cleaning_prod = template.company_id.cleaning_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 35,
                    'product_id': cleaning_prod.id,
                    'name': 'رسم النظافة',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'cleaning',
                    'specific_price': template.local_fee_cleaning,
                })

            # المجالس المحلية
            if 'municipality' not in existing_types and template.local_fee_per_kwh > 0:
                muni_prod = template.company_id.local_fee_product_id or service_product
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 40,
                    'product_id': muni_prod.id,
                    'name': 'رسم المجالس المحلية',
                    'price_type': 'meter_reading',
                    'meter_line_type': 'municipality',
                    'specific_price': template.local_fee_per_kwh,
                })

            # الخصم المدعوم
            if template.subsidy_enabled and 'discount' not in existing_types and template.discount_formula_id:
                self.env['utility.contract.template.line'].create({
                    'template_id': template.id,
                    'sequence': 45,
                    'product_id': discount_product.id if discount_product else False,
                    'name': 'خصم استهلاك مدعوم',
                    'price_type': 'fixed',
                    'meter_line_type': 'discount',
                    'qty_formula_id': template.discount_formula_id.id,
                    'is_subsidized': True,
                    'specific_price': 0.0,
                })

            # تحديث الأسعار للبنود الحالية لتتطابق تماماً مع بيانات القالب
            for line in template.line_ids:
                if line.meter_line_type == 'consumption':
                    line.specific_price = template.price_per_kwh
                elif line.meter_line_type in ('fixed_fee', 'service_charge'):
                    line.specific_price = template.service_charge
                elif line.meter_line_type == 'mu_allim':
                    line.specific_price = template.local_fee_mu_allim
                elif line.meter_line_type == 'cleaning':
                    line.specific_price = template.local_fee_cleaning
                elif line.meter_line_type == 'municipality':
                    line.specific_price = template.local_fee_per_kwh
                elif line.meter_line_type == 'discount':
                    if template.discount_formula_id:
                        line.qty_formula_id = template.discount_formula_id.id
                        line.specific_price = 0.0

        if len(self) == 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def action_create_biweekly_blocks(self):
        """إنشاء الشرائح الثمانية النموذجية لقالب العقد الحالي"""
        blocks_data = [
            {'sequence': 10, 'name': 'الشريحة الأولى (0-2,999)', 'from_kwh': 0, 'to_kwh': 3000, 'price_per_kwh': 230, 'is_discount': False},
            {'sequence': 20, 'name': 'الشريحة الثانية (3,000-9,999)', 'from_kwh': 3000, 'to_kwh': 10000, 'price_per_kwh': 220, 'is_discount': False},
            {'sequence': 30, 'name': 'الشريحة الثالثة (10,000-19,999)', 'from_kwh': 10000, 'to_kwh': 20000, 'price_per_kwh': 200, 'is_discount': False},
            {'sequence': 40, 'name': 'الشريحة الرابعة (20,000-29,999)', 'from_kwh': 20000, 'to_kwh': 30000, 'price_per_kwh': 190, 'is_discount': False},
            {'sequence': 50, 'name': 'الشريحة الخامسة (30,000-99,999)', 'from_kwh': 30000, 'to_kwh': 100000, 'price_per_kwh': 185, 'is_discount': False},
            {'sequence': 60, 'name': 'الشريحة السادسة (100,000-199,999)', 'from_kwh': 100000, 'to_kwh': 200000, 'price_per_kwh': 180, 'is_discount': False},
            {'sequence': 70, 'name': 'الشريحة السابعة (200,000-299,999)', 'from_kwh': 200000, 'to_kwh': 300000, 'price_per_kwh': 175, 'is_discount': False},
            {'sequence': 80, 'name': 'الشريحة الثامنة (300,000+)', 'from_kwh': 300000, 'to_kwh': 0, 'price_per_kwh': 170, 'is_discount': False},
        ]
        ctx = dict(self.env.context, skip_tier_validation=True)
        Block = self.env['utility.contract.template.block']
        for template in self:
            # حذف الشرائح الحالية بشكل صريح مع تجاوز التحقق المؤقت
            existing = Block.with_context(ctx).search([
                ('template_id', '=', template.id),
                ('is_discount', '=', False),
            ])
            existing.with_context(ctx).unlink()
            # إنشاء الشرائح الثمانية الجديدة
            new_blocks = [{**b, 'template_id': template.id} for b in blocks_data]
            Block.with_context(ctx).create(new_blocks)
            # التحقق النهائي الصارم بعد اكتمال العملية
            template._validate_contract_template_tiers()
        
        if len(self) == 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def action_view_versions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('إصدارات قالب العقد: %s') % self.name,
            'res_model': 'utility.contract.template.version',
            'view_mode': 'tree,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id, 'create': False, 'delete': False},
        }

    def action_open_clone_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('استنساخ كقالب جديد (Create From Existing Template)'),
            'res_model': 'utility.contract.template.clone.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_template_id': self.id,
                'default_new_name': _('%s (نسخة)') % self.name,
                'default_new_code': f"{self.code or 'CT'}_COPY",
                'default_target_scope': self.scope,
                'default_target_region_ids': [(6, 0, self.region_ids.ids)],
                'default_target_area_ids': [(6, 0, self.area_ids.ids)],
            },
        }


class UtilityContractTemplateLine(models.Model):
    _name = 'utility.contract.template.line'
    _description = 'بند قالب العقد'
    _rec_name = 'name'
    _order = 'sequence'

    template_id = fields.Many2one('utility.contract.template', 'قالب العقد', required=True, ondelete='cascade')
    sequence = fields.Integer('التسلسل', default=10)

    product_id = fields.Many2one('product.product', 'المنتج', required=True)
    name = fields.Text(string='الوصف', translate=True)

    quantity = fields.Float('الكمية', default=1.0)
    uom_id = fields.Many2one('uom.uom', 'وحدة القياس')

    price_type = fields.Selection([
        ('fixed', 'سعر ثابت'),
        ('meter_reading', 'حسب قراءة العداد'),
    ], default='fixed', required=True)

    currency_id = fields.Many2one(
        'res.currency',
        related='template_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    specific_price = fields.Monetary('السعر المحدد', currency_field='currency_id')

    # تصنيف البند للفوترة
    meter_line_type = fields.Selection([
        ('consumption', 'الاستهلاك'),
        ('service_charge', 'رسم خدمة ثابت'),
        ('fixed_fee', 'رسم ثابت (قديم)'),
        ('mu_allim', 'رسم المعلم'),
        ('cleaning', 'رسم النظافة'),
        ('municipality', 'رسم المجلس المحلي'),
        ('discount', 'خصم'),
    ], string='نوع بند العداد')

    # الربط مع معادلات محرك الاحتساب
    qty_formula_id = fields.Many2one('utility.formula', 'معادلة الكمية',
        help='معادلة ديناميكية تحسب الكمية تلقائياً (متغيرات: الاستهلاك، قالب العقد، الحساب، الفئة)')
    is_subsidized = fields.Boolean('خصم مدعوم',
        help='يطبق الخصم حسب فئة المشترك — يعمل فقط مع نوع بند العداد = خصم')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('_bypass_version_sync'):
            for t in records.mapped('template_id'):
                t._get_or_create_active_version()
        return records

    def write(self, vals):
        templates = self.mapped('template_id')
        res = super().write(vals)
        if not self.env.context.get('_bypass_version_sync'):
            for t in (templates | self.mapped('template_id')):
                t._get_or_create_active_version()
        return res

    def unlink(self):
        templates = self.mapped('template_id')
        res = super().unlink()
        if not self.env.context.get('_bypass_version_sync'):
            for t in templates:
                t._get_or_create_active_version()
        return res
