from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
import hmac
import logging
from psycopg2 import IntegrityError
from odoo.addons.utility_core.models.utility_integration import sanitize_sensitive_payload

_logger = logging.getLogger(__name__)


class UtilityBillingAPI(http.Controller):

    @staticmethod
    def _error(code, message):
        """Return the stable API error envelope for all billing endpoints."""
        return {'success': False, 'code': code, 'error': message}

    @staticmethod
    def _request_params(kwargs=None):
        """Return endpoint parameters for live JSON-RPC and direct test calls.

        Odoo 16 stores the raw JSON-RPC envelope in ``request.jsonrequest``;
        the endpoint values live below its ``params`` key.  The dispatcher
        passes those values as ``kwargs`` in normal controller execution.
        Reading the raw envelope as if it were parameters silently loses every
        supplied identifier and produces false validation errors.
        """
        if kwargs:
            return kwargs
        payload = getattr(request, 'jsonrequest', None) or {}
        if not isinstance(payload, dict):
            return {}
        params = payload.get('params')
        return params if isinstance(params, dict) else payload

    def _get_authorized_accounts(self):
        """Ø¥Ø±Ø¬Ø§Ø¹ recordset Ù„Ø­Ø³Ø§Ø¨Ø§Øª Ø§Ù„ÙƒÙ‡Ø±Ø¨Ø§Ø¡ Ø§Ù„Ù…Ø³Ù…ÙˆØ­ Ù„Ù„Ù…Ø³ØªØ®Ø¯Ù… Ø§Ù„Ø­Ø§Ù„ÙŠ Ø§Ù„ÙˆØµÙˆÙ„ Ø¥Ù„ÙŠÙ‡Ø§.

        Ù„Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠÙ† Ø§Ù„Ø¯Ø§Ø®Ù„ÙŠÙŠÙ†: ÙƒÙ„ Ø§Ù„Ø­Ø³Ø§Ø¨Ø§Øª.
        Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠ Ø§Ù„Ø¨ÙˆØ§Ø¨Ø©: Ø§Ù„Ø­Ø³Ø§Ø¨Ø§Øª Ø§Ù„Ù…Ø±ØªØ¨Ø·Ø© Ø¨Ù€ partner Ø§Ù„Ø®Ø§Øµ Ø¨Ù‡Ù… ÙÙ‚Ø·.
        """
        user = request.env.user
        Customer = request.env['utility.customer']
        if user.has_group('base.group_user'):
            # Internal calls deliberately use the normal environment so ACLs
            # and ir.rules remain the single authorization source of truth.
            return Customer.search([])
        return Customer.sudo().search([
            ('partner_id', '=', user.partner_id.id),
        ])

    def _authorize_account(self, customer_number):
        """Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ù…Ù„ÙƒÙŠØ© Ø­Ø³Ø§Ø¨ Ø§Ù„ÙƒÙ‡Ø±Ø¨Ø§Ø¡ ÙˆØ¥Ø±Ø¬Ø§Ø¹Ù‡ Ø¥Ù† ÙˆØ¬Ø¯."""
        accounts = self._get_authorized_accounts()
        return accounts.filtered(lambda a: a.customer_number == customer_number)[:1]

    def _resolve_authorized_customer(self, params):
        """Resolve exact customer identifiers within the caller's access scope."""
        accounts = self._get_authorized_accounts()
        customer, error_code = accounts._resolve_identifiers(
            customer_id=params.get('customer_id'),
            customer_number=params.get('customer_number'),
            external_qr_reference=params.get('external_qr_reference'),
            meter_id=params.get('meter_id'),
            meter_number=params.get('meter_number'),
            operational_number=params.get('operational_number'),
            lookup_value=params.get('lookup_value'),
            scope_ids=accounts.ids,
        )
        return customer, error_code

    @staticmethod
    def _customer_payload(customer):
        return {
            'customer_id': customer.id,
            'customer_number': customer.customer_number,
            'external_qr_reference': customer.external_qr_reference or None,
            'customer_name': customer.partner_id.name if customer.partner_id else None,
        }

    @http.route('/api/v1/utility/customer/lookup', type='json', auth='user', methods=['POST'])
    def customer_lookup(self, **kwargs):
        """Resolve an authorized customer by exact business identifier."""
        customer, error_code = self._resolve_authorized_customer(
            self._request_params(kwargs))
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'Ù…Ø¹Ø±ÙØ§Øª Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø§Ø±Ø¶Ø©')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(
                error_code,
                'A customer, meter, QR, or lookup identifier is required',
            )
        if error_code == 'CUSTOMER_IDENTIFIER_AMBIGUOUS':
            return self._error(error_code, 'Ø§Ù„Ù…Ø¹Ø±Ù Ø§Ù„Ù…Ø¯Ø®Ù„ ÙŠØ·Ø§Ø¨Ù‚ Ø£ÙƒØ«Ø± Ù…Ù† Ø­Ø³Ø§Ø¨.')
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'Ø§Ù„Ø­Ø³Ø§Ø¨ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯')
        return {'success': True, 'customer': self._customer_payload(customer)}

    @http.route('/api/v1/utility/customer/qr_reference', type='json', auth='user', methods=['POST'])
    def update_customer_qr_reference(self, **kwargs):
        """Assign or change the current external QR reference idempotently."""
        params = self._request_params(kwargs)
        customer, error_code = self._resolve_authorized_customer(params)
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'Ù…Ø¹Ø±ÙØ§Øª Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…ØªØ¹Ø§Ø±Ø¶Ø©')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(
                error_code,
                'customer_id, customer_number or external_qr_reference is required',
            )
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'Ø§Ù„Ø­Ø³Ø§Ø¨ ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯')
        target_key = (
            'new_external_qr_reference'
            if 'new_external_qr_reference' in params
            else 'external_qr_reference'
        )
        if target_key not in params:
            return self._error('VALIDATION_ERROR', 'external_qr_reference is required')

        reference = (params.get(target_key) or '').strip() or False
        owner = request.env['utility.customer']
        if reference:
            owner = owner.search([
                ('external_qr_reference', '=', reference),
                ('company_id', '=', customer.company_id.id),
                ('id', '!=', customer.id),
        ], limit=1)
        if owner:
            return self._error(
                'QR_REFERENCE_ALREADY_ASSIGNED',
                'Ù…Ø¹Ø±Ù QR Ø§Ù„Ø®Ø§Ø±Ø¬ÙŠ Ù…Ø³ØªØ®Ø¯Ù… Ø¨Ø§Ù„ÙØ¹Ù„ Ù„Ø¯Ù‰ Ø­Ø³Ø§Ø¨ Ø¢Ø®Ø±',
            )
        try:
            with request.env.cr.savepoint():
                customer.write({'external_qr_reference': reference})
        except IntegrityError:
            return self._error(
                'QR_REFERENCE_ALREADY_ASSIGNED',
                'Ù…Ø¹Ø±Ù QR Ø§Ù„Ø®Ø§Ø±Ø¬ÙŠ Ù…Ø³ØªØ®Ø¯Ù… Ø¨Ø§Ù„ÙØ¹Ù„ Ù„Ø¯Ù‰ Ø­Ø³Ø§Ø¨ Ø¢Ø®Ø±',
            )
        return {'success': True, 'customer': self._customer_payload(customer)}

    def _authorize_order(self, order_id):
        """Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ù…Ù„ÙƒÙŠØ© Ø§Ù„ÙØ§ØªÙˆØ±Ø© ÙˆØ¥Ø±Ø¬Ø§Ø¹Ù‡Ø§ Ø¶Ù…Ù† Ù†Ø·Ø§Ù‚ Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… Ø§Ù„Ù…ØµØ±Ø­ Ù„Ù‡.

        Ù„Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠÙ† Ø§Ù„Ø¯Ø§Ø®Ù„ÙŠÙŠÙ† ØªÙØ·Ø¨Ù‘Ù‚ Record Rules ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ø¹Ø¨Ø± Ø¨ÙŠØ¦Ø© ORM Ø§Ù„Ø¹Ø§Ø¯ÙŠØ©ØŒ
        ÙˆÙŠÙØ¶Ø§Ù Ø´Ø±Ø· Ù…Ù„ÙƒÙŠØ© Ø§Ù„Ø­Ø³Ø§Ø¨ Ø¨ÙˆØµÙÙ‡ Ù‚ÙŠØ¯Ø§Ù‹ Ø®Ø§ØµØ§Ù‹ Ø¨Ø§Ù„Ù€ endpoint.
        Ù„Ù…Ø³ØªØ®Ø¯Ù…ÙŠ Ø§Ù„Ø¨ÙˆØ§Ø¨Ø© ÙŠÙØ³ØªØ®Ø¯Ù… sudo Ù„Ù‚Ø±Ø§Ø¡Ø© Ø§Ù„ÙØ§ØªÙˆØ±Ø© Ø¨Ø¹Ø¯ Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ù…Ù„ÙƒÙŠØ©.
        """
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return request.env['sale.order']
        authorized_accounts = self._get_authorized_accounts()
        # Authorization first: ORM Record Rules enforce org scope for internal users
        # + explicit customer ownership check for both internal and portal principals.
        # Do NOT use sudo().browse() before authorization.
        Order = request.env['sale.order']
        order = Order.search([
            ('id', '=', order_id),
            ('customer_id', 'in', authorized_accounts.ids),
        ], limit=1)
        return order

    def _get_current_collector(self):
        """Return the authenticated field collector, or fail closed.

        The endpoint performs financial writes with a deliberately scoped
        sudo after this check because a field collector is not an Accounting
        user.  The selected staff member and the collector cash journal are
        nevertheless enforced again by ``account.payment`` on creation.
        """
        user = request.env.user
        if not user.has_group('utility_core.group_utility_collector'):
            return False, self._error(
                'COLLECTOR_ROLE_REQUIRED',
                'This operation is restricted to field collectors.',
            )
        # Odoo groups on res.users are the sole functional-authorization
        # source.  utility.staff remains a linked custody/operational profile,
        # never a second role authority.
        collector = request.env['utility.staff'].sudo().search([
            ('user_id', '=', user.id),
            ('company_id', '=', request.env.company.id),
            ('active', '=', True),
        ], limit=1)
        if not collector:
            return False, self._error(
                'COLLECTOR_PROFILE_MISSING',
                'No active field-collector profile is configured for this user.',
            )
        if not collector.collection_journal_id:
            journal = collector.sudo()._ensure_collector_cash_journal()
            if not journal:
                return False, self._error(
                    'COLLECTOR_CASH_JOURNAL_MISSING',
                    'A dedicated cash journal must be configured for this collector.',
                )
        return collector, False

    def _get_collector_scope_accounts(self):
        """Return utility customers that the current collector can work on.

        This keeps the mobile collector list aligned with the route assignment
        model used by the reader endpoint.  Global utility users keep their
        normal record-rule scope; restricted collectors must have assigned
        routes and only receive accounts on those routes.
        """
        user = request.env.user
        accounts = self._get_authorized_accounts()
        if not user.has_group('utility_core.group_utility_collector'):
            return request.env['utility.customer']
        if user._is_global_utility_scope():
            return accounts
        routes = user.sudo().assigned_route_ids
        if not routes:
            return request.env['utility.customer']
        return accounts.filtered(lambda account: account.route_id in routes)

    @staticmethod
    def _collection_receipt_payload(payment, collection, duplicate=False):
        allocations = payment.allocation_ids.filtered(
            lambda allocation: allocation.state == 'reconciled')
        allocated_amount = sum(allocations.mapped('allocated_amount'))
        return {
            'success': True,
            'duplicate': duplicate,
            'payment_id': payment.id,
            'collection_id': collection.id,
            'reference': collection.name or payment.name,
            'payment_reference': payment.name,
            'amount': payment.amount,
            'allocated_amount': allocated_amount,
            'unapplied_credit': max(payment.amount - allocated_amount, 0.0),
            'allocation_count': len(allocations),
            'paid_at': fields.Datetime.to_string(collection.collection_date),
            'state': collection.state,
        }

    def _collector_account_payload(self, customer):
        """Return a live, payable-invoice view for one already-authorized account."""
        orders = request.env['sale.order'].search([
            ('customer_id', '=', customer.id),
            ('state', '!=', 'cancel'),
        ], order='date_order desc, id desc')
        bills = []
        for order in orders:
            # The customer and sale order were resolved with the caller's
            # normal ACL/rules.  Invoice data is read only through this exact,
            # already-authorized bill; no client-supplied invoice is browsed.
            invoices = order.sudo()._get_posted_utility_moves().filtered(
                lambda move: move.move_type == 'out_invoice'
                and move.amount_residual > 0)
            for invoice in invoices:
                due_date = order.date_order.date().isoformat() if order.date_order else None
                bills.append({
                    'order_id': order.id,
                    'invoice_id': invoice.id,
                    'bill_number': order.name,
                    'invoice_number': invoice.name,
                    'amount': invoice.amount_total,
                    'amount_residual': invoice.amount_residual,
                    'due_date': due_date,
                    'state': order.bill_state,
                    'overdue': bool(order.is_overdue),
                })
        total_due = sum(bill['amount_residual'] for bill in bills)
        current_bill = bills[0]['amount_residual'] if bills else 0.0
        debt_amount = max(total_due - current_bill, 0.0)
        meter = customer.meter_id
        return {
            'success': True,
            'account': {
                **self._customer_payload(customer),
                'account_number': customer.customer_number,
                'meter_number': meter.meter_number if meter else None,
                'meter_id': meter.id if meter else None,
                # The account state is the supported operational connection
                # status in V1; utility.meter has no independent
                # ``connection_status`` field.
                'connection_status': customer.state,
                'accounting_balance': customer.accounting_balance,
                'due_amount': total_due,
                'current_bill': current_bill,
                'debt_amount': debt_amount,
                'allow_partial': True,
                'bills': bills,
            },
        }

    @http.route('/api/v1/utility/collector/account', type='json', auth='user', methods=['POST'])
    def collector_account(self, **kwargs):
        """Look up one account and its actual payable invoice targets."""
        _collector, error = self._get_current_collector()
        if error:
            return error
        customer, error_code = self._resolve_authorized_customer(
            self._request_params(kwargs))
        if error_code == 'CUSTOMER_IDENTIFIER_MISMATCH':
            return self._error(error_code, 'Customer identifiers conflict.')
        if error_code == 'CUSTOMER_IDENTIFIER_REQUIRED':
            return self._error(error_code, 'A customer identifier is required.')
        if error_code == 'CUSTOMER_IDENTIFIER_AMBIGUOUS':
            return self._error(error_code, 'The supplied identifier matches more than one account.')
        if not customer:
            return self._error(error_code or 'CUSTOMER_NOT_FOUND', 'Account not found.')
        return self._collector_account_payload(customer)

    @http.route('/api/v1/utility/collector/collect_cash', type='json', auth='user', methods=['POST'])
    def collector_collect_cash(self, **kwargs):
        """Post one idempotent field cash collection.

        The posted payment remains a partner receivable item. Allocation
        settles the selected current invoice first and then prior receivables.

        A successful response exists only after Odoo posted the payment,
        reconciled it against the selected invoice, and created the collector
        custody record.  It intentionally does not queue or print an
        unacknowledged financial transaction on the device.
        """
        params = self._request_params(kwargs)
        collector, error = self._get_current_collector()
        if error:
            return error
        request_key = (params.get('idempotency_key') or '').strip()
        if len(request_key) < 8 or len(request_key) > 128:
            return self._error(
                'INVALID_IDEMPOTENCY_KEY',
                'idempotency_key must contain 8 to 128 characters.',
            )
        try:
            order_id = int(params.get('order_id'))
            invoice_id = int(params.get('invoice_id'))
            amount = float(params.get('amount'))
        except (TypeError, ValueError):
            return self._error(
                'VALIDATION_ERROR',
                'order_id, invoice_id and a positive numeric amount are required.',
            )
        if amount <= 0:
            return self._error('VALIDATION_ERROR', 'amount must be positive.')

        order = self._authorize_order(order_id)
        if not order:
            return self._error('ORDER_NOT_FOUND', 'Bill not found in your assigned scope.')
        if order.company_id != collector.company_id:
            return self._error('COMPANY_MISMATCH', 'The bill is not in the collector company.')

        authorized_invoices = order.sudo()._get_posted_utility_moves().filtered(
            lambda move: move.id == invoice_id and move.move_type == 'out_invoice')
        if not authorized_invoices:
            return self._error(
                'INVALID_INVOICE',
                'The selected invoice does not belong to this bill or is not posted.',
            )
        invoice = authorized_invoices[:1]
        customer = order.customer_id

        # Older migrated accounting moves can carry the validated utility bill
        # link while the denormalized customer link is empty.  The payment
        # allocator deliberately requires both links so it can never reconcile
        # a payment to a different electricity account.  Repair only that
        # narrowly-defined legacy case after proving that the order and partner
        # already identify the same customer; never overwrite a conflicting
        # customer link.
        if not invoice.utility_customer_id:
            if invoice.partner_id != customer.partner_id:
                return self._error(
                    'INVOICE_CUSTOMER_MISMATCH',
                    'The selected invoice partner does not match the electricity account.',
                )
            invoice.sudo().write({'utility_customer_id': customer.id})
        elif invoice.utility_customer_id != customer:
            return self._error(
                'INVOICE_CUSTOMER_MISMATCH',
                'The selected invoice belongs to a different electricity account.',
            )

        Payment = request.env['account.payment'].sudo().with_company(order.company_id)
        existing = Payment.search([
            ('company_id', '=', order.company_id.id),
            ('collection_request_key', '=', request_key),
        ], limit=1)
        if existing:
            if (existing.collector_id != collector
                    or existing.utility_sale_order_id != order
                    or existing.utility_invoice_id != invoice
                    or existing.amount != amount):
                return self._error(
                    'IDEMPOTENCY_KEY_REUSED',
                    'This idempotency key belongs to a different collection request.',
                )
            # A previous request may have created a draft payment before this
            # Odoo 18 migration repair was deployed.  Its source order is
            # already verified above, so backfill only an absent computed
            # customer link and let the same idempotency key resume safely.
            if not existing.utility_customer_id:
                existing.write({'utility_customer_id': customer.id})
            elif existing.utility_customer_id != customer:
                return self._error(
                    'PAYMENT_CUSTOMER_MISMATCH',
                    'The original collection request belongs to a different electricity account.',
                )
            collection = request.env['utility.collection'].sudo().search(
                [('payment_id', '=', existing.id)], limit=1)
            if not existing._is_utility_posted():
                try:
                    # Keep the posting and its allocation/custody side effects
                    # atomic.  A failed retry must not leave a draft payment
                    # that permanently reserves this idempotency key.
                    with request.env.cr.savepoint():
                        existing.action_post()
                except (AccessError, UserError, ValidationError) as exc:
                    _logger.warning(
                        'collect_cash retry rejected key=%s order=%s invoice=%s: %s',
                        request_key, order.id, invoice.id, exc, exc_info=True,
                    )
                    existing.invalidate_recordset()
                    collection = request.env['utility.collection'].sudo().search(
                        [('payment_id', '=', existing.id)], limit=1)
                    allocations = request.env['utility.payment.allocation'].sudo().search(
                        [('payment_id', '=', existing.id)], limit=1)
                    # A draft without any accounting move, allocation, or
                    # custody record was left by an older failed request and
                    # is safe to discard.  Posted or otherwise evidenced
                    # financial artifacts are never deleted here.
                    if (existing.state == 'draft' and not existing.move_id
                            and not collection and not allocations):
                        existing.unlink()
                    return self._error(
                        'COLLECTION_REJECTED', str(exc),
                    )
                collection = request.env['utility.collection'].sudo().search(
                    [('payment_id', '=', existing.id)], limit=1)
            if not collection:
                allocation = request.env['utility.payment.allocation'].sudo().allocate_payment(existing)
                if existing.utility_sale_order_id and allocation:
                    existing._create_field_collection_from_allocation(allocation)
                collection = request.env['utility.collection'].sudo().search(
                    [('payment_id', '=', existing.id)], limit=1)
            if not collection or not existing._is_utility_posted():
                return self._error(
                    'COLLECTION_IN_PROGRESS',
                    'The original collection request is still being processed.',
                )
            return self._collection_receipt_payload(existing, collection, duplicate=True)

        method_line = collector.collection_journal_id.inbound_payment_method_line_ids[:1]
        if not method_line:
            return self._error(
                'COLLECTOR_PAYMENT_METHOD_MISSING',
                'No inbound payment method is configured on the collector cash journal.',
            )
        cash_account = collector.collection_journal_id.default_account_id
        if cash_account and method_line.payment_account_id != cash_account:
            method_line.sudo().write({'payment_account_id': cash_account.id})
        try:
            with request.env.cr.savepoint():
                payment = Payment.create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'amount': amount,
                    'currency_id': invoice.currency_id.id,
                    'journal_id': collector.collection_journal_id.id,
                    'utility_sale_order_id': order.id,
                    # Set this explicitly as well as through the stored
                    # compute.  It avoids an incomplete-payment window while
                    # Odoo evaluates create constraints for migrated data.
                    'utility_customer_id': customer.id,
                    'utility_invoice_id': invoice.id,
                    'utility_payment_method': 'cash',
                    'collector_id': collector.id,
                    'payment_method_line_id': method_line.id,
                    'collection_request_key': request_key,
                    'collection_request_user_id': request.env.user.id,
                })
                # ``action_post`` creates the exact allocation and the field
                # custody record.  It must share the creation savepoint so a
                # validation failure rolls back the draft payment as well.
                payment.action_post()
        except IntegrityError as exc:
            if getattr(exc, 'pgcode', None) != '23505':
                raise
            payment = Payment.search([
                ('company_id', '=', order.company_id.id),
                ('collection_request_key', '=', request_key),
            ], limit=1)
            if not payment:
                raise
            collection = request.env['utility.collection'].sudo().search(
                [('payment_id', '=', payment.id)], limit=1)
            if not payment._is_utility_posted():
                try:
                    with request.env.cr.savepoint():
                        payment.action_post()
                except (AccessError, UserError, ValidationError) as exc:
                    _logger.warning(
                        'collect_cash concurrent retry rejected key=%s order=%s invoice=%s: %s',
                        request_key, order.id, invoice.id, exc, exc_info=True,
                    )
                    payment.invalidate_recordset()
                    collection = request.env['utility.collection'].sudo().search(
                        [('payment_id', '=', payment.id)], limit=1)
                    allocations = request.env['utility.payment.allocation'].sudo().search(
                        [('payment_id', '=', payment.id)], limit=1)
                    if (payment.state == 'draft' and not payment.move_id
                            and not collection and not allocations):
                        payment.unlink()
                    return self._error('COLLECTION_REJECTED', str(exc))
                collection = request.env['utility.collection'].sudo().search(
                    [('payment_id', '=', payment.id)], limit=1)
            if not collection:
                allocation = request.env['utility.payment.allocation'].sudo().allocate_payment(payment)
                if payment.utility_sale_order_id and allocation:
                    payment._create_field_collection_from_allocation(allocation)
                collection = request.env['utility.collection'].sudo().search(
                    [('payment_id', '=', payment.id)], limit=1)
            if payment._is_utility_posted() and collection:
                return self._collection_receipt_payload(payment, collection, duplicate=True)
            return self._error('COLLECTION_IN_PROGRESS', 'The original request is still being processed.')

        except (AccessError, UserError, ValidationError) as exc:
            _logger.warning(
                'collect_cash rejected key=%s order=%s invoice=%s: %s',
                request_key, order.id, invoice.id, exc, exc_info=True,
            )
            return self._error('COLLECTION_REJECTED', str(exc))
        collection = request.env['utility.collection'].sudo().search(
            [('payment_id', '=', payment.id)], limit=1)
        if (not payment._is_utility_posted()
                or not collection or collection.state != 'posted'):
            # This indicates an unexpected programming/configuration fault.
            # It must roll back rather than create a receipt for partial work.
            raise ValidationError('Field collection did not reach a posted custody state.')
        return self._collection_receipt_payload(payment, collection)

    @http.route('/api/v1/utility/billing/balance', type='json', auth='user', methods=['POST'])
    def billing_balance(self, **kwargs):
        params = self._request_params(kwargs)
        customer_number = params.get('customer_number')
        if not customer_number:
            return self._error('VALIDATION_ERROR', 'customer_number is required')
        account = self._authorize_account(customer_number)
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Account not found')
        orders = request.env['sale.order'].sudo().search([
            ('customer_id', '=', account.id),
            ('bill_state', 'not in', ('paid', 'cancelled')),
        ])
        debt = sum(orders.mapped('balance_due'))
        return {
            'customer_number': account.customer_number,
            'accounting_balance': account.accounting_balance,
            'debt': debt,
            'last_purchase_date': account.last_purchase_date.isoformat() if account.last_purchase_date else None,
        }

    @http.route('/api/v1/utility/billing/bills', type='json', auth='user', methods=['POST'])
    def billing_bills(self, **kwargs):
        params = self._request_params(kwargs)
        customer_number = params.get('customer_number')
        limit = params.get('limit', 12)
        if not customer_number:
            return self._error('VALIDATION_ERROR', 'customer_number is required')
        account = self._authorize_account(customer_number)
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Account not found')
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            return self._error('INVALID_LIMIT', 'limit must be numeric')
        orders = request.env['sale.order'].sudo().search([
            ('customer_id', '=', account.id),
        ], order='date_order desc', limit=limit)
        return {
            'bills': [{
                'bill_number': o.name,
                'period': '%s - %s' % (o.period_start, o.period_end) if o.period_start and o.period_end else None,
                'amount': o.amount_total,
                'paid': o.amount_paid,
                'balance': o.balance_due,
                'due_date': o.date_order.date().isoformat() if o.date_order else None,
                'state': o.bill_state,
            } for o in orders],
        }

    @http.route('/api/v1/utility/billing/pay', type='json', auth='user', methods=['POST'])
    def billing_pay(self, **kwargs):
        """ØªÙ… ØªØ¹Ø·ÙŠÙ„ Ø§Ù„Ø¯ÙØ¹ Ø§Ù„Ù…Ø¨Ø§Ø´Ø± Ù…Ù† Ø§Ù„Ø¨ÙˆØ§Ø¨Ø©. Ø§Ø³ØªØ®Ø¯Ù… /api/v1/utility/billing/payment_intent Ø¨Ø¯Ù„Ø§Ù‹ Ù…Ù†Ù‡."""
        return self._error(
            'ENDPOINT_DISABLED',
            'Direct payment creation is disabled. Use /api/v1/utility/billing/payment_intent instead.',
        )

    @http.route('/api/v1/utility/billing/payment_intent', type='json', auth='user', methods=['POST'])
    def billing_payment_intent(self, **kwargs):
        params = self._request_params(kwargs)
        order_id = params.get('order_id')
        amount = params.get('amount')
        provider_id = params.get('provider_id')
        invoice_id = params.get('invoice_id')
        direction = params.get('payment_direction', 'inbound')
        if direction != 'inbound':
            return self._error(
                'INVALID_PAYMENT_DIRECTION',
                'Customer payment intents support inbound payments only',
            )

        if not order_id or not amount:
            return self._error('VALIDATION_ERROR', 'order_id and amount are required')
        order = self._authorize_order(order_id)
        if not order:
            return self._error('ORDER_NOT_FOUND', 'Order not found')
        posted_moves = order._get_posted_utility_moves()
        if invoice_id:
            try:
                invoice_id = int(invoice_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'invoice_id must be numeric')
            invoice = request.env['account.move'].sudo().browse(invoice_id).exists()
            if (not invoice or len(invoice) != 1 or invoice not in posted_moves
                    or invoice.partner_id != order.partner_id):
                return self._error(
                    'INVALID_INVOICE',
                    'invoice_id must identify a posted accounting invoice of this bill',
                )
        elif len(posted_moves) == 1:
            invoice = posted_moves
        else:
            return self._error(
                'INVOICE_REQUIRED',
                'invoice_id is required when the bill has multiple accounting invoices',
            )
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'amount must be a positive number')
        if amount <= 0:
            return self._error('VALIDATION_ERROR', 'amount must be a positive number')

        if direction == 'inbound':
            if amount > invoice.amount_residual:
                return self._error(
                    'AMOUNT_EXCEEDS_RESIDUAL',
                    'amount cannot exceed the selected invoice residual',
                )
            if order.bill_state in ('paid', 'cancelled'):
                return self._error('BILL_NOT_PAYABLE', 'Bill is not payable')

        Provider = request.env['utility.integration.provider'].sudo()
        if provider_id:
            try:
                provider_id = int(provider_id)
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'provider_id must be numeric')
            provider = Provider.browse(provider_id)
        else:
            provider = Provider.search([
                ('is_payment_capable', '=', True),
                ('payment_direction', 'in', (direction, 'both')),
                ('active', '=', True),
                ('company_id', '=', order.company_id.id),
            ], limit=1)

        if not provider or not provider.active or not provider.is_payment_capable:
            return self._error(
                'PAYMENT_PROVIDER_UNAVAILABLE',
                'No active payment provider configured for the requested operation',
            )
        if not provider.supports_direction(direction):
            return self._error(
                'PAYMENT_DIRECTION_UNSUPPORTED',
                'Provider %s does not support payment direction: %s' % (provider.name, direction),
            )
        if provider.company_id and provider.company_id != order.company_id:
            return self._error(
                'PAYMENT_PROVIDER_COMPANY_MISMATCH',
                'Payment provider is not available for the bill company',
            )

        tx = request.env['utility.payment.gateway.transaction'].sudo().create({
            'provider_id': provider.id,
            'payment_direction': direction,
            'sale_order_id': order.id,
            'utility_invoice_id': invoice.id,
            'amount': amount,
        })
        tx.action_mark_pending()
        return {
            'transaction_id': tx.id,
            'reference': tx.name,
            'payment_direction': tx.payment_direction,
            'state': tx.state,
            'amount': tx.amount,
        }

    @http.route('/api/v1/utility/payment_gateway/webhook/<string:reference>', type='json', auth='public', methods=['POST'], csrf=False)
    def payment_gateway_webhook(self, reference, **kwargs):
        params = self._request_params(kwargs)
        # 1. Search transaction by reference WITHOUT locking first
        tx = request.env['utility.payment.gateway.transaction'].sudo().search([
            ('name', '=', reference),
        ], limit=1)
        if not tx:
            return self._error('TRANSACTION_NOT_FOUND', 'Transaction not found')

        # 2. Verify callback token BEFORE acquiring DB row-level lock
        token = params.get('token') or params.get('callback_token') or params.get('signature')
        if not token or not tx.access_token:
            _logger.warning('Payment webhook missing token for reference %s', reference)
            return self._error('AUTHENTICATION_REQUIRED', 'Missing authentication token')
        expected = tx.access_token.encode('utf-8')
        received = token.encode('utf-8')
        if len(expected) != len(received) or not hmac.compare_digest(expected, received):
            _logger.warning('Payment webhook invalid token for reference %s', reference)
            return self._error('INVALID_TOKEN', 'Invalid token')

        # 3. Acquire FOR UPDATE row-level lock ONLY AFTER authentication succeeds
        request.env.cr.execute(
            "SELECT id FROM utility_payment_gateway_transaction WHERE name = %s FOR UPDATE",
            [reference]
        )
        tx.invalidate_recordset(['state', 'payment_id', 'callback_payload', 'error_message'])

        status = params.get('status')
        if not status:
            return self._error('VALIDATION_ERROR', 'Payment status is required')
        provider_reference = params.get('provider_reference') or params.get('reference')
        if tx.state == 'done':
            return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id if tx.payment_id else False}
        if tx.state != 'pending':
            return self._error(
                'INVALID_TRANSACTION_STATE',
                'Only pending payment transactions can receive callbacks',
            )
        if status in ('success', 'done', 'paid') and not provider_reference:
            return self._error(
                'VALIDATION_ERROR',
                'Provider reference is required for successful payments',
            )
        sanitized_params = str(sanitize_sensitive_payload(params))
        if status not in ('success', 'done', 'paid'):
            tx.write({
                'state': 'failed',
                'callback_payload': sanitized_params,
                'error_message': params.get('error') or 'Payment gateway reported failure',
            })
            error_response = self._error(
                'PAYMENT_FAILED',
                params.get('error') or 'Payment gateway reported failure',
            )
            error_response['state'] = tx.state
            return error_response
        tx.action_confirm_payment(provider_reference=provider_reference, callback_payload=sanitized_params)
        return {'success': True, 'state': tx.state, 'payment_id': tx.payment_id.id if tx.payment_id else False}

    @http.route('/api/v1/utility/operations/service_request', type='json', auth='user', methods=['POST'])
    def service_request(self, **kwargs):
        """Ø¥Ù†Ø´Ø§Ø¡ Ø·Ù„Ø¨ Ø®Ø¯Ù…Ø©.  Ø§Ù„ØªÙÙˆÙŠØ¶ ÙŠØ³Ø¨Ù‚ Ø£ÙŠ ÙˆØµÙˆÙ„ Ù„Ù„Ø³Ø¬Ù„:
        - Ù†Ø­Ø¯Ø¯ Ø£ÙˆÙ„Ø§Ù‹ Ø§Ù„Ø­Ø³Ø§Ø¨Ø§Øª Ø§Ù„Ù…ØµØ±Ø­ Ø¨Ù‡Ø§ Ù„Ù‡Ø°Ø§ Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… (ORM Record Rules + Ù…Ù„ÙƒÙŠØ© Ø­Ø³Ø§Ø¨).
        - Ù†Ø¨Ø­Ø« Ø¶Ù…Ù† ØªÙ„Ùƒ Ø§Ù„Ø­Ø³Ø§Ø¨Ø§Øª ÙÙ‚Ø· â€” Ù„Ø§ sudo().browse() Ù‚Ø¨Ù„ Ø§Ù„ØªÙÙˆÙŠØ¶.
        - Ø¨Ø¹Ø¯ Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ù‡ÙˆÙŠØ© ÙˆØ§Ù„Ù…Ù„ÙƒÙŠØ©ØŒ ÙŠÙÙ†Ø´Ø£ Ø£Ù…Ø± Ø§Ù„Ø®Ø¯Ù…Ø©.
        """
        params = self._request_params(kwargs)
        customer_id = params.get('customer_id')
        service_type = params.get('service_type')
        description = params.get('description')
        if not customer_id or not service_type or not description:
            return self._error(
                'VALIDATION_ERROR',
                'customer_id, service_type, and description are required',
            )
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'customer_id must be numeric')
        # Authorization FIRST: search within authorized scope, no sudo() before auth.
        authorized = self._get_authorized_accounts()
        account = authorized.filtered(lambda c: c.id == customer_id)[:1]
        if not account:
            return self._error('CUSTOMER_NOT_FOUND', 'Customer account not found')
        try:
            order = request.env['utility.service.order'].sudo().create({
                'customer_id': account.id,
                'service_type': service_type,
                'description': description,
                'state': 'draft',
            })
            return {'order_number': order.order_number}
        except KeyError:
            return self._error('MODEL_UNAVAILABLE', 'utility.service.order model not available')

    @http.route('/api/v1/utility/reports/daily', type='json', auth='user', methods=['POST'])
    def reports_daily(self, **kwargs):
        from datetime import date
        params = self._request_params(kwargs)
        report_date = params.get('date', date.today().isoformat())
        region_id = params.get('region_id')
        area_id = params.get('area_id')
        user = request.env.user
        if not user.has_group('base.group_user'):
            return self._error(
                'ACCESS_DENIED',
                'Access denied. Reports are for internal users only.',
            )
        allowed_accounts = self._get_authorized_accounts()
        allowed_ids = allowed_accounts.ids
        if not allowed_ids:
            return {'total_bills': 0, 'total_collections': 0.0, 'active_alarms': 0}
        start_dt = '%s 00:00:00' % report_date
        end_dt = '%s 23:59:59' % report_date

        bills_domain = [
            ('customer_id', 'in', allowed_ids),
            ('date_order', '>=', start_dt),
            ('date_order', '<=', end_dt),
        ]
        if region_id:
            try:
                bills_domain.append(('customer_id.region_id', '=', int(region_id)))
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'region_id must be numeric')
        if area_id:
            try:
                bills_domain.append(('customer_id.area_id', '=', int(area_id)))
            except (TypeError, ValueError):
                return self._error('VALIDATION_ERROR', 'area_id must be numeric')
        total_bills = request.env['sale.order'].search_count(bills_domain)

        payments_domain = [
            ('date', '=', report_date),
            ('utility_sale_order_id.customer_id', 'in', allowed_ids),
        ]
        pay_data = request.env['account.payment'].read_group(
            payments_domain, ['amount:sum'], [])
        total_collections = pay_data[0].get('amount', 0) if pay_data else 0.0

        alarms_domain = [
            ('customer_id', 'in', allowed_ids),
            ('alarm_date', '>=', start_dt), ('alarm_date', '<=', end_dt),
            ('state', 'not in', ('resolved', 'dismissed')),
        ]
        active_alarms = request.env['utility.alarm'].search_count(alarms_domain)

        return {
            'total_bills': total_bills,
            'total_collections': total_collections,
            'active_alarms': active_alarms,
        }


    @http.route('/api/v1/utility/collector/period/invoices', type='json', auth='user', methods=['POST'])
    def collector_period_invoices(self, **kwargs):
        collector, error = self._get_current_collector()
        if error:
            return error

        params = self._request_params(kwargs)
        try:
            limit = int(params.get('limit', 0) or 0)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'limit must be numeric')
        try:
            offset = int(params.get('offset', 0) or 0)
        except (TypeError, ValueError):
            return self._error('VALIDATION_ERROR', 'offset must be numeric')

        period = request.env['date.range'].search([
            ('collection_state', 'in', ('open', 'closing')),
            '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
        ], order='date_start desc', limit=1)
        if not period:
            period = request.env['date.range'].search([
                ('period_role', '=', 'payment'),
                ('state', '=', 'open'),
                '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
            ], order='date_start desc', limit=1)

        if not period:
            return {'success': True, 'period': None, 'invoices': []}

        period_data = {
            'id': period.id,
            'name': period.name,
            'state': period.state,
        }

        authorized_accounts = self._get_collector_scope_accounts()
        if not authorized_accounts:
            return {'success': True, 'period': period_data, 'invoices': []}

        # The collector home page is also the invoice list for the active
        # collection period.  Do not limit it to unpaid moves: a collector
        # must see paid invoices too, with their real status, so that the
        # mobile list matches the billing period in Odoo and does not look
        # empty after most invoices have been collected.
        #
        # New invoices always carry ``utility_customer_id``.  The second
        # branch keeps migrated invoices visible when that stored link is
        # absent but the linked utility sale order is valid.
        domain = [
            ('company_id', '=', collector.company_id.id),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('utility_sale_order_id', '!=', False),
            '|',
            ('utility_customer_id', 'in', authorized_accounts.ids),
            ('utility_sale_order_id.customer_id', 'in', authorized_accounts.ids),
        ]

        reading_period = period.reading_period_id
        if reading_period:
            domain.append(('utility_sale_order_id.date_range_id', '=', reading_period.id))

        invoices = request.env['account.move'].sudo().search(
            domain,
            order='invoice_date desc, id desc',
            limit=limit or None,
            offset=max(offset, 0),
        )

        customer_ids = (invoices.mapped('utility_customer_id') |
                        invoices.mapped('utility_sale_order_id.customer_id')).ids
        open_by_customer = {}
        if customer_ids:
            open_moves = request.env['account.move'].sudo().search([
                ('company_id', '=', collector.company_id.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('amount_residual', '>', 0),
                '|',
                ('utility_customer_id', 'in', customer_ids),
                ('utility_sale_order_id.customer_id', 'in', customer_ids),
            ])
            for open_move in open_moves:
                open_customer = (open_move.utility_customer_id
                                 or open_move.utility_sale_order_id.customer_id)
                if open_customer:
                    open_by_customer.setdefault(open_customer.id, 0.0)
                    open_by_customer[open_customer.id] += open_move.amount_residual

        invoice_list = []
        for inv in invoices:
            order = inv.utility_sale_order_id
            customer = inv.utility_customer_id or order.customer_id
            if not customer:
                # Defensive guard for malformed historic accounting moves.
                # Such records must not be exposed without a validated
                # customer scope.
                continue
            meter = order.meter_id if order else False
            total_due = open_by_customer.get(customer.id, inv.amount_residual)
            invoice_list.append({
                'customer_id': customer.id,
                'customer_number': customer.customer_number,
                # The mobile app keeps an ``account_number`` key for display
                # compatibility, but ``utility.customer`` stores the account
                # identifier as ``customer_number``.
                'account_number': customer.customer_number,
                'customer_name': customer.partner_id.name if customer.partner_id else '',
                'meter_id': meter.id if meter else False,
                'meter_number': meter.meter_number if meter else '',
                'order_id': order.id if order else False,
                'invoice_id': inv.id,
                'invoice_number': inv.name,
                'amount': inv.amount_total,
                'amount_residual': inv.amount_residual,
                'current_bill': inv.amount_residual,
                'debt_amount': max(total_due - inv.amount_residual, 0.0),
                'due_amount': total_due,
                'due_date': str(inv.invoice_date_due) if inv.invoice_date_due else str(inv.invoice_date),
                'overdue': inv.invoice_date_due and inv.invoice_date_due < request.env.context.get('tz_date', fields.Date.today()),
            })

        return {
            'success': True,
            'period': period_data,
            'invoices': invoice_list,
            'invoice_count': len(invoice_list),
            'customer_count': len({item['customer_id'] for item in invoice_list}),
        }



    @http.route('/api/v1/utility/collector/report', type='json', auth='user', methods=['POST'])
    def collector_report(self, **kwargs):
        params = self._request_params(kwargs)
        collector, error = self._get_current_collector()
        if error:
            return error
        customer_name = params.get('customer_name', '').strip()
        customer_number = params.get('customer_number', '').strip()
        date_from = params.get('date_from')
        date_to = params.get('date_to')

        authorized_accounts = self._get_collector_scope_accounts()
        if not authorized_accounts:
            return {'success': True, 'total_amount': 0.0, 'total_count': 0, 'transactions': []}

        domain = [
            ('utility_customer_id', 'in', authorized_accounts.ids),
            ('collector_id', '=', collector.id),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ]

        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        if customer_name or customer_number:
            customer_domain = [('id', 'in', authorized_accounts.ids)]
            if customer_name:
                customer_domain.append(('partner_id.name', 'ilike', customer_name))
            if customer_number:
                customer_domain.append(('customer_number', 'ilike', customer_number))

            filtered_customers = request.env['utility.customer'].sudo().search(customer_domain)
            domain.append(('utility_customer_id', 'in', filtered_customers.ids))

        payments = request.env['account.payment'].sudo().search(domain, order='date desc, id desc')

        transactions = []
        total_amount = 0.0

        for pay in payments:
            customer = pay.utility_customer_id or pay.utility_sale_order_id.customer_id
            amount = pay.amount
            total_amount += amount
            transactions.append({
                'receipt_number': pay.name or pay.ref or '',
                'customer_name': (
                    customer.partner_id.name
                    if customer and customer.partner_id else ''
                ),
                'customer_number': customer.customer_number if customer else '',
                'amount': amount,
                'date': str(pay.date),
            })

        return {
            'success': True,
            'total_amount': total_amount,
            'total_count': len(transactions),
            'transactions': transactions,
        }
