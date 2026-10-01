from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _current_collector_profile(self, company):
        """Return the current user's active custody profile, not a role source.

        Functional authorization belongs exclusively to ``res.users`` groups.
        The staff record is retained only because collections and settlements
        need a stable custody identity.
        """
        user = self.env.user
        if not (user.has_group('utility_core.group_utility_collector')
                or user._is_admin()
                or user.has_group('base.group_account_manager')):
            return self.env['utility.staff']
        return self.env['utility.staff'].search([
            ('user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=1)

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    opening_customer_id = fields.Many2one(
        'utility.customer', string='حساب افتتاحي للتسوية', index=True,
        copy=False, check_company=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', string='حساب الكهرباء', compute='_compute_utility_customer',
        store=True, index=True, readonly=True)
    utility_opening_move_id = fields.Many2one(
        'account.move', string='قيد الرصيد الافتتاحي', index=True,
        copy=False, check_company=True,
        domain="[('state', '=', 'posted'), ('move_type', '=', 'entry')]",)
    utility_invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية المحددة', index=True,
        copy=False, domain="[('utility_sale_order_id', '=', utility_sale_order_id), ('state', '=', 'posted')]",
        help='الفاتورة الوحيدة التي ستتم مطابقة هذه الدفعة معها.')
    collector_id = fields.Many2one(
        'utility.staff', string='المتحصل الميداني', index=True,
        check_company=True,
        help='المتحصل الذي تخصه اليومية النقدية لهذه الدفعة.')
    collection_request_key = fields.Char(
        string='مفتاح طلب التحصيل الميداني', copy=False, index=True,
        help='معرف ثابت يرسله تطبيق المحصل لمنع تكرار نفس التحصيل عند إعادة المحاولة.')
    collection_company_id = fields.Many2one(
        'res.company', related='company_id', store=True, readonly=True, index=True,
        string='شركة طلب التحصيل',
        help='نسخة مخزنة من شركة الدفعة لاستخدام قيد التفرد على جدول account_payment.')
    collection_request_user_id = fields.Many2one(
        'res.users', string='مستخدم طلب التحصيل الميداني', readonly=True,
        copy=False, index=True)
    service_charge_id = fields.Many2one('utility.service.charge', string='رسم الخدمة', index=True, copy=False, check_company=True)
    utility_payment_method = fields.Selection([
        ('cash', 'نقدي (تحصيل ميداني)'),
        ('bank', 'بنكي (تحصيل ميداني / تحويل)'),
        ('electronic', 'إلكتروني (بوابة دفع / محفظة)'),
    ], string='طريقة دفع الكهرباء', default='cash')
    electronic_doc_no = fields.Char(string='رقم المستند الإلكتروني')
    is_invoice_verified = fields.Boolean(string='تم التحقق من الفاتورة')
    date_range_id = fields.Many2one(
        'date.range',
        string='فترة الدفع',
        domain="[('period_role', 'in', ('reading', 'payment'))]",
    )
    timing_classification = fields.Selection([
        ('on_time', 'في الموعد المحدد'),
        ('late', 'متأخر'),
        ('exceptional', 'استثنائي'),
        ('outside_window', 'خارج نافذة التحصيل الميداني'),
    ], string='تصنيف توقيت السداد', default='on_time', index=True)
    qr_code_value = fields.Char('بيانات QR', compute='_compute_utility_qr_code', readonly=True)
    qr_code_url = fields.Char('رابط QR', compute='_compute_utility_qr_code', readonly=True)
    allocation_ids = fields.One2many(
        'utility.payment.allocation', 'payment_id', string='تخصيصات الدفعة',
        readonly=True, copy=False)
    allocation_count = fields.Integer(
        'عدد التخصيصات', compute='_compute_allocation_count')

    _sql_constraints = [
        (
            'utility_collection_request_key_company_uniq',
            'unique(collection_company_id, collection_request_key)',
            'مفتاح طلب التحصيل الميداني مستخدم مسبقاً في هذه الشركة.',
        ),
    ]

    @api.depends('allocation_ids')
    def _compute_allocation_count(self):
        for payment in self:
            payment.allocation_count = len(payment.allocation_ids)

    @api.depends('journal_id', 'payment_type', 'payment_method_line_id', 'collector_id', 'utility_payment_method')
    def _compute_outstanding_account_id(self):
        super()._compute_outstanding_account_id()
        for pay in self:
            if pay.utility_payment_method == 'cash':
                collector = pay.collector_id or pay._current_collector_profile(pay.company_id)
                cash_account = collector.collection_journal_id.default_account_id if collector and collector.collection_journal_id else False
                if cash_account:
                    pay.outstanding_account_id = cash_account

    @api.depends(
        'utility_sale_order_id', 'utility_sale_order_id.customer_id',
        'opening_customer_id', 'utility_opening_move_id',
        'utility_opening_move_id.utility_customer_id')
    def _compute_utility_customer(self):
        for payment in self:
            payment.utility_customer_id = (
                payment.utility_sale_order_id.customer_id
                or payment.opening_customer_id
                or payment.utility_opening_move_id.utility_customer_id
            )

    def action_view_utility_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('تخصيصات الدفعة'),
            'res_model': 'utility.payment.allocation',
            'view_mode': 'list,form',
            'domain': [('payment_id', '=', self.id)],
            'context': {'default_payment_id': self.id, 'create': False},
        }

    @api.onchange('utility_payment_method')
    def _onchange_utility_payment_method(self):
        if self.utility_payment_method == 'cash':
            collector = self.collector_id or self._current_collector_profile(self.company_id)
            if collector:
                self.collector_id = collector
                self.journal_id = collector.collection_journal_id
        elif self.utility_payment_method == 'electronic':
            provider = self.env['utility.integration.provider'].search([
                ('company_id', '=', self.company_id.id),
                ('provider_type', 'in', ('payment_gateway', 'mobile_money')),
                ('active', '=', True),
            ], limit=1)
            if provider and provider.mode != 'manual':
                elec_journal = self.env['account.journal'].search([
                    ('company_id', '=', self.company_id.id),
                    ('type', '=', 'bank'),
                ], limit=1)
                if elec_journal:
                    self.journal_id = elec_journal

    @api.depends('name', 'amount', 'date', 'state', 'utility_sale_order_id', 'utility_sale_order_id.name', 'utility_sale_order_id.customer_id.customer_number', 'utility_sale_order_id.meter_id.meter_number', 'date_range_id.name')
    def _compute_utility_qr_code(self):
        for payment in self:
            order = payment.utility_sale_order_id
            payload = '|'.join([
                'UTILITY-PAYMENT',
                payment.company_id.name or '',
                payment.name or '',
                order.name or '',
                order.customer_id.customer_number or '',
                order.partner_id.name or payment.partner_id.name or '',
                order.meter_id.meter_number or '',
                payment.date_range_id.name or '',
                'amount=%.2f' % (payment.amount or 0.0),
                'date=%s' % (payment.date or ''),
                'state=%s' % (payment.state or ''),
            ])
            payment.qr_code_value = payload
            payment.qr_code_url = '/report/barcode/?barcode_type=QR&value=%s' % quote(payload)

    def _get_payment_period_for_order(self, order):
        """Return the payment period for a bill's date_range_id.

        نموذج الدورة الموحد: السجل نفسه يحمل كلا النطاقين — نُرجع date_range_id مباشرة.
        السجلات التاريخية (period_role='payment'): نبحث بـ reading_period_id أو parent_id.
        """
        if not order or not order.date_range_id:
            return self.env['date.range']

        order_period = order.date_range_id

        # السجل الموحد (قراءة): يحمل نطاق الدفع بداخله — نُرجع السجل نفسه
        if order_period.period_role == 'reading':
            return order_period

        # التوافق العكسي: سجل قديم له period_role آخر — نبحث عن سجل الدفع التاريخي
        # 1. البحث باستخدام الرابط المباشر الصريح reading_period_id
        period = self.env['date.range'].search([
            ('period_role', '=', 'payment'),
            ('reading_period_id', '=', order_period.id),
            ('company_id', 'in', [order.company_id.id, False]),
        ], order='is_current_period desc, date_start desc, id desc', limit=1)

        # 2. التوافق العكسي: البحث بـ parent_id إذا لم يتوفر reading_period_id
        if not period:
            period = self.env['date.range'].search([
                ('period_role', '=', 'payment'),
                ('parent_id', '=', order_period.id),
                ('company_id', 'in', [order.company_id.id, False]),
            ], order='is_current_period desc, date_start desc, id desc', limit=1)

        # 3. إذا لم يوجد سجل دفع منفصل — السجل نفسه يحمل الدفع (تحويل غير مكتمل لدورة بدون payment period)
        if not period:
            return order_period

        return period

    def _validate_utility_payment_period(self):
        """Ensure a utility payment is linked to the correct billing cycle.

        السجل الموحد (period_role='reading'):
          - date_range_id للدفعة يجب أن يطابق date_range_id للفاتورة.
          - collection_state يجب أن يكون 'open' أو 'closing'.
        السجلات التاريخية (period_role='payment'): التحقق بالمنطق القديم.
        """
        for payment in self.filtered('utility_sale_order_id'):
            order_period = payment.utility_sale_order_id.date_range_id
            if not order_period:
                raise ValidationError(_('لا يمكن تسجيل التحصيل لأن الفاتورة غير مرتبطة بفترة قراءة.'))
            if not payment.date_range_id:
                raise ValidationError(_('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".') % order_period.display_name)

            pay_period = payment.date_range_id

            # السجل الموحد (period_role='reading'): تحقق مباشر
            if pay_period.period_role == 'reading':
                if pay_period != order_period:
                    raise ValidationError(_(
                        'فترة الدفعة يجب أن تطابق فترة قراءة الفاتورة "%s".، الفترة الحالية: "%s".'
                    ) % (order_period.display_name, pay_period.display_name))
                if pay_period.collection_state not in ('open', 'closing'):
                    raise ValidationError(_(
                        'حالة التحصيل للدورة "%s" هي "%s". لا يمكن تسجيل دفعة بعد إغلاق التحصيل.'
                    ) % (pay_period.display_name, pay_period.collection_state))
                return

            # التوافق العكسي: سجلات تاريخية (period_role != 'reading')
            if pay_period.period_role != 'payment':
                raise ValidationError(_('فترة التحصيل يجب أن تكون من نوع سداد وتحصيل.'))
            linked_reading_period = pay_period.reading_period_id or pay_period.parent_id
            if linked_reading_period != order_period:
                raise ValidationError(_(
                    'فترة التحصيل يجب أن تكون فترة الدفع المرتبطة مباشرة بفترة قراءة الفاتورة "%s".'
                ) % order_period.display_name)

    def _validate_utility_payment_amount(self):
        """Validate and lock the exact utility invoice before posting payment."""
        self.ensure_one()
        if not self.utility_sale_order_id:
            return
        if self.utility_payment_method == 'cash':
            collector = self.collector_id or self._current_collector_profile(self.company_id)
            if not collector or not collector.collection_journal_id:
                raise ValidationError(_(
                    'يجب تجهيز اليومية النقدية المستقلة للمتحصل قبل ترحيل التحصيل.'
                ))
            if self.journal_id != collector.collection_journal_id:
                raise ValidationError(_(
                    'دفعة التحصيل يجب أن تستخدم اليومية الخاصة بالمتحصل المحدد.'
                ))
            cash_account = collector.collection_journal_id.default_account_id
            if not cash_account:
                raise ValidationError(_(
                    'يجب إعداد حساب صندوق نقدي مستقل في يومية التحصيل للمتحصل.'
                ))
            if self.outstanding_account_id != cash_account:
                for line in collector.collection_journal_id.inbound_payment_method_line_ids:
                    if line.payment_account_id != cash_account:
                        line.sudo().write({'payment_account_id': cash_account.id})
                self.outstanding_account_id = cash_account
            if self.outstanding_account_id != cash_account:
                raise ValidationError(_(
                    'حساب سيولة دفعة المتحصل يجب أن يكون حساب صندوق المتحصل المستقل.'
                ))
        self.env['utility.payment.allocation'].prevalidate_payment(
            self, require_posted=False)

    @api.onchange('utility_sale_order_id')
    def _onchange_utility_sale_order_id(self):
        if self.utility_sale_order_id:
            payment_period = self._get_payment_period_for_order(self.utility_sale_order_id)
            self.date_range_id = payment_period

    @api.constrains(
        'utility_sale_order_id', 'utility_invoice_id', 'partner_id',
        'date_range_id', 'collector_id', 'journal_id', 'utility_payment_method')
    def _check_utility_payment_period_matches_bill(self):
        self._validate_utility_payment_period()
        for payment in self.filtered('utility_sale_order_id'):
            order = payment.utility_sale_order_id
            expected_partner = order.customer_id.partner_id
            if payment.partner_id != expected_partner:
                raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
            if not payment.utility_invoice_id:
                raise ValidationError(_('يجب تحديد الفاتورة المحاسبية التي ستطابق معها الدفعة.'))
            if payment.utility_invoice_id.utility_sale_order_id != order:
                raise ValidationError(_('الفاتورة المحددة لا تخص فاتورة الكهرباء المختارة.'))
            if payment.utility_invoice_id.partner_id != expected_partner:
                raise ValidationError(_('شريك الفاتورة المحاسبية لا يطابق شريك الحساب الكهربائي.'))
            if payment.utility_payment_method == 'cash':
                if not payment.collector_id or payment.journal_id != payment.collector_id.collection_journal_id:
                    raise ValidationError(_('دفعة التحصيل النقدية يجب أن تطابق يومية المتحصل.'))

    def _prepare_field_collector_payment(self, vals, order):
        """Bind cash utility payments to the current collector cash journal."""
        if vals.get('utility_payment_method', 'cash') != 'cash':
            return
        collector = self.env['utility.staff'].browse(
            vals.get('collector_id')).exists() if vals.get('collector_id') else self._current_collector_profile(order.company_id)
        if not collector or not collector.collection_journal_id:
            raise ValidationError(_(
                'لا توجد يومية نقدية مستقلة مهيأة للمتحصل الحالي.'
            ))
        if collector.company_id != order.company_id:
            raise ValidationError(_('المتحصل واليومية يجب أن ينتميا إلى شركة الفاتورة.'))
        journal = collector.collection_journal_id
        journal_id = vals.get('journal_id')
        if journal_id and journal_id != journal.id:
            raise ValidationError(_('لا يمكن تسجيل دفعة المتحصل في يومية متحصل آخر.'))
        vals['collector_id'] = collector.id
        vals['journal_id'] = journal.id
        cash_account = journal.default_account_id
        if cash_account:
            for line in journal.inbound_payment_method_line_ids:
                if line.payment_account_id != cash_account:
                    line.sudo().write({'payment_account_id': cash_account.id})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order_id = vals.get('utility_sale_order_id')
            if order_id:
                order = self.env['sale.order'].browse(order_id)
                if not order.customer_id:
                    raise ValidationError(_('فاتورة الكهرباء لا تحتوي على حساب كهربائي.'))
                expected_partner_id = order.customer_id.partner_id.id
                if vals.get('partner_id') and vals['partner_id'] != expected_partner_id:
                    raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
                vals['partner_id'] = expected_partner_id
                self._prepare_field_collector_payment(vals, order)
                payment_period = self._get_payment_period_for_order(order)
                if not payment_period:
                    raise ValidationError(
                        _('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".')
                        % order.date_range_id.display_name
                    )
                vals['date_range_id'] = payment_period.id

            # توجيه اليومية تلقائياً إذا كان الدفع يدوياً ولم تتحدد اليومية
            payment_method = vals.get('utility_payment_method', 'cash')
            if payment_method in ('cash', 'bank') and not vals.get('journal_id'):
                user_journal = self.env.user.collection_journal_id
                if user_journal:
                    vals['journal_id'] = user_journal.id

        payments = super().create(vals_list)
        for payment, vals in zip(payments, vals_list):
            if vals.get('service_charge_id'):
                payment.service_charge_id.payment_id = payment.id
        return payments

    def write(self, vals):
        if vals.get('utility_sale_order_id'):
            order = self.env['sale.order'].browse(vals['utility_sale_order_id'])
            expected_partner_id = order.customer_id.partner_id.id
            if vals.get('partner_id', expected_partner_id) != expected_partner_id:
                raise ValidationError(_('شريك الدفعة يجب أن يطابق شريك الحساب الكهربائي.'))
            vals['partner_id'] = expected_partner_id
            payment_period = self._get_payment_period_for_order(order)
            if not payment_period:
                raise ValidationError(
                    _('لا توجد فترة دفع مرتبطة بفترة قراءة الفاتورة "%s".')
                    % order.date_range_id.display_name
                )
            vals['date_range_id'] = payment_period.id
            self._prepare_field_collector_payment(vals, order)
            return super().write(vals)

        if 'collector_id' in vals or 'journal_id' in vals or 'utility_payment_method' in vals:
            utility_payments = self.filtered('utility_sale_order_id')
            if utility_payments:
                res = True
                for payment in utility_payments:
                    candidate = dict(vals)
                    candidate.setdefault('utility_payment_method', payment.utility_payment_method)
                    candidate.setdefault('collector_id', payment.collector_id.id)
                    candidate.setdefault('journal_id', payment.journal_id.id)
                    payment._prepare_field_collector_payment(
                        candidate, payment.utility_sale_order_id)
                    res = super(AccountPayment, payment).write(candidate) and res
                non_utility = self - utility_payments
                if non_utility:
                    res = super(AccountPayment, non_utility).write(vals) and res
                if vals.get('service_charge_id'):
                    for payment in self:
                        payment.service_charge_id.payment_id = payment.id
                return res

        res = super().write(vals)
        if vals.get('service_charge_id'):
            for payment in self:
                payment.service_charge_id.payment_id = payment.id
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_utility_sale_order_id')
        if order_id and 'date_range_id' in fields_list:
            order = self.env['sale.order'].browse(order_id).exists()
            payment_period = self._get_payment_period_for_order(order)
            if payment_period:
                res['date_range_id'] = payment_period.id
        if order_id and 'utility_invoice_id' in fields_list:
            order = self.env['sale.order'].browse(order_id).exists()
            if order:
                posted_moves = (order.invoice_ids | order.utility_move_ids).filtered(
                    lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund'))
                if len(posted_moves) == 1:
                    res['utility_invoice_id'] = posted_moves.id

        if order_id and 'collector_id' in fields_list:
            order = self.env['sale.order'].browse(order_id).exists()
            collector = self._current_collector_profile(order.company_id) if order else self.env['utility.staff']
            if collector:
                res['collector_id'] = collector.id
                if 'journal_id' in fields_list and collector.collection_journal_id:
                    res['journal_id'] = collector.collection_journal_id.id

        # تعيين طريقة الدفع الافتراضية واليومية الميدانية للمستخدم
        if 'utility_payment_method' in fields_list and not res.get('utility_payment_method'):
            res['utility_payment_method'] = 'cash'

        if 'journal_id' in fields_list and not res.get('journal_id'):
            if self.env.user.collection_journal_id:
                res['journal_id'] = self.env.user.collection_journal_id.id
        return res

    def _create_payment_notification(self):
        Notification = self.env['utility.notification.log'].sudo()
        send_sms = self.env['ir.config_parameter'].sudo().get_param('utility.send_sms_on_payment', False)
        for payment in self.filtered('utility_sale_order_id'):
            order = payment.utility_sale_order_id
            body = _('تم استلام دفعة بمبلغ %.2f للفاتورة %s. المتبقي %.2f.') % (
                payment.amount, order.name, order.balance_due)
            Notification.create_log(
                'payment_received', body, record=payment, customer=order.customer_id,
                partner=payment.partner_id, channel='portal', subject=_('استلام دفعة كهرباء'))
            if send_sms:
                Notification.create_log(
                    'payment_received', body, record=payment, customer=order.customer_id,
                    partner=payment.partner_id, channel='sms', subject=_('استلام دفعة كهرباء'))

    def _create_field_collection_from_allocation(self, allocation):
        """Create the custody record for a posted field-cash payment once.

        The payment and its exact invoice allocation remain the accounting
        source of truth; the collection is the operational custody record used
        by collector settlements and bank deposits.
        """
        self.ensure_one()
        if self.utility_payment_method != 'cash' or not self.collector_id:
            return self.env['utility.collection']
        collection_model = self.env['utility.collection']
        existing = collection_model.search([('payment_id', '=', self.id)], limit=1)
        if existing:
            return existing
        collection = collection_model.create({
            'payment_id': self.id,
            'allocation_id': allocation.id,
            'collector_id': self.collector_id.id,
            'collection_method': 'field_collector',
            'source': 'manual',
            'external_reference': self.name,
        })
        collection.action_confirm()
        collection.action_post()
        return collection

    def action_post(self):
        # FIX-15: منع ترحيل دفعة على فاتورة ملغاة أو مدفوعة بالكامل
        for payment in self.filtered(lambda p: p.utility_sale_order_id or p.utility_opening_move_id):
            order = payment.utility_sale_order_id
            if payment.utility_opening_move_id and not payment.utility_invoice_id:
                payment.utility_invoice_id = payment.utility_opening_move_id.id
            if order and not payment.date_range_id:
                payment_period = payment._get_payment_period_for_order(order)
                if payment_period:
                    payment.date_range_id = payment_period.id
                else:
                    raise ValidationError(_('لا توجد فترة دفع مرتبطة بفترة قراءة هذه الفاتورة.'))
            if order:
                payment._validate_utility_payment_period()
            payment._validate_utility_payment_amount()
            if order and order.state == 'cancel':
                raise ValidationError(
                    'لا يمكن تسجيل دفعة على فاتورة ملغاة [%s]. يُرجى التحقق من رقم الفاتورة.' % order.name
                )
            if order and order.bill_state == 'paid' and order.balance_due <= 0:
                raise ValidationError(
                    'الفاتورة [%s] مدفوعة بالكامل بالفعل. لا حاجة لتسجيل دفعة إضافية.' % order.name
                )
            # تحديد تصنيف توقيت السداد
            period = payment.date_range_id
            pay_date = payment.date or fields.Date.context_today(payment)
            pay_datetime = fields.Datetime.to_datetime(payment.date) or fields.Datetime.now()
            # فحص حالة التحصيل: مفتوحة أو قيد الإغلاق (مع مراعاة استقلالية التحصيل عن القراءة)
            is_collection_active = (
                getattr(period, 'collection_state', False) in ('open', 'closing')
                or (period and period.state in ('open', 'closing', 'payment_open'))
            )

            # 1. الدورة الموحدة: نطاق الدفع الصريح (Date)
            if period and period.payment_start and period.payment_end:
                if period.payment_start <= pay_date <= period.payment_end:
                    payment.timing_classification = 'on_time' if is_collection_active else 'late'
                elif pay_date > period.payment_end:
                    payment.timing_classification = 'late'
                else:
                    payment.timing_classification = 'outside_window'
            # 2. السجلات التاريخية أو الدقيقة: نافذة التحصيل (Datetime)
            elif period and period.payment_window_start and period.payment_window_end:
                if period.payment_window_start <= pay_datetime <= period.payment_window_end:
                    payment.timing_classification = 'on_time' if is_collection_active else 'late'
                else:
                    payment.timing_classification = 'late' if pay_datetime > period.payment_window_end else 'outside_window'
            # 3. اعتماد حالة التحصيل إذا كانت الفترة بدون نطاق صريح
            elif period and is_collection_active:
                payment.timing_classification = 'on_time'
            elif order:
                payment.timing_classification = 'late'
        res = super().action_post()
        utility_payments = self.filtered('utility_customer_id')
        for payment in utility_payments:
            if payment.move_id and 'utility_customer_id' in payment.move_id._fields:
                payment.move_id.write({'utility_customer_id': payment.utility_customer_id.id})
        self.filtered('service_charge_id').mapped('service_charge_id').action_mark_paid_from_payment()
        for payment in self.filtered(lambda p: p.utility_sale_order_id or p.utility_opening_move_id):
            allocation = self.env['utility.payment.allocation'].with_context(
                utility_payment_source=(
                    'gateway' if payment.utility_payment_method == 'electronic'
                    else 'bank' if payment.utility_payment_method == 'bank'
                    else 'cashier'
                )
            ).allocate_payment(payment)
            if payment.utility_sale_order_id:
                payment._create_field_collection_from_allocation(allocation)
        self.filtered('utility_sale_order_id')._create_payment_notification()
        return res

    def _reconcile_utility_sale_order(self):
        """Backward-compatible entry point delegating to the single allocator."""
        self.ensure_one()
        return self.env['utility.payment.allocation'].allocate_payment(self)
