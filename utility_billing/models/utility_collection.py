from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class UtilityCollection(models.Model):
    _name = 'utility.collection'
    _description = 'تحصيل فاتورة كهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'collection_date desc, id desc'

    name = fields.Char('المرجع', required=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    collection_date = fields.Datetime(
        'تاريخ التحصيل', required=True, default=fields.Datetime.now)
    payment_id = fields.Many2one(
        'account.payment', required=True, ondelete='restrict', index=True)
    allocation_id = fields.Many2one(
        'utility.payment.allocation', required=True, ondelete='restrict',
        index=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', related='payment_id.utility_customer_id',
        store=True, readonly=True)
    partner_id = fields.Many2one(
        'res.partner', related='utility_customer_id.partner_id',
        string='العميل / الشريك المحاسبي', store=True, readonly=True)
    sale_order_id = fields.Many2one(
        'sale.order', related='payment_id.utility_sale_order_id',
        store=True, readonly=True)
    invoice_id = fields.Many2one(
        'account.move', related='allocation_id.invoice_id',
        store=True, readonly=True)
    collector_id = fields.Many2one('utility.staff', index=True)
    collection_method = fields.Selection([
        ('field_collector', 'محصل ميداني'),
        ('bank_transfer', 'تحويل بنكي'),
        ('external_collection', 'محصل خارجي'),
        ('electronic', 'إلكتروني'),
        ('api', 'واجهة API'),
        ('other', 'أخرى'),
    ], required=True, default='field_collector')
    currency_id = fields.Many2one(
        'res.currency', related='payment_id.currency_id', store=True,
        readonly=True)
    amount = fields.Monetary(
        'المبلغ', related='payment_id.amount', store=True, readonly=True,
        currency_field='currency_id')
    settled_amount = fields.Monetary(
        'المسدد فعليًا', compute='_compute_settled_amount', store=True,
        currency_field='currency_id')
    remaining_amount = fields.Monetary(
        'المتبقي لدى المحصل', compute='_compute_settled_amount', store=True,
        currency_field='currency_id', index=True)
    external_reference = fields.Char('المرجع الخارجي', copy=False, index=True)
    source = fields.Selection([
        ('manual', 'يدوي'), ('gateway', 'بوابة'), ('api', 'API')
    ], default='manual', required=True)
    journal_id = fields.Many2one(
        'account.journal', string='يومية التحصيل', readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'), ('confirmed', 'مؤكد'), ('posted', 'مرحّل'),
        ('included_in_settlement', 'ضمن التسوية'), ('settled', 'مسدد'),
        ('cancelled', 'ملغى'),
    ], default='draft', required=True, tracking=True, index=True)
    account_move_id = fields.Many2one(
        'account.move', 'قيد الدفعة المرتبط', readonly=True, copy=False)
    settlement_line_ids = fields.One2many(
        'utility.collection.settlement.line', 'collection_id', readonly=True)
    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('collection_payment_uniq', 'unique(payment_id)',
         'لا يجوز إنشاء أكثر من تحصيل لنفس الدفعة.'),
        ('collection_allocation_uniq', 'unique(allocation_id)',
         'لا يجوز إنشاء أكثر من تحصيل لنفس التخصيص.'),
        ('collection_external_ref_uniq',
         'unique(company_id, external_reference)',
         'المرجع الخارجي للتحصيل مستخدم مسبقًا.'),
    ]

    @api.depends(
        'settlement_line_ids.actual_settled_amount',
        'settlement_line_ids.settlement_id.state',
    )
    def _compute_settled_amount(self):
        financial_states = ('posted', 'deposited', 'reconciled')
        for record in self:
            actual = sum(
                line.actual_settled_amount
                for line in record.settlement_line_ids
                if line.settlement_id.state in financial_states
            )
            record.settled_amount = actual
            record.remaining_amount = max(record.amount - actual, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault(
                'name', self.env['ir.sequence'].next_by_code(
                    'utility.collection') or _('جديد'))
        records = super().create(vals_list)
        custody_methods = ('field_collector', 'external_collection')
        for record in records:
            if record.payment_id.company_id != record.company_id:
                raise ValidationError(_('شركة التحصيل يجب أن تطابق شركة الدفعة.'))
            if (not record.payment_id._is_utility_posted()
                    or record.allocation_id.state != 'reconciled'):
                raise ValidationError(
                    _('لا يمكن إنشاء تحصيل قبل ترحيل الدفعة وتسوية تخصيصها.'))
            if record.allocation_id.payment_id != record.payment_id:
                raise ValidationError(_('تخصيص التحصيل لا يطابق الدفعة المحددة.'))
            if record.currency_id != record.company_id.currency_id:
                raise ValidationError(
                    _('تحصيلات الكهرباء في هذه المرحلة يجب أن تكون بعملة الشركة.'))
            if record.collection_method in custody_methods:
                if not record.collector_id:
                    raise ValidationError(
                        _('يجب تحديد المحصل للتحصيل الميداني أو الخارجي.'))
                if record.collector_id.company_id != record.company_id:
                    raise ValidationError(
                        _('المحصل يجب أن ينتمي إلى نفس الشركة.'))
                if record.payment_id.collector_id != record.collector_id:
                    raise ValidationError(
                        _('المحصل في سجل التحصيل يجب أن يطابق محصل الدفعة.'))
        return records

    @api.constrains('collection_method', 'collector_id', 'company_id')
    def _check_collector_requirement(self):
        for record in self:
            if record.collection_method in ('field_collector', 'external_collection') and not record.collector_id:
                raise ValidationError(
                    _('التحصيل الميداني أو الخارجي يتطلب محصلًا محددًا.'))
            if record.collector_id and record.collector_id.company_id != record.company_id:
                raise ValidationError(_('المحصل يجب أن ينتمي إلى نفس الشركة.'))

    def _get_accounts(self):
        self.ensure_one()
        company = self.company_id
        journal = self.collector_id.collection_journal_id
        if not journal:
            raise ValidationError(_('يرجى إعداد يومية التحصيل قبل ترحيل التحصيل.'))
        return (
            journal,
            journal.default_account_id,
            company.deposit_clearing_account_id,
        )

    def _lock_for_settlement(self):
        """Lock collections so two settlement confirmations cannot race."""
        self.env.flush_all()
        ids = tuple(self.ids)
        if ids:
            self.env.cr.execute(
                'SELECT id FROM utility_collection WHERE id IN %s ORDER BY id FOR UPDATE',
                [ids],
            )
        self.invalidate_cache()

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            if record.collection_method in ('field_collector', 'external_collection'):
                if not record.collector_id:
                    raise ValidationError(_('حدد المحصل قبل تأكيد التحصيل.'))
            record.state = 'confirmed'
        return True

    def _validate_payment_cash_line(self, cash_account):
        self.ensure_one()
        payment_lines = self.payment_id.move_id.line_ids.filtered(
            lambda line: line.account_id == cash_account
            and not line.reconciled
            and line.debit > 0
        )
        if len(payment_lines) != 1:
            raise ValidationError(_(
                'دفعة التحصيل لا تحتوي على سطر سيولة وحيد في صندوق المتحصل. '
                'راجع إعداد اليومية قبل الترحيل.'
            ))
        if float_compare(
                payment_lines.balance, self.amount,
                precision_rounding=self.company_id.currency_id.rounding) != 0:
            raise ValidationError(_('سطر مقاصة الدفعة لا يطابق مبلغ التحصيل.'))
        return payment_lines

    def action_post(self):
        custody_methods = ('field_collector', 'external_collection')
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_('يجب تأكيد التحصيل قبل ترحيله.'))
            if record.collection_method not in custody_methods:
                # Direct bank/electronic/API payments have no collector custody.
                record.state = 'settled'
                continue

            journal, cash_account, _deposit_clearing = record._get_accounts()
            if not cash_account or journal.type != 'cash':
                raise ValidationError(_('يومية المتحصل لا تحتوي على صندوق نقدي صالح.'))
            if record.payment_id.journal_id != journal:
                raise ValidationError(_('دفعة التحصيل لا تستخدم يومية المتحصل المحدد.'))
            record._validate_payment_cash_line(cash_account)
            # The payment move already represents custody. No second GL entry is created.
            record.write({
                'account_move_id': record.payment_id.move_id.id,
                'journal_id': journal.id,
                'state': 'posted',
            })
        return True

    def action_cancel(self):
        if any(record.state in (
                'posted', 'included_in_settlement', 'settled') for record in self):
            raise ValidationError(
                _('لا يمكن إلغاء تحصيل مرحّل؛ استخدم إجراء عكس معتمد.'))
        self.write({'state': 'cancelled'})


