from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrderType(models.Model):
    _name = 'sale.order.type'
    _description = 'نوع أمر البيع'
    _order = 'sequence'

    name = fields.Char(string='الاسم', required=True, translate=True)
    code = fields.Char(string='الرمز')
    active = fields.Boolean(string='نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)

    description = fields.Text(string='الوصف', translate=True)
    sequence_id = fields.Many2one('ir.sequence', string='تسلسل القيود', copy=False)
    journal_id = fields.Many2one('account.journal', string='يومية الفوترة', domain="[('type', '=', 'sale')]")
    warehouse_id = fields.Many2one('stock.warehouse', string='المستودع')
    picking_policy = fields.Selection([
        ('direct', 'تسليم كل منتج عند توفره'),
        ('one', 'تسليم جميع المنتجات دفعة واحدة'),
    ], string='سياسة الشحن', default='direct')
    payment_term_id = fields.Many2one('account.payment.term', string='شروط الدفع')
    pricelist_id = fields.Many2one('product.pricelist', string='قائمة الأسعار')
    incoterm_id = fields.Many2one('account.incoterms', string='الإنكوتيرمز')
    sequence = fields.Integer('التسلسل', default=10)
    rule_ids = fields.One2many('sale.order.type.rule', 'order_type_id', string='القواعد', copy=True)

    def matches_order(self, order):
        self.ensure_one()
        return any(rule.matches_order(order) for rule in self.rule_ids)

    def matches_invoice(self, invoice):
        self.ensure_one()
        return any(rule.matches_invoice(invoice) for rule in self.rule_ids)


class SaleOrderTypeRule(models.Model):
    _name = 'sale.order.type.rule'
    _description = 'قاعدة المطابقة التلقائية لنوع أمر البيع'
    _order = 'sequence'

    name = fields.Char('الاسم', required=True)
    sequence = fields.Integer('التسلسل', default=10)
    order_type_id = fields.Many2one('sale.order.type', string='نوع أمر البيع', ondelete='cascade')
    product_ids = fields.Many2many('product.product', string='المنتجات')
    product_category_ids = fields.Many2many('product.category', string='فئات المنتجات')

    def matches_order(self, order):
        self.ensure_one()
        order_products = order.order_line.mapped('product_id')
        return self.matches_products(order_products) or self.matches_product_categories(order_products.mapped('categ_id'))

    def matches_products(self, products):
        self.ensure_one()
        return self.product_ids and any(p in products for p in self.product_ids)

    def matches_product_categories(self, categories):
        self.ensure_one()
        return self.product_category_ids and any(c in categories for c in self.product_category_ids)

    def matches_invoice(self, invoice):
        self.ensure_one()
        invoice_products = invoice.invoice_line_ids.mapped('product_id')
        return self.matches_products(invoice_products) or self.matches_product_categories(invoice_products.mapped('categ_id'))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_contract = fields.Boolean(string='هل هو عقد اشتراك')
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='قالب عقد الكهرباء',
    )

    @api.onchange('is_contract')
    def _change_is_contract(self):
        if not self.is_contract:
            self.contract_template_id = False


