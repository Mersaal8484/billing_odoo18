import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import '../../../core/network/billing_api_service.dart';
import '../../customers/domain/entities.dart';
import '../domain/collection_models.dart';

/// Source of truth for field collections.  It never fabricates an account,
/// payment or receipt: a receipt is kept locally only after Odoo confirms the
/// posted payment, exact allocation and collector custody record.
class OdooCollectionRepository implements CollectionRepository {
  OdooCollectionRepository(this._billing, {FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final BillingApiService _billing;
  final FlutterSecureStorage _storage;
  final List<CollectionReceipt> _receipts = [];
  final Map<String, CollectionAccount> _accounts = {};
  // This is deliberately separate from `_accounts`: that map is a multi-key
  // lookup cache (customer, account and meter identifiers).  The collector
  // home list must always retain the exact snapshot produced by the most
  // recent period-invoice sync, regardless of cache-key collisions.
  List<CollectionAccount> _syncedPeriodAccounts = const [];
  final _changeHub = StreamController<List<CollectionAccount>>.broadcast();
  CollectionPeriod? _currentPeriod;
  String? _periodMessage;

  @override
  CollectionPeriod? get currentPeriod => _currentPeriod;

  @override
  String? get periodMessage => _periodMessage;

  @override
  List<CollectionAccount> get syncedAccounts =>
      List.unmodifiable(_syncedPeriodAccounts);

  @override
  Stream<List<CollectionAccount>> watchAccounts({String? query}) async* {
    yield _filterAccounts(query);
    yield* _changeHub.stream.map((_) => _filterAccounts(query));
  }

  List<CollectionAccount> _filterAccounts(String? query) {
    final value = query?.trim().toLowerCase() ?? '';
    final unique = <String, CollectionAccount>{};
    for (final account in _accounts.values) {
      unique[account.id] = account;
    }
    var list = unique.values.toList()
      ..sort((a, b) => b.dueTotal.compareTo(a.dueTotal));
    if (value.isEmpty) return List.unmodifiable(list);
    list = list.where((account) {
      return account.customer.name.toLowerCase().contains(value) ||
          account.customer.customerNumber.toLowerCase().contains(value) ||
          account.customer.accountNumber.toLowerCase().contains(value) ||
          account.meter.meterNumber.toLowerCase().contains(value);
    }).toList();
    return List.unmodifiable(list);
  }

  void _cacheAccount(CollectionAccount account) {
    _accounts[account.id] = account;
    _accounts[account.customer.customerNumber] = account;
    _accounts[account.customer.accountNumber] = account;
    _accounts[account.meter.meterNumber] = account;
  }

  void _notify() {
    if (!_changeHub.isClosed) {
      _changeHub.add(_filterAccounts(null));
    }
  }

  @override
  Future<CollectionPeriod?> syncPeriodInvoices() async {
    final result = await _billing.getCollectorPeriodInvoices();
    final rawPeriod = result['period'];
    if (rawPeriod is! Map) {
      _currentPeriod = null;
      _periodMessage = 'لا توجد فترة تحصيل مفتوحة حالياً';
      _accounts.clear();
      _syncedPeriodAccounts = const [];
      _notify();
      return null;
    }
    final periodMap = Map<String, dynamic>.from(rawPeriod);
    _currentPeriod = CollectionPeriod(
      id: _toInt(periodMap['id']) ?? 0,
      name: periodMap['name']?.toString() ?? '',
      state: periodMap['state']?.toString() ?? '',
      invoiceCount: _toInt(result['invoice_count']) ?? 0,
      customerCount: _toInt(result['customer_count']) ?? 0,
    );
    _periodMessage = null;
    final accounts = _mapPeriodInvoiceAccounts(result);
    _syncedPeriodAccounts = List.unmodifiable(accounts);
    _debugPeriodInvoiceSync(result, accounts);
    _accounts.clear();
    for (final account in accounts) {
      _cacheAccount(account);
    }
    _notify();
    return _currentPeriod;
  }

  void _debugPeriodInvoiceSync(
    Map<String, dynamic> result,
    List<CollectionAccount> accounts,
  ) {
    assert(() {
      final rows = result['invoices'];
      final rawRows = _periodInvoiceRows(result);
      debugPrint(
        '[collector-sync] period_invoice_count=${_currentPeriod?.invoiceCount} '
        'period_customer_count=${_currentPeriod?.customerCount} '
        'raw_invoices=${rawRows.length} mapped_accounts=${accounts.length} '
        'result_keys=${result.keys.toList()} invoices_type=${rows.runtimeType}',
      );
      for (final row in rawRows.take(2)) {
        debugPrint('[collector-sync] raw_invoice=${jsonEncode(row)}');
      }
      for (final account in accounts.take(3)) {
        debugPrint(
          '[collector-sync] mapped_account=${jsonEncode({
            'id': account.id,
            'customer_number': account.customer.customerNumber,
            'account_number': account.customer.accountNumber,
            'customer_name': account.customer.name,
            'meter_number': account.meter.meterNumber,
            'due_total': account.dueTotal,
            'invoices': account.invoices.length,
          })}',
        );
      }
      return true;
    }());
  }

  List<Map<String, dynamic>> _periodInvoiceRows(Map<String, dynamic> result) {
    final rows = result['invoices'];
    if (rows is List) {
      return rows
          .whereType<Map>()
          .map((row) => Map<String, dynamic>.from(row))
          .toList(growable: false);
    }
    return const [];
  }

  String _firstText(
    Map<String, dynamic> values,
    List<String> keys, {
    String fallback = '',
  }) {
    for (final key in keys) {
      final value = values[key];
      if (value == null || value == false) continue;
      final text = value.toString().trim();
      if (text.isNotEmpty) return text;
    }
    return fallback;
  }

  int? _toInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '');
  }

  double _toDouble(Object? value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }

  @override
  Future<CollectionAccount?> resolveQr(String payload) async {
    final account = _mapAccount(await _billing.getCollectorAccount(qrReference: payload));
    if (account != null) {
      _cacheAccount(account);
      _notify();
    }
    return account;
  }

  @override
  Future<CollectionAccount?> findById(String id) async {
    final cached = _accounts[id];
    if (cached != null) return cached;
    final account = _mapAccount(
      await _billing.getCollectorAccount(lookupValue: id),
    );
    if (account != null) {
      _cacheAccount(account);
      _notify();
    }
    return account;
  }

  @override
  Future<CollectionReceipt> collect({
    required String accountId,
    required CollectionInvoice invoice,
    required double amount,
    required PaymentMethod method,
  }) async {
    if (method != PaymentMethod.cash) {
      throw StateError('التحصيل الميداني في هذه المرحلة نقدي فقط.');
    }
    final account = _accounts[accountId] ?? await findById(accountId);
    if (account == null) throw StateError('الحساب غير موجود أو خارج مسارك.');

    final pendingKey = _pendingKey(
      accountId: accountId,
      invoiceId: invoice.invoiceId,
      amount: amount,
    );
    // Persist before sending. If the connection times out after the server
    // posts the payment, the next attempt reuses this exact key and receives
    // the original receipt instead of creating a second collection.
    final requestKey =
        await _storage.read(key: pendingKey) ?? 'MC-${const Uuid().v4()}';
    await _storage.write(key: pendingKey, value: requestKey);
    final result = await _billing.collectCash(
      orderId: invoice.orderId,
      invoiceId: invoice.invoiceId,
      amount: amount,
      idempotencyKey: requestKey,
    );
    await _storage.delete(key: pendingKey);
    final receipt = CollectionReceipt(
      reference: result['reference'] as String? ?? requestKey,
      displayName: result['payment_reference'] as String? ?? '',
      account: account,
      amount: (result['amount'] as num?)?.toDouble() ?? amount,
      method: PaymentMethod.cash,
      paidAt: DateTime.tryParse(result['paid_at'] as String? ?? '') ??
          DateTime.now(),
    );
    _receipts.insert(0, receipt);
    return receipt;
  }

  String _pendingKey({
    required String accountId,
    required int invoiceId,
    required double amount,
  }) => 'collection.pending.$accountId.$invoiceId.${amount.toStringAsFixed(2)}';

  CollectionAccount? _mapAccount(Map<String, dynamic> result) {
    final raw = result['account'];
    if (raw is! Map) return null;
    final account = Map<String, dynamic>.from(raw);
    final customerId = _toInt(account['customer_id']);
    if (customerId == null) return null;
    final bills = (account['bills'] as List? ?? const [])
        .whereType<Map>()
        .map((value) {
      final bill = Map<String, dynamic>.from(value);
      final residual = _toDouble(bill['amount_residual']);
      final total = _toDouble(bill['amount']);
      final isOverdue = bill['overdue'] == true;
      final InvoiceStatus status;
      if (residual <= 0) {
        status = InvoiceStatus.paid;
      } else if (isOverdue) {
        status = InvoiceStatus.overdue;
      } else if (total > 0 && residual < total) {
        status = InvoiceStatus.partiallyPaid;
      } else {
        status = InvoiceStatus.unpaid;
      }
      return CollectionInvoice(
        orderId: _toInt(bill['order_id']) ?? 0,
        invoiceId: _toInt(bill['invoice_id']) ?? 0,
        id: '${bill['invoice_id']}',
        invoiceNumber: _firstText(
          bill,
          ['invoice_number', 'bill_number', 'number', 'display_name'],
          fallback: '—',
        ),
        dueDate: DateTime.tryParse(bill['due_date']?.toString() ?? '') ??
            DateTime.now(),
        amount: total,
        amountResidual: residual,
        status: status,
      );

    }).toList(growable: false);
    final customer = Customer(
      remoteId: customerId,
      customerNumber: _firstText(
        account,
        [
          'customer_number',
          'account_number',
          'billing_number',
          'subscriber_number',
          'customer_id',
        ],
        fallback: '$customerId',
      ),
      accountNumber: _firstText(
        account,
        [
          'account_number',
          'customer_number',
          'billing_number',
          'subscriber_number',
        ],
        fallback: '$customerId',
      ),
      name: _firstText(
        account,
        ['customer_name', 'subscriber_name', 'name', 'partner_name'],
        fallback: '—',
      ),
    );
    final meter = Meter(
      remoteId: _toInt(account['meter_id']) ?? 0,
      meterNumber: _firstText(
        account,
        ['meter_number', 'nickname', 'meter', 'counter_number'],
        fallback: '—',
      ),
      customerRemoteId: customerId,
      paymentType: MeterPaymentType.postpaid,
      connectionStatus: account['connection_status']?.toString() ?? 'connected',
    );
    return CollectionAccount(
      id: customer.customerNumber,
      customer: customer,
      meter: meter,
      balance: _toDouble(account['accounting_balance']),
      debtAmount: _toDouble(account['debt_amount']),
      currentBill: _toDouble(account['current_bill']),
      dueAmount: _toDouble(account['due_amount']),
      allowPartial: account['allow_partial'] != false,
      message: '',
      qrPayload: account['external_qr_reference']?.toString() ?? '',
      invoices: bills,
    );
  }

  List<CollectionAccount> _mapPeriodInvoiceAccounts(Map<String, dynamic> result) {
    final rows = _periodInvoiceRows(result);
    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final row in rows) {
      final item = row;
      final key = _firstText(
        item,
        [
          'customer_number',
          'account_number',
          'billing_number',
          'subscriber_number',
          'customer_id',
        ],
      );
      if (key.isEmpty) continue;
      grouped.putIfAbsent(key, () => <Map<String, dynamic>>[]).add(item);
    }

    return grouped.entries.map((entry) {
      final first = entry.value.first;
      final customerId = _toInt(first['customer_id']) ?? 0;
      final invoices = entry.value.map((bill) {
        final residual = _toDouble(bill['amount_residual']);
        final total = _toDouble(bill['amount']);
        final isOverdue = bill['overdue'] == true;
        final InvoiceStatus status;
        if (residual <= 0) {
          status = InvoiceStatus.paid;
        } else if (isOverdue) {
          status = InvoiceStatus.overdue;
        } else if (total > 0 && residual < total) {
          status = InvoiceStatus.partiallyPaid;
        } else {
          status = InvoiceStatus.unpaid;
        }
        return CollectionInvoice(
          orderId: _toInt(bill['order_id']) ?? 0,
          invoiceId: _toInt(bill['invoice_id']) ?? 0,
          id: '${bill['invoice_id']}',
          invoiceNumber: _firstText(
            bill,
            ['invoice_number', 'bill_number', 'number', 'display_name'],
            fallback: '—',
          ),
          dueDate: DateTime.tryParse(bill['due_date']?.toString() ?? '') ??
              DateTime.now(),
          amount: total,
          amountResidual: residual,
          status: status,
        );
      }).toList(growable: false);

      final customer = Customer(
        remoteId: customerId,
        customerNumber: _firstText(
          first,
          [
            'customer_number',
            'account_number',
            'billing_number',
            'subscriber_number',
            'customer_id',
          ],
          fallback: '$customerId',
        ),
        accountNumber: _firstText(
          first,
          [
            'account_number',
            'customer_number',
            'billing_number',
            'subscriber_number',
          ],
          fallback: '$customerId',
        ),
        name: _firstText(
          first,
          ['customer_name', 'subscriber_name', 'name', 'partner_name'],
          fallback: '—',
        ),
      );
      final meter = Meter(
        remoteId: _toInt(first['meter_id']) ?? 0,
        meterNumber: _firstText(
          first,
          ['meter_number', 'nickname', 'meter', 'counter_number'],
          fallback: '—',
        ),
        customerRemoteId: customerId,
        paymentType: MeterPaymentType.postpaid,
        connectionStatus: 'connected',
      );
      final dueAmount = _toDouble(first['due_amount']) > 0
          ? _toDouble(first['due_amount'])
          : invoices
              .where((item) => item.status != InvoiceStatus.paid)
              .fold<double>(0, (sum, item) => sum + item.amountResidual);
      final currentBill = _toDouble(first['current_bill']) > 0
          ? _toDouble(first['current_bill'])
          : (invoices.isEmpty ? 0.0 : invoices.first.amountResidual);
      return CollectionAccount(
        id: customer.customerNumber,
        customer: customer,
        meter: meter,
        balance: 0,
        debtAmount: _toDouble(first['debt_amount']),
        currentBill: currentBill,
        dueAmount: dueAmount,
        allowPartial: true,
        message: '',
        qrPayload: '',
        invoices: invoices,
      );
    }).toList(growable: false);
  }

  @override
  Future<CollectorReport> collectorReport({
    String? customerName,
    String? customerNumber,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    final result = await _billing.getCollectorReport(
      customerName: customerName,
      customerNumber: customerNumber,
      dateFrom: dateFrom == null ? null : _dateOnly(dateFrom),
      dateTo: dateTo == null ? null : _dateOnly(dateTo),
    );
    final transactions = (result['transactions'] as List? ?? const [])
        .whereType<Map>()
        .map((row) {
      final item = Map<String, dynamic>.from(row);
      return CollectorReportTransaction(
        receiptNumber: item['receipt_number']?.toString() ?? '',
        customerName: item['customer_name']?.toString() ?? '',
        customerNumber: item['customer_number']?.toString() ?? '',
        amount: (item['amount'] as num?)?.toDouble() ?? 0,
        date: DateTime.tryParse(item['date']?.toString() ?? ''),
      );
    }).toList(growable: false);
    return CollectorReport(
      totalAmount: (result['total_amount'] as num?)?.toDouble() ?? 0,
      totalCount: (result['total_count'] as num?)?.toInt() ??
          transactions.length,
      transactions: transactions,
    );
  }

  String _dateOnly(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';

  @override
  CollectorDailySummary dailySummary() => CollectorDailySummary(
        collectedAmount: _receipts.fold(0, (sum, item) => sum + item.amount),
        operationCount: _receipts.length,
        pendingAccounts: 0,
      );

  @override
  List<CollectionReceipt> receipts() => List.unmodifiable(_receipts);

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
