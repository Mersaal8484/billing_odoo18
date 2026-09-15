from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    legacy_single_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', related='company_id.legacy_single_phase_meter_model_id',
        readonly=False, string='موديل العداد القديم — أحادي الطور',
        domain=[('phase', '=', 'single')])
    legacy_three_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', related='company_id.legacy_three_phase_meter_model_id',
        readonly=False, string='موديل العداد القديم — ثلاثي الطور',
        domain=[('phase', '=', 'three')])

    pos_epson_printer_ip = fields.Char(
        string='عنوان IP طابعة Epson',
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        readonly=True,
    )

    group_display_incoterm = fields.Boolean(
        string='شروط التجارة الدولية (Incoterms)',
        implied_group='account.group_delivery_invoice_address',
    )
    default_picking_policy = fields.Selection([
        ('direct', 'تسليم كل منتج عند توفره'),
        ('one', 'تسليم جميع المنتجات دفعة واحدة'),
    ], string='سياسة الشحن والتوصيل', default='direct', default_model='sale.order')
    use_security_lead = fields.Boolean(
        string='مهلة الأمان للتسليم',
        config_parameter='sale.use_security_lead',
    )
    security_lead = fields.Float(
        string='مهلة أمان التسليم بالأيام',
        config_parameter='sale.security_lead',
    )
    group_stock_packaging = fields.Boolean(
        string='التعبئة والتغليف للمخزون',
        implied_group='product.group_stock_packaging',
    )
    group_discount_per_so_line = fields.Boolean(
        string='خصومات بنود أوامر البيع',
        implied_group='product.group_discount_per_so_line',
    )
    module_delivery = fields.Boolean(
        string='طرق التوصيل والشحن',
    )

    # --- Meter Reading ---
    meter_review_required = fields.Boolean(
        string='مطلوب مراجعة صورة العداد',
        config_parameter='utility.meter_review_required',
        default=True)
    meter_image_mandatory = fields.Boolean(
        string='صورة العداد إلزامية',
        config_parameter='utility.meter_image_mandatory',
        default=False)
    meter_reading_validation = fields.Selection([
        ('none', 'بدون تحقق'),
        ('consumption_diff', 'التحقق من فرق الاستهلاك'),
        ('image_review', 'مراجعة الصورة'),
        ('both', 'كلاهما'),
    ], string='نوع التحقق من القراءة',
       config_parameter='utility.meter_reading_validation',
       default='both')

    # --- Transformer ---
    max_transformer_loss_tolerance = fields.Float(
        string='نسبة الفاقد المسموح في المحولات (%)',
        config_parameter='utility.max_transformer_loss_tolerance',
        default=10.0)

    # --- Consumption Alerts ---
    high_consumption_threshold = fields.Float(
        string='حد الاستهلاك العالي (kWh)',
        config_parameter='utility.high_consumption_threshold',
        default=10000.0)
    consumption_variation_alert_percentage = fields.Float(
        string='نسبة التغير المنبهة للاستهلاك (%)',
        config_parameter='utility.consumption_variation_alert_percentage',
        default=50.0)

    # --- SMS / Notifications ---
    stock_move_sms_validation = fields.Boolean(
        string='تأكيد رسائل SMS لحركات المخزون',
        config_parameter='utility.stock_move_sms_validation',
        default=False)
    stock_sms_confirmation_template_id = fields.Many2one(
        'sms.template',
        string='قالب رسائل SMS لتأكيد المخزون',
        config_parameter='utility.stock_sms_confirmation_template_id')
    send_sms_on_invoice = fields.Boolean(
        string='إرسال SMS عند إنشاء الفاتورة',
        config_parameter='utility.send_sms_on_invoice',
        default=False)
    send_sms_on_payment = fields.Boolean(
        string='إرسال SMS عند الدفع',
        config_parameter='utility.send_sms_on_payment',
        default=False)
    send_sms_on_overdue = fields.Boolean(
        string='إرسال SMS عند تأخر الفاتورة',
        config_parameter='utility.send_sms_on_overdue',
        default=False)

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        related='company_id.fine_account_id',
        readonly=False,
        string='حساب إيرادات الغرامات')
    discount_account_id = fields.Many2one(
        'account.account',
        related='company_id.discount_account_id',
        readonly=False,
        string='حساب الخصومات / الإعفاءات')
    deposit_account_id = fields.Many2one(
        'account.account',
        related='company_id.deposit_account_id',
        readonly=False,
        string='حساب التأمينات')
    settlement_account_id = fields.Many2one(
        'account.account',
        related='company_id.settlement_account_id',
        readonly=False,
        string='حساب التسويات المالية')
    writeoff_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.writeoff_journal_id',
        readonly=False,
        string='يومية الإعفاءات')
    deposit_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.deposit_journal_id',
        readonly=False,
        string='يومية التأمينات والودائع')
    settlement_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.settlement_journal_id',
        readonly=False,
        string='يومية التسويات')
    opening_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.opening_journal_id',
        readonly=False,
        string='يومية الأرصدة الافتتاحية')
    opening_clearing_account_id = fields.Many2one(
        'account.account',
        related='company_id.opening_clearing_account_id',
        readonly=False,
        string='حساب مقابلة الأرصدة الافتتاحية')
    penalty_product_id = fields.Many2one(
        'product.product',
        related='company_id.penalty_product_id',
        readonly=False,
        string='منتج الغرامات')
    mu_allim_product_id = fields.Many2one(
        'product.product',
        related='company_id.mu_allim_product_id',
        readonly=False,
        string='منتج المعلم')
    cleaning_product_id = fields.Many2one(
        'product.product',
        related='company_id.cleaning_product_id',
        readonly=False,
        string='منتج النظافة')
    local_fee_product_id = fields.Many2one(
        'product.product',
        related='company_id.local_fee_product_id',
        readonly=False,
        string='منتج المجالس المحلية')
    writeoff_account_id = fields.Many2one(
        'account.account',
        related='company_id.writeoff_account_id',
        readonly=False,
        string='حساب الإعفاءات')
    collection_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.collection_journal_id',
        readonly=False,
        string='يومية التحصيل الافتراضية')
    sales_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.sales_journal_id',
        readonly=False,
        string='يومية مبيعات الكهرباء')
    electricity_income_account_id = fields.Many2one(
        'account.account',
        related='company_id.electricity_income_account_id',
        readonly=False,
        string='حساب إيرادات مبيعات الكهرباء')
    electricity_product_id = fields.Many2one(
        'product.product',
        related='company_id.electricity_product_id',
        readonly=False,
        string='منتج طاقة الكهرباء الرئيسي')
    discount_product_id = fields.Many2one(
        'product.product',
        related='company_id.discount_product_id',
        readonly=False,
        string='منتج الخصم والإعفاءات')
    private_transformer_fee_product_id = fields.Many2one(
        'product.product',
        related='company_id.private_transformer_fee_product_id',
        readonly=False,
        string='منتج رسوم المحول الخاص')

    # --- Infrastructure Settings (إعدادات البنية التحتية — مسارات العمل والوسائط) ---
    workflow_backend = fields.Selection([
        ('local', 'Local Odoo (In-Process Outbox)'),
        ('temporal', 'Temporal Workflow Service'),
    ], string='مُحَوِّل مسارات العمل (Workflow Backend)',
       config_parameter='utility.workflow_adapter',
       default='local', required=True)

    media_backend = fields.Selection([
        ('attachment', 'Odoo Attachments (Database/Filestore)'),
        ('filesystem', 'Local Shared Filesystem'),
        ('s3', 'S3 Compatible Cloud Storage'),
    ], string='مُحَوِّل الوسائط والصور (Media Backend)',
       config_parameter='utility.media_backend',
       default='attachment', required=True)

    # إعدادات Temporal
    temporal_target_host = fields.Char(
        string='عنوان خادم Temporal Host',
        config_parameter='utility.temporal_target_host',
        default='localhost:7233')
    temporal_namespace = fields.Char(
        string='نطاق Temporal Namespace',
        config_parameter='utility.temporal_namespace',
        default='default')

    # إعدادات Filesystem
    filesystem_storage_path = fields.Char(
        string='مسار تخزين الملفات (Filesystem Path)',
        config_parameter='utility.filesystem_storage_path')

    # إعدادات S3
    s3_endpoint_url = fields.Char(
        string='رابط خادم S3 Endpoint URL',
        config_parameter='utility.s3_endpoint_url')
    s3_bucket_name = fields.Char(
        string='اسم الحاوية S3 Bucket Name',
        config_parameter='utility.s3_bucket_name')
    s3_access_key = fields.Char(
        string='مفتاح الوصول S3 Access Key',
        config_parameter='utility.s3_access_key')
    s3_secret_key = fields.Char(
        string='المفتاح السري S3 Secret Key',
        config_parameter='utility.s3_secret_key')
    s3_region_name = fields.Char(
        string='المنطقة S3 Region',
        config_parameter='utility.s3_region_name',
        default='us-east-1')

    @api.constrains('workflow_backend', 'temporal_target_host', 'media_backend', 'filesystem_storage_path', 's3_endpoint_url', 's3_bucket_name', 's3_access_key', 's3_secret_key')
    def _check_infrastructure_backend_config(self):
        for rec in self:
            if rec.workflow_backend == 'temporal':
                raise ValidationError(_("مُحَوِّل Temporal Workflow حاليًا في مرحلة العقد الأولي (Placeholder Contract) وغير جاهز للإنتاج. يُرجى اختيار Local Odoo (In-Process Outbox)."))

            if rec.media_backend == 's3':
                raise ValidationError(_("مُحَوِّل S3 Cloud Storage حاليًا في مرحلة العقد الأولي (Placeholder Contract) وغير جاهز للإنتاج. يُرجى اختيار Odoo Attachments أو Local Shared Filesystem."))

            if rec.media_backend == 'filesystem' and not rec.filesystem_storage_path:
                raise ValidationError(_("عند اختيار Filesystem يجب تحديد مسار تخزين الملفات."))

    def action_populate_missing_defaults(self):
        """فحص وتوليد الإعدادات الافتراضية والحسابات والمنتجات وموديلات العدادات الناقصة للشركة."""
        self.ensure_one()
        company = self.company_id or self.env.company
        product_obj = self.env['product.product']
        journal_obj = self.env['account.journal']
        account_obj = self.env['account.account']
        model_obj = self.env['utility.meter.model']

        # Helper to get or create product
        def _get_or_create_product(field_name, name, xml_ref=None):
            if getattr(company, field_name):
                return getattr(company, field_name)
            prod = False
            if xml_ref:
                rec = self.env.ref(xml_ref, raise_if_not_found=False)
                if rec and (not getattr(rec, 'company_id', False) or rec.company_id == company):
                    prod = rec
            if not prod:
                prod = product_obj.search([('name', '=', name)], limit=1)
            if not prod:
                prod = product_obj.create({
                    'name': name,
                    'type': 'service',
                    'lst_price': 0.0,
                })
            setattr(company, field_name, prod)
            return prod

        # Helper to get or create journal
        def _get_or_create_journal(field_name, default_code, name, jtype, xml_ref=None):
            if getattr(company, field_name):
                return getattr(company, field_name)
            j = False
            if xml_ref:
                rec = self.env.ref(xml_ref, raise_if_not_found=False)
                if rec and (not getattr(rec, 'company_id', False) or rec.company_id == company):
                    j = rec
            if not j:
                j = journal_obj.search([
                    ('code', '=', default_code),
                    ('company_id', 'in', (company.id, False))
                ], limit=1)
            if not j:
                j = journal_obj.search([
                    ('type', '=', jtype),
                    ('name', 'ilike', name),
                    ('company_id', 'in', (company.id, False))
                ], limit=1)
            if not j:
                j = journal_obj.search([
                    ('type', '=', jtype),
                    ('company_id', 'in', (company.id, False))
                ], limit=1)
            if not j:
                code = default_code
                suffix = 1
                while journal_obj.search([('code', '=', code), ('company_id', 'in', (company.id, False))], limit=1):
                    code = f"{default_code[:3]}{suffix}"
                    suffix += 1
                j = journal_obj.create({
                    'name': name,
                    'code': code,
                    'type': jtype,
                    'company_id': company.id,
                })
            setattr(company, field_name, j)
            return j

        # Helper to get or create account
        def _get_or_create_account(field_name, default_code, name, acc_type, xml_ref=None, search_domain=None):
            if getattr(company, field_name):
                return getattr(company, field_name)
            acc = False
            if xml_ref:
                rec = self.env.ref(xml_ref, raise_if_not_found=False)
                if rec and (not getattr(rec, 'company_id', False) or rec.company_id == company):
                    acc = rec
            if not acc and search_domain:
                acc = account_obj.search([
                    ('company_id', 'in', (company.id, False)),
                    ('deprecated', '=', False)
                ] + search_domain, limit=1)
            if not acc:
                acc = account_obj.search([
                    ('code', '=', default_code),
                    ('company_id', 'in', (company.id, False)),
                    ('deprecated', '=', False)
                ], limit=1)
            if not acc:
                acc = account_obj.search([
                    ('name', 'ilike', name),
                    ('company_id', 'in', (company.id, False)),
                    ('deprecated', '=', False)
                ], limit=1)
            if not acc and acc_type:
                acc = account_obj.search([
                    ('account_type', '=', acc_type),
                    ('company_id', 'in', (company.id, False)),
                    ('deprecated', '=', False)
                ], limit=1)
            if not acc:
                code = default_code
                suffix = 1
                while account_obj.search([('code', '=', code), ('company_id', 'in', (company.id, False))], limit=1):
                    code = f"{default_code[:5]}{suffix}"
                    suffix += 1
                acc = account_obj.create({
                    'name': name,
                    'code': code,
                    'account_type': acc_type,
                    'company_id': company.id,
                })
            setattr(company, field_name, acc)
            return acc

        # 1. Products (المنتجات)
        _get_or_create_product('electricity_product_id', 'طاقة الكهرباء الرئيسية', 'utility_core.utility_product_consumption')
        _get_or_create_product('discount_product_id', 'خصم وإعفاءات الكهرباء', 'utility_core.utility_product_discount')
        _get_or_create_product('penalty_product_id', 'غرامة تأخير / مخالفة', 'utility_core.utility_product_penalty')
        _get_or_create_product('mu_allim_product_id', 'رسم المعلم', 'utility_core.utility_product_mu_allim')
        _get_or_create_product('cleaning_product_id', 'رسم النظافة', 'utility_core.utility_product_cleaning')
        _get_or_create_product('local_fee_product_id', 'رسم المجالس المحلية', 'utility_core.utility_product_municipality')
        _get_or_create_product('private_transformer_fee_product_id', 'رسوم المحول الخاص', 'utility_core.utility_product_private_transformer_fee')

        # 2. Journals (اليوميات)
        _get_or_create_journal('sales_journal_id', 'UBILL', 'يومية مبيعات الكهرباء (فواتير المشتركين)', 'sale', 'utility_core.journal_utility_sales')
        _get_or_create_journal('collection_journal_id', 'CSH1', 'يومية التحصيل الافتراضية', 'cash')
        _get_or_create_journal('opening_journal_id', 'UOPEN', 'يومية الأرصدة الافتتاحية', 'general', 'utility_core.journal_opening_balance')
        _get_or_create_journal('writeoff_journal_id', 'WRT', 'يومية الإعفاءات والتسويات', 'general')
        _get_or_create_journal('deposit_journal_id', 'DEP', 'يومية التأمينات والودائع', 'general')
        _get_or_create_journal('settlement_journal_id', 'SETTL', 'يومية التسويات المالية', 'general')

        # 3. Accounts (الحسابات)
        _get_or_create_account('electricity_income_account_id', '400099', 'إيرادات مبيعات استهلاك الكهرباء', 'income', 'utility_core.account_income_electricity')
        _get_or_create_account('fine_account_id', '410001', 'إيرادات الغرامات', 'income', 'utility_core.demo_account_fine')
        _get_or_create_account('discount_account_id', '490099', 'خصومات وإعفاءات استهلاك الكهرباء', 'income', 'utility_core.account_discount_utility', search_domain=[('account_type', 'in', ('expense', 'income'))])
        _get_or_create_account('deposit_account_id', '210001', 'حساب التأمينات والودائع', 'liability_current', 'utility_core.demo_account_deposit', search_domain=[('account_type', 'ilike', 'liability')])
        _get_or_create_account('settlement_account_id', '410002', 'حساب التسويات المالية', 'income_other', 'utility_core.demo_account_settlement')
        _get_or_create_account('writeoff_account_id', '420002', 'حساب الإعفاءات والديون المعدومة', 'expense', search_domain=[('account_type', '=', 'expense')])
        _get_or_create_account('opening_clearing_account_id', '999999', 'حساب مقابلة الأرصدة الافتتاحية', 'equity', search_domain=[
            '|', ('code', 'in', ('999999', '300000', '399999')),
            '|', ('name', 'ilike', 'افتتاح'),
            ('account_type', '=', 'equity')
        ])

        # 4. Legacy Meter Models (موديلات العدادات)
        if not company.legacy_single_phase_meter_model_id:
            m1 = model_obj.search([('phase', '=', 'single')], limit=1)
            if not m1:
                m1 = model_obj.create({
                    'name': 'عداد أحادي افتراضي',
                    'code': 'MDL-1P-DEF',
                    'phase': 'single',
                })
            company.legacy_single_phase_meter_model_id = m1

        if not company.legacy_three_phase_meter_model_id:
            m3 = model_obj.search([('phase', '=', 'three')], limit=1)
            if not m3:
                m3 = model_obj.create({
                    'name': 'عداد ثلاثي افتراضي',
                    'code': 'MDL-3P-DEF',
                    'phase': 'three',
                })
            company.legacy_three_phase_meter_model_id = m3

        # 5. Currency & Country (العملة: الريال اليمني YER والدولة: اليمن)
        yer_curr = self.env.ref('base.YER', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'YER')], limit=1)
        if yer_curr:
            if not yer_curr.active:
                yer_curr.active = True
            if company.currency_id != yer_curr:
                has_moves = self.env['account.move.line'].search_count([('company_id', '=', company.id)]) > 0
                if not has_moves:
                    company.currency_id = yer_curr

        country_ye = self.env.ref('base.ye', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'YE')], limit=1)
        if country_ye and not company.country_id:
            company.country_id = country_ye

        # 6. Sync populated values back to current in-memory settings view
        fields_to_sync = [
            'electricity_product_id', 'discount_product_id', 'penalty_product_id',
            'mu_allim_product_id', 'cleaning_product_id', 'local_fee_product_id',
            'private_transformer_fee_product_id',
            'sales_journal_id', 'collection_journal_id', 'opening_journal_id',
            'writeoff_journal_id', 'deposit_journal_id', 'settlement_journal_id',
            'electricity_income_account_id', 'fine_account_id', 'discount_account_id',
            'deposit_account_id', 'settlement_account_id', 'writeoff_account_id',
            'opening_clearing_account_id',
            'legacy_single_phase_meter_model_id', 'legacy_three_phase_meter_model_id',
            'currency_id',
        ]
        for fname in fields_to_sync:
            if hasattr(self, fname) and hasattr(company, fname):
                val = getattr(company, fname)
                if val:
                    self[fname] = val

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('توليد البيانات الافتراضية'),
                'message': _('تم فحص وتوليد الحسابات واليوميات والمنتجات والعملة (الريال اليمني) وموديلات العدادات بنجاح!'),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'}
            }
        }
