from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityCustomerStatementWizard(models.TransientModel):
    _name = 'utility.customer.statement.wizard'
    _description = 'كشف حساب مشترك كهرباء'

    customer_id = fields.Many2one('utility.customer', string='الحساب / المشترك', required=True)
    date_from = fields.Date(string='من تاريخ')
    date_to = fields.Date(string='إلى تاريخ', default=fields.Date.context_today)
    include_draft = fields.Boolean(string='تضمين المسودات', help='تضمين الفواتير والسدادات المسودة غير المعتمدة')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'utility.customer' and self.env.context.get('active_id'):
            res.setdefault('customer_id', self.env.context['active_id'])
        return res

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('تاريخ البداية يجب أن يكون قبل أو يساوي تاريخ النهاية.'))

    def _order_domain(self, before=False):
        self.ensure_one()
        domain = [
            '|',
            ('customer_id', '=', self.customer_id.id),
            ('partner_id', '=', self.customer_id.partner_id.id),
            ('state', '!=', 'cancel'),
        ]
        if not self.include_draft:
            domain.append(('state', 'not in', ('draft', 'sent')))
        if before and self.date_from:
            domain.append(('date_order', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date_order', '>=', self.date_from))
            if self.date_to:
                domain.append(('date_order', '<=', '%s 23:59:59' % self.date_to))
        return domain

    def _payment_domain(self, before=False):
        self.ensure_one()
        domain = [
            '|',
            ('utility_sale_order_id.customer_id', '=', self.customer_id.id),
            ('partner_id', '=', self.customer_id.partner_id.id),
        ]
        if not self.include_draft:
            domain.append(('state', '=', 'posted'))
        else:
            domain.append(('state', '!=', 'cancelled'))
        if before and self.date_from:
            domain.append(('date', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', self.date_to))
        return domain

    def _writeoff_domain(self, before=False):
        self.ensure_one()
        domain = [
            '|',
            ('customer_id', '=', self.customer_id.id),
            ('sale_order_id.customer_id', '=', self.customer_id.id),
            ('state', '=', 'applied'),
        ]
        if before and self.date_from:
            domain.append(('date', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', '%s 23:59:59' % self.date_to))
        return domain

    def _settlement_domain(self, before=False):
        self.ensure_one()
        domain = [
            '|',
            ('account_id', '=', self.customer_id.id),
            ('partner_id', '=', self.customer_id.partner_id.id),
        ]
        if not self.include_draft:
            domain.append(('state', '=', 'applied'))
        else:
            domain.append(('state', '!=', 'cancelled'))

        if before and self.date_from:
            domain.append(('date', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', self.date_to))
        return domain

    def _get_opening_balance(self):
        self.ensure_one()
        # Opening balances are real posted receivable entries.  The legacy
        # partner.open_balance field is intentionally excluded from statements.
        base_opening = 0.0
        if not self.date_from:
            return base_opening
        orders = self.env['sale.order'].search(self._order_domain(before=True))
        payments = self.env['account.payment'].search(self._payment_domain(before=True))
        writeoffs = self.env['utility.writeoff'].search(self._writeoff_domain(before=True))
        settlements = self.env['utility.financial.settlement'].search(self._settlement_domain(before=True))

        settlement_debit = sum(s.amount for s in settlements if s.settlement_type == 'debit')
        settlement_credit = sum(s.amount for s in settlements if s.settlement_type == 'credit')

        return base_opening + sum(orders.mapped('amount_total')) + settlement_debit - sum(payments.mapped('amount')) - sum(writeoffs.mapped('amount')) - settlement_credit

    def _get_statement_lines(self, opening_balance=None):
        self.ensure_one()
        entries = []
        orders = self.env['sale.order'].search(self._order_domain(), order='date_order, id')
        for order in orders:
            entries.append({
                'date': order.date_order.date() if order.date_order else False,
                'sequence': order.id,
                'kind': 'invoice',
                'ref': order.name,
                'description': _('فاتورة كهرباء رقم %s') % (order.name or ''),
                'debit': order.amount_total,
                'credit': 0.0,
                'prev_reading': order.previous_reading or '',
                'curr_reading': order.current_reading or '',
                'consumption': order.consumption or '',
            })

        payments = self.env['account.payment'].search(self._payment_domain(), order='date, id')
        for payment in payments:
            pay_ref = payment.name or payment.ref or ''
            bill_ref = payment.utility_sale_order_id.name if payment.utility_sale_order_id else ''
            desc = _('سداد فاتورة %s') % bill_ref if bill_ref else _('سداد دفعة حساب')
            entries.append({
                'date': payment.date,
                'sequence': payment.id,
                'kind': 'payment',
                'ref': pay_ref,
                'description': desc,
                'debit': 0.0,
                'credit': payment.amount,
            })

        writeoffs = self.env['utility.writeoff'].search(self._writeoff_domain(), order='date, id')
        for wo in writeoffs:
            entries.append({
                'date': wo.date.date() if wo.date else False,
                'sequence': wo.id,
                'kind': 'writeoff',
                'ref': wo.writeoff_number,
                'description': _('إعفاء / شطب: %s') % (wo.reason or _('خصم معتمد')),
                'debit': 0.0,
                'credit': wo.amount,
            })

        settlements = self.env['utility.financial.settlement'].search(self._settlement_domain(), order='date, id')
        for st in settlements:
            is_debit = (st.settlement_type == 'debit')
            desc = _('تسوية مالية (%s): %s') % (_('مدين') if is_debit else _('دائن'), st.reason or '')
            entries.append({
                'date': st.date,
                'sequence': st.id,
                'kind': 'settlement',
                'ref': st.name,
                'description': desc,
                'debit': st.amount if is_debit else 0.0,
                'credit': 0.0 if is_debit else st.amount,
            })

        entries.sort(key=lambda line: (line['date'] or fields.Date.today(), line['kind'], line['sequence']))
        balance = self._get_opening_balance() if opening_balance is None else opening_balance
        for line in entries:
            balance += line['debit'] - line['credit']
            line['balance'] = balance
        return entries

    def _get_statement_totals(self):
        self.ensure_one()
        opening = self._get_opening_balance()
        lines = self._get_statement_lines(opening)
        debit = sum(line['debit'] for line in lines)
        credit = sum(line['credit'] for line in lines)
        return {
            'opening': opening,
            'debit': debit,
            'credit': credit,
            'closing': opening + debit - credit,
        }

    def _prepare_report_values(self):
        self.ensure_one()
        opening = self._get_opening_balance()
        lines = self._get_statement_lines(opening)
        debit = sum(line['debit'] for line in lines)
        credit = sum(line['credit'] for line in lines)
        closing = opening + debit - credit
        return {
            'customer': self.customer_id,
            'partner': self.customer_id.partner_id,
            'lines': lines,
            'totals': {
                'opening': opening,
                'debit': debit,
                'credit': credit,
                'closing': closing,
            },
        }

    def action_print_statement(self):
        self.ensure_one()
        # Organizational scope guard: even for read-only reports, the customer
        # must be within the acting user's scope to prevent cross-scope data leakage.
        self.env.user.check_record_scope(self.customer_id)
        return self.env.ref('utility_billing.action_report_customer_statement').report_action(self)
