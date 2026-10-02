from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class UtilityDeposit(models.Model):
    _name = 'utility.deposit'
    _description = 'تأمين المشتركين'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'deposit_number'
    _order = 'deposit_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', required=True, default=lambda self: self.env.company)
    deposit_number = fields.Char('رقم التأمين', required=True, copy=False, readonly=True, default=lambda self: _('جديد'))
    customer_id = fields.Many2one('utility.customer', 'العميل / المشترك', required=True, index=True)
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True, index=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    amount = fields.Monetary('مبلغ التأمين', required=True, currency_field='currency_id')
    deposit_date = fields.Date('تاريخ التأمين', default=fields.Date.context_today)
    deposit_type = fields.Selection([
        ('connection', 'توصيل'),
        ('security', 'أمان'),
        ('meter', 'عداد'),
    ], string='نوع التأمين', default='security', required=True)
    status = fields.Selection([
        ('draft', 'مسودة'),
        ('held', 'محتجز / مستلم'),
        ('released', 'مسترد'),
        ('forfeited', 'مصادر'),
    ], string='الحالة', default='draft', readonly=True, tracking=True, copy=False)
    release_date = fields.Date('تاريخ الاسترداد', readonly=True, copy=False)
    notes = fields.Text('ملاحظات')

    # ── قيود المحاسبة الحقيقية ────────────────────────────────────────────────
    receipt_move_id = fields.Many2one(
        'account.move', string='قيد استلام التأمين', readonly=True, copy=False, index=True,
        help='قيد استلام التأمين: مدين (النقدية) / دائن (التزامات التأمينات المحتجزة).'
    )
    release_move_id = fields.Many2one(
        'account.move', string='قيد استرداد التأمين', readonly=True, copy=False, index=True,
        help='قيد استرداد التأمين: مدين (التزامات التأمينات) / دائن (النقدية/البنك).'
    )
    forfeit_move_id = fields.Many2one(
        'account.move', string='قيد مصادرة التأمين', readonly=True, copy=False, index=True,
        help='قيد مصادرة التأمين: مدين (التزامات التأمينات) / دائن (إيرادات الغرامات/المصادرة).'
    )
    reclassification_move_id = fields.Many2one(
        'account.move', string='قيد إعادة التصنيف المحاسبي', readonly=True, copy=False, index=True,
        help='قيد تسوية تاريخي: مدين (ذمم المشترك) / دائن (التزامات التأمينات).'
    )

    # حقول التوافق التاريخي
    payment_id = fields.Many2one('account.payment', string='سند القبض (تاريخي)', readonly=True, copy=False)
    legacy_payment_id = fields.Many2one('account.payment', related='payment_id', readonly=False, string='سند القبض التاريخي')
    move_id = fields.Many2one('account.move', string='القيد المحاسبي (تاريخي)', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('deposit_number', _('جديد')) == _('جديد'):
                vals['deposit_number'] = self.env['ir.sequence'].next_by_code('utility.deposit') or _('جديد')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_positive_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    'مبلغ التأمين يجب أن يكون أكبر من الصفر. القيمة المدخلة: %s'
                ) % rec.amount)

    def _lock_records(self):
        """Row-level lock to prevent concurrent state transitions."""
        if self.ids:
            self.env.cr.execute(
                "SELECT id FROM utility_deposit WHERE id IN %s FOR UPDATE",
                [tuple(self.ids)]
            )

    def _get_company_config(self, company_field, config_key):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        param = self.env['ir.config_parameter'].sudo().get_param(config_key, '0')
        return int(param) if param and param.isdigit() else 0

    def action_receive_deposit(self):
        """استلام التأمين:
        ينشئ قيد محاسبي صريح:
          Dr: حساب الصندوق/البنك (Cash/Bank Account)
          Cr: حساب التزامات التأمينات (Deposit Liability Account)
        """
        self._lock_records()
        for rec in self:
            if rec.status != 'draft':
                raise ValidationError(_('يمكن استلام مبالغ التأمين للمسودات فقط.'))
            if rec.amount <= 0:
                raise ValidationError(_('لا يمكن تسجيل وديعة بمبلغ صفر أو سالب.'))
            if rec.receipt_move_id and rec.receipt_move_id.state == 'posted':
                raise ValidationError(_('تم استلام هذا التأمين وترحيل قيده مسبقاً.'))

            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError(_('يرجى تحديد يومية التأمينات وحساب التأمينات (الالتزامات) في الإعدادات أولاً.'))

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError(_('لا يوجد عميل مرتبط بحساب المشترك.'))

            journal = self.env['account.journal'].browse(deposit_journal_id)
            cash_account = journal.default_account_id
            if not cash_account:
                raise ValidationError(_('اليومية المحددة للتأمينات ليس لها حساب افتراضي.'))

            # إنشاء قيد الاستلام: Dr النقدية / Cr التزامات التأمين
            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'company_id': rec.company_id.id,
                'date': rec.deposit_date or fields.Date.context_today(self),
                'ref': _('استلام تأمين رقم: %s') % rec.deposit_number,
                'line_ids': [
                    (0, 0, {
                        'account_id': cash_account.id,
                        'name': _('استلام تأمين %s') % rec.deposit_number,
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': _('تأمين محتجز %s') % rec.deposit_number,
                        'debit': 0.0,
                        'credit': rec.amount,
                        'partner_id': partner.id,
                    }),
                ],
            })
            move.action_post()
            rec.write({
                'status': 'held',
                'receipt_move_id': move.id,
                'move_id': move.id,
            })
            rec.message_post(body=_('تم استلام مبلغ التأمين وترحيل القيد المحاسبي %s.') % move.name)

    def action_release_deposit(self):
        """استرداد التأمين:
        ينشئ قيد استرداد صريح:
          Dr: حساب التزامات التأمينات (Deposit Liability Account)
          Cr: حساب الصندوق/البنك (Cash/Bank Account)
        """
        self._lock_records()
        for rec in self:
            if rec.status != 'held':
                raise ValidationError(_('يمكن استرداد التأمينات المحتجزة فقط.'))
            if rec.release_move_id and rec.release_move_id.state == 'posted':
                raise ValidationError(_('تم استرداد هذا التأمين مسبقاً.'))

            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError(_('يرجى تحديد يومية التأمينات وحساب التأمينات في الإعدادات أولاً.'))

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError(_('لا يوجد عميل مرتبط بحساب المشترك.'))

            journal = self.env['account.journal'].browse(deposit_journal_id)
            bank_account = journal.default_account_id
            if not bank_account:
                raise ValidationError(_('اليومية المحددة ليس لها حساب افتراضي.'))

            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'company_id': rec.company_id.id,
                'date': fields.Date.context_today(self),
                'ref': _('استرداد تأمين رقم: %s') % rec.deposit_number,
                'line_ids': [
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': _('استرداد التأمين %s') % rec.deposit_number,
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': bank_account.id,
                        'name': _('مقابل استرداد تأمين %s') % rec.deposit_number,
                        'debit': 0.0,
                        'credit': rec.amount,
                        'partner_id': partner.id,
                    }),
                ],
            })
            move.action_post()
            rec.write({
                'status': 'released',
                'release_date': fields.Date.context_today(self),
                'release_move_id': move.id,
            })
            rec.message_post(body=_('تم استرداد مبلغ التأمين وترحيل القيد المحاسبي %s.') % move.name)

    def action_forfeit_deposit(self):
        """مصادرة التأمين:
        ينشئ قيد مصادرة صريح:
          Dr: حساب التزامات التأمينات (Deposit Liability Account)
          Cr: حساب إيرادات الغرامات / المصادرات (Fine/Forfeit Revenue Account)
        """
        self._lock_records()
        for rec in self:
            if rec.status != 'held':
                raise ValidationError(_('يمكن مصادرة التأمينات المحتجزة فقط.'))
            if rec.forfeit_move_id and rec.forfeit_move_id.state == 'posted':
                raise ValidationError(_('تمت مصادرة هذا التأمين مسبقاً.'))

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError(_('لا يمكن مصادرة تأمين [%s] بدون عميل مرتبط.') % rec.deposit_number)

            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            fine_account_id = rec._get_company_config('fine_account_id', 'utility.fine_account_id')

            if not deposit_journal_id or not deposit_account_id or not fine_account_id:
                raise ValidationError(_('إعدادات الحسابات غير مكتملة للمصادرة (حساب الغرامات، التأمينات، واليومية).'))

            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'company_id': rec.company_id.id,
                'date': fields.Date.context_today(self),
                'ref': _('مصادرة تأمين رقم: %s') % rec.deposit_number,
                'line_ids': [
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': _('مصادرة التأمين %s') % rec.deposit_number,
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': fine_account_id,
                        'name': _('إيراد مصادرة تأمين %s') % rec.deposit_number,
                        'debit': 0.0,
                        'credit': rec.amount,
                        'partner_id': partner.id,
                    }),
                ],
            })
            move.action_post()
            rec.write({
                'status': 'forfeited',
                'forfeit_move_id': move.id,
            })
            rec.message_post(body=_('تمت مصادرة مبلغ التأمين وترحيل القيد المحاسبي %s.') % move.name)

    def action_reclassify_legacy_deposit(self):
        """إعادة تصنيف وديعة تاريخية (Admin Action):
        للتأمينات القديمة التي سُجلت عبر account.payment كذمم مدينة بالخطأ:
        ينشئ قيد تسوية محاسبي حقيقي:
          Dr: حساب الذمم المدينة للعميل (Customer Receivable)
          Cr: حساب التزامات التأمينات (Deposit Liability Account)
        لإلغاء أثر تخفيض الذمم المدينة وتأسيس التزام التأمين الفعلي دون المساس بالنقدية المقبوضة.
        """
        if not (self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.user.has_group('account.group_account_manager')
                or self.env.is_admin()):
            raise AccessError(_('هذا الإجراء مخصص لمدير النظام أو مدير الحسابات فقط.'))
        self._lock_records()
        for rec in self:
            if not rec.payment_id:
                raise ValidationError(_('لا يمكن إعادة تصنيف تأمين ليس لديه سند قبض تاريخي.'))
            if rec.receipt_move_id and rec.receipt_move_id.state == 'posted':
                continue

            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError(_('يرجى تحديد يومية وحساب التأمينات في الإعدادات أولاً.'))

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError(_('لا يوجد عميل مرتبط بحساب المشترك.'))

            receivable_account = partner.property_account_receivable_id or rec.company_id.account_default_pos_receivable_account_id
            if not receivable_account:
                receivable_account = self.env['account.account'].search([
                    ('company_ids', 'in', [rec.company_id.id]),
                    ('account_type', '=', 'asset_receivable'),
                ], limit=1)

            # إنشاء قيد إعادة التصنيف: Dr الذمم المدينة / Cr التزامات التأمين
            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'company_id': rec.company_id.id,
                'date': fields.Date.context_today(self),
                'ref': _('إعادة تصنيف تأمين تاريخي رقم: %s') % rec.deposit_number,
                'line_ids': [
                    (0, 0, {
                        'account_id': receivable_account.id,
                        'name': _('إعادة تصنيف ذمم تأمين %s') % rec.deposit_number,
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': _('تأمين محتجز معاد تصنيفه %s') % rec.deposit_number,
                        'debit': 0.0,
                        'credit': rec.amount,
                        'partner_id': partner.id,
                    }),
                ],
            })
            move.action_post()

            # التوفيق المحاسبي الدقيق بين سطر الدفعة التاريخية وسطر قيد إعادة التصنيف لإغلاق أثر الذمم المفتوحة
            if rec.payment_id and rec.payment_id.move_id:
                payment_rec_lines = rec.payment_id.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                )
                reclass_rec_lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                )
                if payment_rec_lines and reclass_rec_lines:
                    (payment_rec_lines + reclass_rec_lines).reconcile()

            rec.write({
                'status': 'held',
                'reclassification_move_id': move.id,
                'receipt_move_id': move.id,
            })
            rec.message_post(body=_(
                'تمت إعادة تصنيف التأمين التاريخي وترحيل قيد التسوية وتوفيق الذمم المحاسبية %s (Dr Receivable / Cr Deposit Liability).'
            ) % move.name)

