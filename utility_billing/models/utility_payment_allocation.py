from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class UtilityPaymentAllocation(models.Model):
    _name = 'utility.payment.allocation'
    _description = 'تخصيص دفعة كهرباء'
    _order = 'allocation_date desc, id desc'

    name = fields.Char('المرجع', required=True, copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', related='payment_id.company_id', store=True,
        readonly=True, index=True)
    payment_id = fields.Many2one(
        'account.payment', string='الدفعة', required=True, ondelete='restrict',
        index=True, check_company=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', related='payment_id.utility_customer_id',
        string='حساب الكهرباء', store=True, readonly=True, index=True)
    sale_order_id = fields.Many2one(
        'sale.order', related='payment_id.utility_sale_order_id',
        string='فاتورة الكهرباء', store=True, readonly=True, index=True)
    invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية', required=True,
        ondelete='restrict', index=True, check_company=True,
        domain="[('utility_sale_order_id', '=', sale_order_id), ('state', '=', 'posted')]" )
    partner_id = fields.Many2one(
        'res.partner', related='payment_id.partner_id', string='الشريك المحاسبي',
        store=True, readonly=True, index=True)
    currency_id = fields.Many2one(
        'res.currency', related='payment_id.currency_id', store=True,
        readonly=True)

    requested_amount = fields.Monetary('المبلغ المطلوب', currency_field='currency_id')
    allocated_amount = fields.Monetary('المبلغ المخصص', currency_field='currency_id')
    residual_before = fields.Monetary('المتبقي قبل التخصيص', currency_field='currency_id')
    residual_after = fields.Monetary('المتبقي بعد التخصيص', currency_field='currency_id')
    allocation_date = fields.Datetime(
        'تاريخ التخصيص', required=True, default=fields.Datetime.now, index=True)
    source = fields.Selection([
        ('cashier', 'تحصيل نقدي'),
        ('bank', 'تحويل بنكي'),
        ('gateway', 'بوابة دفع'),
        ('api', 'واجهة API'),
        ('migration', 'ترحيل'),
    ], string='المصدر', required=True, default='cashier', index=True)
    external_reference = fields.Char('المرجع الخارجي', index=True, copy=False)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('allocated', 'مخصص'),
        ('reconciled', 'تمت التسوية'),
        ('reversed', 'معكوس'),
        ('cancelled', 'ملغى'),
        ('error', 'خطأ'),
    ], string='الحالة', required=True, default='draft', index=True)
    partial_reconcile_ids = fields.Many2many(
        'account.partial.reconcile', 'utility_payment_allocation_partial_rel',
        'allocation_id', 'partial_reconcile_id', string='تسويات محاسبية',
        readonly=True, copy=False)
    reconciliation_reference = fields.Char('مرجع التسوية', readonly=True, copy=False)
    created_by = fields.Many2one(
        'res.users', string='أنشأه', default=lambda self: self.env.user,
        required=True, readonly=True)
    reversed_at = fields.Datetime('تاريخ العكس', readonly=True, copy=False)
    reversed_by = fields.Many2one('res.users', string='عُكس بواسطة', readonly=True, copy=False)
    reversal_reason = fields.Text('سبب العكس', readonly=True, copy=False)
    notes = fields.Text('ملاحظات')
    error_message = fields.Text('رسالة الخطأ', readonly=True)

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_payment_allocation_ext_uniq
                ON utility_payment_allocation
                   (source, external_reference, utility_customer_id)
             WHERE external_reference IS NOT NULL AND external_reference <> ''
            """
        )
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_payment_allocation_payment_invoice_uniq
                ON utility_payment_allocation (payment_id, invoice_id)
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('utility_allocation_internal'):
            raise ValidationError(_(
                'لا يمكن إنشاء تخصيص مالي يدويًا؛ يتم إنشاؤه فقط من محرك التحصيل.'
            ))
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'utility.payment.allocation') or _('New')
        return super().create(vals_list)

    @api.constrains('payment_id', 'invoice_id', 'partner_id', 'utility_customer_id')
    def _check_allocation_context(self):
        for allocation in self:
            payment = allocation.payment_id
            invoice = allocation.invoice_id
            customer = allocation.utility_customer_id
            if not payment or not invoice or not customer:
                continue
            if payment.utility_sale_order_id != invoice.utility_sale_order_id:
                raise ValidationError(_('الدفعة والفاتورة المحاسبية لا تخصان نفس فاتورة الكهرباء.'))
            if invoice.utility_customer_id != customer:
                raise ValidationError(_('الفاتورة المحاسبية لا تخص حساب الكهرباء المحدد.'))
            if payment.partner_id != customer.partner_id or invoice.partner_id != customer.partner_id:
                raise ValidationError(_('الشريك المحاسبي لا يطابق حساب الكهرباء.'))

    @staticmethod
    def _partial_ids(lines):
        partials = lines.mapped('matched_debit_ids') | lines.mapped('matched_credit_ids')
        return partials

    def _lock_invoice(self, invoice):
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM account_move WHERE id = %s FOR UPDATE', [invoice.id])
        invoice.invalidate_recordset([
            'state', 'partner_id', 'move_type', 'amount_residual', 'payment_state'])

    @staticmethod
    def _target_residual(invoice, opening=False):
        if opening:
            return sum(invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
                and line.debit > 0 and not line.reconciled
            ).mapped('amount_residual'))
        return invoice.amount_residual

    @api.model
    def prevalidate_payment(self, payment, require_posted=False):
        """Lock and validate the exact invoice before or after payment posting."""
        payment.ensure_one()
        order = payment.utility_sale_order_id
        customer = payment.utility_customer_id
        invoice = payment.utility_invoice_id
        opening_move = payment.utility_opening_move_id
        if not customer or not invoice or (not order and not opening_move):
            raise ValidationError(_('بيانات الدفعة الكهربائية غير مكتملة للتخصيص.'))
        if payment.payment_type != 'inbound':
            raise ValidationError(_('تخصيص الدفعات الصادرة خارج نطاق تحصيل الكهرباء.'))
        if require_posted and not payment._is_utility_posted():
            raise ValidationError(_('لا يمكن تخصيص دفعة غير مرحلة.'))
        if (invoice.utility_sale_order_id != order
                or invoice.utility_customer_id != customer
                or payment.partner_id != customer.partner_id
                or invoice.partner_id != customer.partner_id):
            raise ValidationError(_('الدفعة والفاتورة لا تخصان نفس حساب الكهرباء.'))
        receivable_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable')
        target_currency = (receivable_lines[:1].currency_id
                           or invoice.currency_id)
        if payment.currency_id != target_currency:
            raise ValidationError(_('عملة الدفعة يجب أن تطابق عملة الفاتورة المحاسبية.'))
        self._lock_invoice(invoice)
        valid_opening = bool(opening_move and invoice == opening_move)
        if invoice.state != 'posted' or (
                invoice.move_type != 'out_invoice' and not valid_opening):
            raise ValidationError(_('المستند المحدد ليس مستند ذمم مدينة ومرحلاً.'))
        if payment.amount <= 0:
            raise ValidationError(_('يجب أن يكون مبلغ الدفعة أكبر من صفر.'))
        residual = self._target_residual(invoice, opening=valid_opening)
        if residual <= 0:
            raise ValidationError(_('الفاتورة المحددة مسددة بالكامل.'))
        if payment.amount > residual:
            raise ValidationError(_('مبلغ الدفعة يتجاوز المتبقي الحالي للفواتير المحددة.'))
        return invoice

    def _resolve_source(self, payment):
        source = self.env.context.get('utility_payment_source')
        if source:
            return source
        if payment.utility_payment_method == 'electronic':
            return 'gateway'
        if payment.utility_payment_method == 'bank':
            return 'bank'
        return 'cashier'

    @api.model
    def allocate_payment(self, payment):
        """Create one auditable allocation and reconcile only its exact invoice."""
        payment.ensure_one()
        if not payment.utility_sale_order_id and not payment.utility_opening_move_id:
            return self.env['utility.payment.allocation']

        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM account_payment WHERE id = %s FOR UPDATE',
            [payment.id],
        )
        payment.invalidate_recordset()

        existing = self.search([
            ('payment_id', '=', payment.id),
            ('state', 'in', ('allocated', 'reconciled')),
        ], limit=1)
        if existing:
            return existing

        customer = payment.utility_customer_id
        order = payment.utility_sale_order_id
        invoice = payment.utility_invoice_id
        source = self._resolve_source(payment)
        external_reference = self.env.context.get(
            'utility_external_reference') or payment.electronic_doc_no

        if external_reference:
            duplicate = self.search([
                ('source', '=', source),
                ('external_reference', '=', external_reference),
                ('utility_customer_id', '=', customer.id),
                ('payment_id', '!=', payment.id),
                ('state', 'in', ('allocated', 'reconciled')),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'تم تسجيل المرجع الخارجي %s مسبقًا لهذه الدفعة.'
                ) % external_reference)

        if (not payment._is_utility_posted() or not customer or not invoice
                or (not order and not payment.utility_opening_move_id)):
            raise ValidationError(_('بيانات الدفعة الكهربائية غير مكتملة للتخصيص.'))
        if payment.payment_type != 'inbound':
            raise ValidationError(_('تخصيص الدفعات الصادرة خارج نطاق تحصيل الكهرباء.'))

        invoice = self.prevalidate_payment(payment, require_posted=True)

        residual_before = self._target_residual(
            invoice, opening=bool(payment.utility_opening_move_id))
        acting_user = self.env.user
        allocation = self.with_context(
            utility_allocation_internal=True,
        ).sudo().create({
            'payment_id': payment.id,
            'invoice_id': invoice.id,
            'requested_amount': payment.amount,
            'residual_before': residual_before,
            'source': source,
            'external_reference': external_reference,
            'created_by': acting_user.id,
            'state': 'allocated',
        })

        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: (
                not line.reconciled
                and line.partner_id == invoice.partner_id
                and line.account_id.account_type == 'asset_receivable'
                and line.company_id == invoice.company_id
                and (not line.currency_id or line.currency_id == invoice.currency_id)
            ))
        invoice_lines = invoice.line_ids.filtered(
            lambda line: (
                not line.reconciled
                and line.partner_id == invoice.partner_id
                and line.account_id.account_type == 'asset_receivable'
                and line.company_id == invoice.company_id
                and (not line.currency_id or line.currency_id == invoice.currency_id)
            ))
        if not payment_lines or not invoice_lines:
            raise ValidationError(_('تعذر تحديد سطور الذمم المدينة للدفعة والفاتورة.'))

        before_partials = self._partial_ids(payment_lines | invoice_lines)
        payment_groups = defaultdict(lambda: self.env['account.move.line'])
        invoice_groups = defaultdict(lambda: self.env['account.move.line'])
        for line in payment_lines:
            payment_groups[(line.account_id.id, line.currency_id.id or invoice.currency_id.id)] |= line
        for line in invoice_lines:
            invoice_groups[(line.account_id.id, line.currency_id.id or invoice.currency_id.id)] |= line
        common_keys = sorted(set(payment_groups) & set(invoice_groups))
        if not common_keys:
            raise ValidationError(_('لا يوجد حساب ذمم مشترك بين الدفعة والفاتورة المحددة.'))
        for key in common_keys:
            (payment_groups[key] | invoice_groups[key]).reconcile()

        invoice.invalidate_recordset(['amount_residual', 'payment_state'])
        residual_after = self._target_residual(
            invoice, opening=bool(payment.utility_opening_move_id))
        allocated_amount = residual_before - residual_after
        currency = invoice.currency_id
        if (float_is_zero(allocated_amount, precision_rounding=currency.rounding)
                or float_compare(
                    residual_before - allocated_amount, residual_after,
                    precision_rounding=currency.rounding) != 0
                or float_compare(allocated_amount, payment.amount,
                                 precision_rounding=currency.rounding) != 0):
            raise ValidationError(_('فشل التحقق من ثابت المبلغ بعد التسوية المحاسبية.'))

        partials = self._partial_ids(payment_lines | invoice_lines) - before_partials
        allocation.with_context(utility_allocation_internal=True).write({
            'allocated_amount': allocated_amount,
            'residual_after': residual_after,
            'partial_reconcile_ids': [(6, 0, partials.ids)],
            'reconciliation_reference': ', '.join(map(str, partials.ids)),
            'state': 'reconciled',
        })
        return allocation

    def action_reverse(self, reason=None):
        return self.action_reverse_allocation(reason=reason)

    def action_reverse_allocation(self, reason=None):
        """Idempotent, controlled reversal of payment allocation.

        Removes only the exact partial reconciliations, restores invoice residual
        and order balance, and handles collection custody dependencies without
        blindly cancelling the underlying payment.
        Requires Billing Manager or Utility Admin privileges.
        """
        if not (self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')
                or self.env.su):
            raise AccessError(_('ليس لديك صلاحية عكس تخصيص الدفعات المالية. يتطلب صلاحية مدير الفوترة أو مدير النظام.'))

        for allocation in self:
            if allocation.state == 'reversed':
                raise ValidationError(_('التخصيص %s معكوس بالفعل.') % allocation.name)
            if allocation.state not in ('allocated', 'reconciled'):
                raise ValidationError(_('لا يمكن عكس تخصيص في حالة %s.') % allocation.state)

            # 1. Collection dependency state matrix
            if 'utility.collection' in self.env:
                collections = self.env['utility.collection'].search([
                    '|', ('allocation_id', '=', allocation.id),
                    ('payment_id', '=', allocation.payment_id.id)
                ])
                for col in collections:
                    if col.state in ('settled', 'deposited', 'reconciled'):
                        raise ValidationError(_(
                            'لا يمكن عكس التخصيص لوجود تحصيل مرتبط في حالة تسوية أو إيداع (%s). يجب عكس التسوية أولاً.'
                        ) % col.display_name)
                    if hasattr(col, 'settlement_id') and col.settlement_id and col.settlement_id.state not in ('cancelled',):
                        raise ValidationError(_(
                            'التحصيل المرتبط بالتخصيص مدرج في تسوية عهدة (%s). يجب إزالته من التسوية أولاً.'
                        ) % col.settlement_id.display_name)
                    col.sudo().write({'state': 'cancelled'})

            # 2. Lock records
            self.env.flush_all()
            self.env.cr.execute('SELECT id FROM account_move WHERE id = %s FOR UPDATE', [allocation.invoice_id.id])
            self.env.cr.execute('SELECT id FROM account_payment WHERE id = %s FOR UPDATE', [allocation.payment_id.id])

            # 3. Unlink only exact partial reconciliations
            if allocation.partial_reconcile_ids:
                allocation.partial_reconcile_ids.unlink()

            # 4. Invalidate and refresh balances
            allocation.invoice_id.invalidate_recordset(['amount_residual', 'payment_state'])
            if allocation.sale_order_id:
                allocation.sale_order_id.invalidate_recordset(['amount_paid', 'balance_due', 'bill_state'])

            # 5. Mark allocation reversed
            allocation.with_context(utility_allocation_internal=True).write({
                'state': 'reversed',
                'reversed_at': fields.Datetime.now(),
                'reversed_by': self.env.user.id,
                'reversal_reason': reason or _('عكس تخصيص مالي'),
            })
        return True

    def action_cancel(self):
        for allocation in self:
            raise ValidationError(_('لا يمكن حذف أو إلغاء سجل تخصيص مالي؛ استخدم إجراء عكس معتمد.'))

    def write(self, vals):
        protected = {
            'payment_id', 'utility_customer_id', 'sale_order_id', 'invoice_id',
            'partner_id', 'currency_id', 'requested_amount', 'allocated_amount',
            'residual_before', 'residual_after', 'allocation_date', 'source',
            'external_reference', 'state', 'partial_reconcile_ids',
            'reconciliation_reference', 'created_by', 'reversed_at',
            'reversed_by', 'reversal_reason', 'error_message',
        }
        if protected.intersection(vals) and not self.env.context.get(
                'utility_allocation_internal'):
            raise ValidationError(_('سجل تخصيص الدفعة غير قابل للتعديل بعد إنشائه.'))
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_('لا يمكن حذف سجل تخصيص مالي؛ استخدم إجراء عكس معتمد.'))