class ResPartnerSector(models.Model):
    _name = 'res.partner.sector'
    _description = 'قطاع المشترك'

    name = fields.Char(string="الاسم", required=True)
    code = fields.Char(string="الرمز")
    active = fields.Boolean(string="نشط", default=True)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    region_id = fields.Many2one('utility.region', string='المنطقة', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='المنطقة الفرعية', domain="[('type', '=', 'area')]")
    zone_id = fields.Many2one('utility.region', string='المنطقة التفصيلية', domain="[('type', '=', 'zone')]")
    utility_postpaid_balance = fields.Monetary(string="مديونية آجل (فواتير)", compute='_compute_utility_balances')
    has_utility_customer = fields.Boolean(string="لديه حساب مشترك", compute='_compute_has_utility_customer')

    def _compute_has_utility_customer(self):
        for partner in self:
            customer = self.env['utility.customer'].search([
                ('partner_id', '=', partner.id),
            ], limit=1)
            partner.has_utility_customer = bool(customer)

    def _compute_utility_balances(self):
        for partner in self:
            customers = self.env['utility.customer'].search([
                ('partner_id', '=', partner.id),
            ])
            if customers:
                ledger_balance = sum(customers.mapped('accounting_balance'))
                # Opening balances are posted receivable lines.  Never add the
                # legacy partner field to accounting truth or double-count it.
                partner.utility_postpaid_balance = ledger_balance
            else:
                partner.utility_postpaid_balance = 0.0

    nickname = fields.Char(string="الاسم المختصر")
    utility_partner_type = fields.Selection([
        ('subscriber', 'مشترك كهرباء'),
        ('employee', 'موظف / مستخدم'),
        ('donor', 'جهة مانحة'),
        ('supported_entity', 'جهة مدعومة'),
        ('other', 'جهة أخرى'),
    ], string='تصنيف الشريك', default='other', required=True, index=True,
        tracking=True,
        help='يحدد الغرض التشغيلي للشريك ويُستخدم لتقييد قوائم الاختيار في النظام.')
    is_subscriber = fields.Boolean(
        string="مشترك كهرباء", default=False, tracking=True,
        help='حقل توافق قديم. التصنيف المعتمد هو تصنيف الشريك.')
    subscriber_status = fields.Selection([
        ('new', 'مشترك جديد'),
        ('old', 'مشترك قديم'),
    ], string="نوع الاشتراك", default='new', tracking=True)
    subscriber_active_status = fields.Selection([
        ('active', 'فعال'),
        ('inactive', 'غير مفعل'),
    ], string="حالة التفعيل", default='active', tracking=True)
    last_payment = fields.Monetary(string="آخر دفعة", compute='_compute_last_payment', store=False)
    last_payment_date = fields.Date(string="تاريخ آخر دفعة", compute='_compute_last_payment', store=False)
    last_invoice = fields.Monetary(string="آخر فاتورة", compute='_compute_last_invoice', store=False)
    last_invoice_date = fields.Date(string="تاريخ آخر فاتورة", compute='_compute_last_invoice', store=False)
    char_code = fields.Char(string="الحرف")
    subscriber_no = fields.Char(string="الرقم الجديد")
    national_id = fields.Char(string="الهوية الوطنية")
    meter_number = fields.Char(string="رقم العداد")
    meter_reading = fields.Integer(string="قراءة العداد في النظام")
    opening_reading = fields.Integer(string="قراءة الافتتاح")
    consumption_difference = fields.Integer(
        string="فرق الاستهلاك", 
        compute="_compute_consumption_difference", 
        store=True
    )
    
    @api.depends('meter_reading', 'opening_reading')
    def _compute_consumption_difference(self):
        for rec in self:
            rec.consumption_difference =   rec.meter_reading - rec.opening_reading

    register_number = fields.Integer(string="رقم السجل")
    open_balance = fields.Monetary(string="الرصيد الافتتاحي (مدين)")
    is_credit_raised = fields.Boolean(string="رصيد مرحل")
    pec_credit = fields.Monetary(string="رصيد مرحل من المؤسسة")
    credit_raise_date = fields.Date(string="تاريخ الترحيل")

    sale_type = fields.Many2one('sale.order.type', string='نوع أمر البيع', company_dependent=True)
    subscriber_id = fields.Many2one('utility.subscriber', string="نوع المشترك", tracking=True)
    sector_id = fields.Many2one('res.partner.sector', string="القطاع", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Keep the legacy subscriber flag aligned with the partner role."""
        for vals in vals_list:
            role = vals.get('utility_partner_type')
            if role == 'subscriber' or (role is None and vals.get('is_subscriber')):
                vals['utility_partner_type'] = 'subscriber'
                vals['is_subscriber'] = True
            elif role and role != 'subscriber':
                vals['is_subscriber'] = False
        return super().create(vals_list)

    def write(self, vals):
        """Synchronize old callers that still write ``is_subscriber``."""
        vals = dict(vals)
        if 'utility_partner_type' in vals:
            vals['is_subscriber'] = vals['utility_partner_type'] == 'subscriber'
        elif 'is_subscriber' in vals:
            vals['utility_partner_type'] = 'subscriber' if vals['is_subscriber'] else 'other'
        return super().write(vals)

    def action_open_utility_customer_registration(self):
        """
        فتح حساب المشترك المرتبط أو تسجيل حساب جديد.

        التسلسل:
        1. إذا وُجد utility.customer مرتبط → فتح الفورم مباشرة.
        2. إذا وُجد سجل تهيئة (utility.migration.customer) مرتبط
           بحالة 'imported' ولم يُفعَّل بعد → استدعاء action_activate_inactive()
           الذي ينشئ الحساب + العداد + الرصيد الافتتاحي ويُحدّث سجل التهيئة.
        3. وإلا → فتح wizard التسجيل العادي للعملاء الجدد.
        """
        if len(self) != 1:
            raise UserError(_('يرجى اختيار شريك واحد فقط.'))
        self.ensure_one()
        if self.utility_partner_type != 'subscriber':
            raise UserError(_('لا يمكن تفعيل حساب كهرباء إلا لشريك مصنف كمشترك كهرباء.'))

        # 1. حساب مشترك موجود بالفعل
        customers = self.env['utility.customer'].search([
            ('partner_id', '=', self.id),
        ])
        if len(customers) == 1:
            return {
                'name': _('حساب المشترك'),
                'type': 'ir.actions.act_window',
                'res_model': 'utility.customer',
                'views': [(False, 'form')],
                'view_mode': 'form',
                'res_id': customers.id,
                'target': 'current',
            }
        if len(customers) > 1:
            return {
                'name': _('حسابات الكهرباء المملوكة'),
                'type': 'ir.actions.act_window',
                'res_model': 'utility.customer',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', customers.ids)],
                'target': 'current',
                'context': {'default_partner_id': self.id},
            }

        # 2. سجل تهيئة مرتبط وبانتظار التفعيل — تفعيل تلقائي بدون wizard
        migration_rec = self.env['utility.migration.customer'].search([
            ('created_partner_id', '=', self.id),
            ('state', '=', 'imported'),
            ('created_customer_id', '=', False),
        ], limit=1)
        if migration_rec:
            try:
                # تفعيل تلقائي كامل: utility.customer + عداد + قراءة + رصيد افتتاحي
                migration_rec.action_activate_inactive()
                if migration_rec.created_customer_id:
                    return {
                        'name': _('حساب المشترك'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'utility.customer',
                        'views': [(False, 'form')],
                        'view_mode': 'form',
                        'res_id': migration_rec.created_customer_id.id,
                        'target': 'current',
                    }
            except UserError:
                # بيانات ناقصة — يُعاد المستخدم لسجل التهيئة لإكمال البيانات
                return {
                    'name': _('إكمال بيانات التفعيل'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'utility.migration.customer',
                    'views': [(False, 'form')],
                    'view_mode': 'form',
                    'res_id': migration_rec.id,
                    'target': 'current',
                }

        # 3. عميل جديد (لا سجل تهيئة) — wizard التسجيل العادي
        return {
            'name': _('تسجيل حساب مشترك'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.customer.wizard',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'res.partner',
                'active_id': self.id,
                'active_ids': [self.id],
            },
        }

    utility_region_id = fields.Many2one('utility.region', string="المنطقة التشغيلية", domain="[('type', '=', 'region')]")
    utility_area_id = fields.Many2one('utility.region', string="الفرع التشغيلي", domain="[('type', '=', 'area')]")
    direct_branch_id = fields.Many2one('utility.region', string="فرع الخدمة المباشر", domain="[('type', '=', 'area')]")
    transformer_zone_id = fields.Many2one('utility.region', string="نطاق المحول", domain="[('type', '=', 'zone')]")
    residential_compound_id = fields.Many2one('utility.region', string="الحي أو المجمع السكني", domain="[('type', '=', 'zone')]")

    payment_token_id = fields.Many2one(
        'payment.token',
        string='رمز الدفع',
        domain="[('id', 'in', payment_token_ids)]",
    )

    def _compute_last_payment(self):
        for partner in self:
            partner.last_payment = 0.0
            partner.last_payment_date = False
            if not partner.id:
                continue
            partner_ids = [partner.id]
            payment = self.env['account.payment'].search([
                ('partner_id', 'in', partner_ids),
                ('state', '=', 'posted'),
            ], order='date desc, id desc', limit=1)
            if payment:
                partner.last_payment = payment.amount
                partner.last_payment_date = payment.date

    def _compute_last_invoice(self):
        for partner in self:
            partner.last_invoice = 0.0
            partner.last_invoice_date = False
            if not partner.id:
                continue
            partner_ids = [partner.id]
            invoice = self.env['account.move'].search([
                ('partner_id', 'in', partner_ids),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')
            ], order='invoice_date desc, id desc', limit=1)
            if invoice:
                partner.last_invoice = invoice.amount_total
                partner.last_invoice_date = invoice.invoice_date

    def _compute_display_name(self):
        super()._compute_display_name()
        if self._context.get('show_nickname'):
            for partner in self:
                if partner.nickname:
                    partner.display_name = f"[{partner.nickname}] {partner.name}"

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('name', operator, name), ('nickname', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    def _get_partner_balance(self, date_cutoff=None, date_range_id=None, journal_type=None, exclude_journal_type=None, date_range_not_null=False, date_range_is_null=False):
        self.ensure_one()
        query = """SELECT sum(l.debit - l.credit) as opening_bal
                   FROM account_move_line l
                   JOIN account_account a ON l.account_id = a.id"""
        if journal_type or exclude_journal_type:
            query += " JOIN account_journal j ON l.journal_id = j.id"
            
        query += " WHERE l.partner_id = %s AND a.account_type = 'asset_receivable'"
        params = [self.id]
        
        if date_cutoff:
            query += " AND l.date < %s"
            params.append(date_cutoff)
        if date_range_id:
            query += " AND l.date_range_id = %s"
            params.append(date_range_id)
        if journal_type:
            query += " AND j.type = %s"
            params.append(journal_type)
        if exclude_journal_type:
            query += " AND j.type != %s"
            params.append(exclude_journal_type)
        if date_range_not_null:
            query += " AND l.date_range_id IS NOT NULL"
        if date_range_is_null:
            query += " AND l.date_range_id IS NULL"
            
        self.env.cr.execute(query, params)
        res = self.env.cr.fetchone()
        return res[0] or 0.0