class UtilityCollectionSettlementLine(models.Model):
    _name = 'utility.collection.settlement.line'
    _description = 'بند تسوية تحصيل'

    settlement_id = fields.Many2one(
        'utility.collection.settlement', required=True, ondelete='cascade')
    collection_id = fields.Many2one(
        'utility.collection', required=True, ondelete='restrict')
    amount = fields.Monetary(
        'المبلغ المختار', required=True, currency_field='currency_id')
    actual_settled_amount = fields.Monetary(
        'المبلغ المسدد فعليًا', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(
        related='settlement_id.currency_id', store=True, readonly=True)

    _sql_constraints = [
        ('settlement_collection_uniq',
         'unique(settlement_id, collection_id)',
         'لا يجوز إدخال التحصيل نفسه أكثر من مرة في التسوية نفسها.'),
    ]


class UtilityCollectionSettlement(models.Model):
    _name = 'utility.collection.settlement'
    _description = 'تسوية عهدة محصل'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settlement_date desc, id desc'

    name = fields.Char('رقم التسوية', required=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    collector_id = fields.Many2one('utility.staff', required=True, index=True)
    settlement_date = fields.Date(
        'تاريخ التسوية', required=True, default=fields.Date.today)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many(
        'utility.collection.settlement.line', 'settlement_id',
        string='التحصيلات')
    expected_amount = fields.Monetary(
        'المتوقع', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    declared_amount = fields.Monetary(
        'المصرح بتسليمه', currency_field='currency_id')
    actual_settled_amount = fields.Monetary(
        'المسدد فعليًا', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    difference_amount = fields.Monetary(
        'الفرق', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    shortage_amount = fields.Monetary(
        'العجز', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    surplus_amount = fields.Monetary(
        'الفائض', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    bank_settlement_line_ids = fields.One2many(
        'utility.bank.settlement.line', 'collection_settlement_id',
        string='تخصيصات الإيداع البنكي', readonly=True)
    bank_allocated_amount = fields.Monetary(
        'المخصص بنكيًا', compute='_compute_bank_allocation', store=True,
        currency_field='currency_id')
    remaining_to_deposit = fields.Monetary(
        'المتبقي للإيداع', compute='_compute_bank_allocation', store=True,
        currency_field='currency_id')
    settlement_method = fields.Selection([
        ('cash', 'نقدي'), ('bank_transfer', 'تحويل بنكي'),
        ('external', 'جهة خارجية')
    ], required=True, default='cash')
    state = fields.Selection([
        ('draft', 'مسودة'), ('confirmed', 'مؤكد'), ('posted', 'مرحّل'),
        ('deposited', 'مودع'), ('reconciled', 'مطابق'),
        ('cancelled', 'ملغى')
    ], default='draft', tracking=True)
    allocation_policy = fields.Selection([
        ('explicit', 'تخصيص صريح'),
        ('oldest_first', 'الأقدم أولاً'),
    ], string='سياسة التخصيص', default='oldest_first', required=True,
        readonly=True, copy=False)
    settlement_key = fields.Char(
        string='مفتاح التسوية', readonly=True, copy=False, index=True)
    created_automatically = fields.Boolean(
        string='منشأة تلقائياً', default=False, readonly=True, copy=False)
    account_move_id = fields.Many2one(
        'account.move', readonly=True, copy=False)
    reference = fields.Char('المرجع الميداني / البنكي')
    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('settlement_ref_uniq', 'unique(company_id, name)',
         'مرجع التسوية يجب أن يكون فريدًا.'),
    ]

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_collection_settlement_key_uniq
                ON utility_collection_settlement (company_id, settlement_key)
             WHERE settlement_key IS NOT NULL AND settlement_key <> ''
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault(
                'name', self.env['ir.sequence'].next_by_code(
                    'utility.collection.settlement') or _('جديد'))
            if vals.get('reference'):
                vals.setdefault(
                    'settlement_key', 'COLLECTOR-DEPOSIT:%s:%s' % (
                        vals.get('company_id') or self.env.company.id,
                        vals['reference'].strip().upper()))
        return super().create(vals_list)

    @api.depends('line_ids.amount', 'line_ids.actual_settled_amount',
                 'declared_amount')
    def _compute_amounts(self):
        for record in self:
            expected = sum(record.line_ids.mapped('amount'))
            actual = sum(record.line_ids.mapped('actual_settled_amount'))
            difference = record.declared_amount - expected
            record.expected_amount = expected
            record.actual_settled_amount = actual
            record.difference_amount = difference
            record.shortage_amount = max(expected - record.declared_amount, 0.0)
            record.surplus_amount = max(record.declared_amount - expected, 0.0)

    @api.depends(
        'bank_settlement_line_ids.allocated_amount',
        'bank_settlement_line_ids.bank_settlement_id.state',
        'declared_amount',
    )
    def _compute_bank_allocation(self):
        states = ('confirmed', 'settled')
        grouped = self.env['utility.bank.settlement.line'].read_group(
            [
                ('collection_settlement_id', 'in', self.ids),
                ('bank_settlement_id.state', 'in', states),
            ],
            ['allocated_amount:sum'], ['collection_settlement_id'],
        ) if self else []
        totals = {
            row['collection_settlement_id'][0]: row['allocated_amount']
            for row in grouped if row.get('collection_settlement_id')
        }
        for record in self:
            allocated = totals.get(record.id, 0.0)
            record.bank_allocated_amount = allocated
            record.remaining_to_deposit = max(
                record.declared_amount - allocated, 0.0)

    def _lock_collections(self):
        collections = self.mapped('line_ids.collection_id')
        collections._lock_for_settlement()
        return collections

    def _auto_allocate_oldest_first(self):
        """Allocate an agent deposit against open custody, oldest first."""
        self.ensure_one()
        if self.line_ids or self.allocation_policy != 'oldest_first':
            return
        if self.declared_amount <= 0:
            raise ValidationError(_('يجب أن يكون مبلغ الإيداع أكبر من صفر.'))
        candidates = self.env['utility.collection'].search([
            ('collector_id', '=', self.collector_id.id),
            ('company_id', '=', self.company_id.id),
            ('currency_id', '=', self.currency_id.id),
            ('state', 'in', ('posted', 'included_in_settlement')),
            ('remaining_amount', '>', 0),
        ], order='collection_date asc, id asc')
        candidates._lock_for_settlement()
        remaining = self.declared_amount
        line_vals = []
        for collection in candidates:
            collection.invalidate_recordset(['remaining_amount', 'state'])
            available = collection.remaining_amount
            if self.currency_id.is_zero(available) or self.currency_id.is_zero(remaining):
                continue
            amount = min(available, remaining)
            line_vals.append((0, 0, {
                'collection_id': collection.id,
                'amount': amount,
            }))
            remaining -= amount
        if not line_vals:
            raise ValidationError(_('لا توجد تحصيلات معلقة قابلة للإيداع لهذا المحصل.'))
        self.write({'line_ids': line_vals, 'created_automatically': True})

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            if not record.line_ids:
                record._auto_allocate_oldest_first()
            collections = record._lock_collections()
            if not record.line_ids:
                raise ValidationError(
                    _('أضف تحصيلات مؤهلة قبل تأكيد التسوية.'))
            if record.company_id.currency_id != record.currency_id:
                raise ValidationError(
                    _('يجب أن تكون عملة التسوية هي عملة الشركة في هذه المرحلة.'))
            if record.declared_amount < 0 or float_is_zero(
                    record.declared_amount,
                    precision_rounding=record.currency_id.rounding):
                raise ValidationError(_('يجب أن يكون المبلغ المصرح به أكبر من صفر.'))
            remaining_declared = record.declared_amount
            for line in record.line_ids.sorted('id'):
                collection = line.collection_id
                if collection not in collections or collection.state not in (
                        'posted', 'included_in_settlement'):
                    raise ValidationError(_('أحد تحصيلات التسوية غير مرحّل.'))
                if collection.collector_id != record.collector_id:
                    raise ValidationError(_('كل التحصيلات يجب أن تخص المحصل نفسه.'))
                if collection.company_id != record.company_id or collection.currency_id != record.currency_id:
                    raise ValidationError(_('الشركة أو العملة لا تطابق التسوية.'))
                available = collection.remaining_amount
                if line.amount <= 0 or line.amount > available:
                    raise ValidationError(_('مبلغ بند التسوية غير صحيح.'))
                line.actual_settled_amount = min(
                    line.amount, remaining_declared, available)
                remaining_declared = max(remaining_declared - line.actual_settled_amount, 0.0)
            record.state = 'confirmed'
            record.action_post()
        return True

    def action_post(self):
        for record in self:
            if record.state in ('posted', 'settled'):
                continue
            if record.state != 'confirmed':
                raise ValidationError(_('يجب تأكيد التسوية قبل ترحيلها.'))
            record._lock_collections()
            for line in record.line_ids:
                collection = line.collection_id
                collection.invalidate_cache(['state', 'remaining_amount'])
                if collection.state not in ('posted', 'included_in_settlement'):
                    raise ValidationError(_(
                        'لا يمكن ترحيل التسوية لأن التحصيل %s لم يعد متاحًا.'
                    ) % collection.name)
                if float_compare(
                        line.actual_settled_amount, collection.remaining_amount,
                        precision_rounding=record.currency_id.rounding) > 0:
                    raise ValidationError(_(
                        'تجاوزت التسوية المتبقي المتاح للتحصيل %s بعد تحديثه.'
                    ) % collection.name)
            company = record.company_id
            if not company.deposit_clearing_account_id or not company.settlement_journal_id:
                raise ValidationError(
                    _('يرجى إعداد حساب مقاصة الإيداع ويومية التسويات.'))
            cash_account = record.collector_id.collection_journal_id.default_account_id
            if not cash_account or record.collector_id.collection_journal_id.type != 'cash':
                raise ValidationError(_('يجب إعداد صندوق نقدي مستقل للمحصل.'))
            if record.currency_id != company.currency_id:
                raise ValidationError(
                    _('التسوية متعددة العملات غير مفعلة؛ استخدم عملة الشركة.'))
            declared = record.declared_amount
            actual = min(record.declared_amount, record.expected_amount)
            lines = [(0, 0, {
                'name': record.name,
                'account_id': company.deposit_clearing_account_id.id,
                'debit': declared,
            })]
            if actual:
                lines.append((0, 0, {
                    'name': record.name,
                    'account_id': cash_account.id,
                    'credit': actual,
                }))
            if record.surplus_amount:
                if not company.collection_surplus_account_id:
                    raise ValidationError(
                        _('يرجى إعداد حساب فائض التحصيل قبل تسجيل فائض.'))
                lines.append((0, 0, {
                    'name': _('فائض %s') % record.name,
                    'account_id': company.collection_surplus_account_id.id,
                    'credit': record.surplus_amount,
                }))
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': company.settlement_journal_id.id,
                'date': record.settlement_date,
                'ref': record.name,
                'line_ids': lines,
            })
            move.action_post()
            record.write({'account_move_id': move.id, 'state': 'posted'})
            for line in record.line_ids:
                new_state = (
                    'settled'
                    if float_compare(
                        line.actual_settled_amount, line.collection_id.amount,
                        precision_rounding=record.currency_id.rounding) >= 0
                    else 'included_in_settlement'
                )
                line.collection_id.write({'state': new_state})
        return True

    def unlink(self):
        if any(record.state not in ('draft', 'cancelled') for record in self):
            raise ValidationError(_('لا يمكن حذف تسوية مرحّلة.'))
        return super().unlink()
