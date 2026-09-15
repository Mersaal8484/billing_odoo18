from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    legacy_single_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', string='موديل العداد القديم — أحادي الطور',
        domain=[('phase', '=', 'single')],
        check_company=False)
    legacy_three_phase_meter_model_id = fields.Many2one(
        'utility.meter.model', string='موديل العداد القديم — ثلاثي الطور',
        domain=[('phase', '=', 'three')],
        check_company=False)

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        string='حساب إيرادات الغرامات',
        check_company=True)
    discount_account_id = fields.Many2one(
        'account.account',
        string='حساب الخصومات / الإعفاءات',
        check_company=True)
    deposit_account_id = fields.Many2one(
        'account.account',
        string='حساب التأمينات',
        check_company=True)
    settlement_account_id = fields.Many2one(
        'account.account',
        string='حساب التسويات المالية',
        check_company=True)
    
    writeoff_journal_id = fields.Many2one(
        'account.journal',
        string='يومية الإعفاءات',
        check_company=True)
    deposit_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التأمينات والودائع',
        check_company=True)
    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التسويات',
        check_company=True)
    opening_journal_id = fields.Many2one(
        'account.journal',
        string='يومية الأرصدة الافتتاحية',
        domain="[('type', '=', 'general')]",
        check_company=True)
    opening_clearing_account_id = fields.Many2one(
        'account.account',
        string='حساب مقابلة الأرصدة الافتتاحية',
        domain="[('deprecated', '=', False)]",
        check_company=True,
        help='الحساب المقابل لقيد الرصيد الافتتاحي. يجب إعداده مسبقاً؛ لا ينشئ النظام حسابات تلقائياً.')
    
    penalty_product_id = fields.Many2one(
        'product.product',
        string='منتج الغرامات',
        check_company=True)
    mu_allim_product_id = fields.Many2one(
        'product.product',
        string='منتج المعلم',
        check_company=True)
    cleaning_product_id = fields.Many2one(
        'product.product',
        string='منتج النظافة',
        check_company=True)
    local_fee_product_id = fields.Many2one(
        'product.product',
        string='منتج المجالس المحلية',
        check_company=True)

    writeoff_account_id = fields.Many2one(
        'account.account',
        string='حساب الإعفاءات',
        check_company=True)
    collection_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التحصيل الافتراضية',
        check_company=True)
    collector_receivable_account_id = fields.Many2one('account.account', string='حساب ذمم المحصلين', check_company=True)
    collection_clearing_account_id = fields.Many2one('account.account', string='حساب مقاصة التحصيل', check_company=True)
    deposit_clearing_account_id = fields.Many2one('account.account', string='حساب مقاصة الإيداع البنكي', check_company=True)
    collection_surplus_account_id = fields.Many2one('account.account', string='حساب فائض التحصيل', check_company=True)

    sales_journal_id = fields.Many2one(
        'account.journal',
        string='يومية مبيعات الكهرباء',
        domain="[('type', '=', 'sale')]",
        check_company=True)
    electricity_income_account_id = fields.Many2one(
        'account.account',
        string='حساب إيرادات مبيعات الكهرباء',
        check_company=True)
    electricity_product_id = fields.Many2one(
        'product.product',
        string='منتج طاقة الكهرباء الرئيسي',
        check_company=True)
    discount_product_id = fields.Many2one(
        'product.product',
        string='منتج الخصم والإعفاءات',
        check_company=True)
    private_transformer_fee_product_id = fields.Many2one(
        'product.product',
        string='منتج رسوم المحول الخاص',
        check_company=True)

    @api.model
    def _init_utility_company_defaults(self):
        """Auto-configure default fee products and journals on company if not set."""
        companies = self.search([])
        for company in companies:
            vals = {}
            def is_compat(rec):
                return rec and (not getattr(rec, 'company_id', False) or rec.company_id == company)

            if not company.opening_journal_id:
                j_open = self.env.ref('utility_core.journal_opening_balance', raise_if_not_found=False)
                if is_compat(j_open):
                    vals['opening_journal_id'] = j_open.id
            if not company.opening_clearing_account_id:
                acc_open = self.env['account.account'].search([
                    ('company_id', 'in', (company.id, False)),
                    ('deprecated', '=', False),
                    '|', ('code', 'in', ('999999', '300000', '399999')),
                    '|', ('name', 'ilike', 'افتتاح'),
                    ('account_type', '=', 'equity')
                ], limit=1)
                if acc_open:
                    vals['opening_clearing_account_id'] = acc_open.id
            if not company.sales_journal_id:
                j_sale = self.env.ref('utility_core.journal_utility_sales', raise_if_not_found=False)
                if is_compat(j_sale):
                    vals['sales_journal_id'] = j_sale.id
            if not company.electricity_income_account_id:
                acc = self.env.ref('utility_core.account_income_electricity', raise_if_not_found=False)
                if is_compat(acc):
                    vals['electricity_income_account_id'] = acc.id
            if not company.electricity_product_id:
                prod = self.env.ref('utility_core.utility_product_consumption', raise_if_not_found=False)
                if is_compat(prod):
                    vals['electricity_product_id'] = prod.id
            if not company.discount_account_id:
                acc = self.env.ref('utility_core.account_discount_utility', raise_if_not_found=False)
                if is_compat(acc):
                    vals['discount_account_id'] = acc.id
            if not company.discount_product_id:
                prod = self.env.ref('utility_core.utility_product_discount', raise_if_not_found=False)
                if is_compat(prod):
                    vals['discount_product_id'] = prod.id
            if not company.mu_allim_product_id:
                prod = self.env.ref('utility_core.utility_product_mu_allim', raise_if_not_found=False)
                if is_compat(prod):
                    vals['mu_allim_product_id'] = prod.id
            if not company.cleaning_product_id:
                prod = self.env.ref('utility_core.utility_product_cleaning', raise_if_not_found=False)
                if is_compat(prod):
                    vals['cleaning_product_id'] = prod.id
            if not company.local_fee_product_id:
                prod = self.env.ref('utility_core.utility_product_municipality', raise_if_not_found=False)
                if is_compat(prod):
                    vals['local_fee_product_id'] = prod.id
            if not company.private_transformer_fee_product_id:
                prod = self.env.ref('utility_core.utility_product_private_transformer_fee', raise_if_not_found=False)
                if is_compat(prod):
                    vals['private_transformer_fee_product_id'] = prod.id

            if not company.account_journal_payment_debit_account_id or not company.account_journal_payment_credit_account_id:
                outstanding_acc = self.env['account.account'].search([
                    ('name', 'ilike', 'مستحق'),
                    ('company_id', 'in', (company.id, False))
                ], limit=1) or self.env['account.account'].search([
                    ('account_type', 'in', ('asset_current', 'asset_cash')),
                    ('company_id', 'in', (company.id, False))
                ], limit=1)
                if not outstanding_acc:
                    outstanding_acc = self.env['account.account'].create({
                        'name': 'حساب الإيصالات والدفعات المستحقة',
                        'code': '101200',
                        'account_type': 'asset_current',
                        'company_id': company.id,
                    })
                if not company.account_journal_payment_debit_account_id:
                    vals['account_journal_payment_debit_account_id'] = outstanding_acc.id
                if not company.account_journal_payment_credit_account_id:
                    vals['account_journal_payment_credit_account_id'] = outstanding_acc.id

            # تفعيل عملة الريال اليمني وتعيينها للشركة
            yer = self.env.ref('base.YER', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'YER')], limit=1)
            if yer:
                if not yer.active:
                    yer.active = True
                if company.currency_id != yer:
                    has_moves = self.env['account.move.line'].search_count([('company_id', '=', company.id)]) > 0
                    if not has_moves:
                        vals['currency_id'] = yer.id
            country_ye = self.env.ref('base.ye', raise_if_not_found=False) or self.env['res.country'].search([('code', '=', 'YE')], limit=1)
            if country_ye and not company.country_id:
                vals['country_id'] = country_ye.id

            if vals:
                company.write(vals)

        # ضمان منح صلاحيات مدير النظام للكهرباء لمستخدمي Admin تلقائياً
        admin_group = self.env.ref('utility_core.group_utility_admin', raise_if_not_found=False)
        if admin_group:
            admin_users = self.env['res.users'].sudo().search([
                '|', ('id', '=', 2),
                '|', ('groups_id', 'in', [self.env.ref('base.group_system').id]),
                ('groups_id', 'in', [self.env.ref('base.group_erp_manager').id])
            ])
            if admin_users:
                admin_group.sudo().write({'users': [(4, u.id) for u in admin_users]})
