import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

/// Live collector inquiry. No locally cached balance is presented as payable.
class CollectionAccountScreen extends ConsumerStatefulWidget {
  const CollectionAccountScreen({super.key, required this.accountId});
  final String accountId;

  @override
  ConsumerState<CollectionAccountScreen> createState() =>
      _CollectionAccountScreenState();
}

class _CollectionAccountScreenState
    extends ConsumerState<CollectionAccountScreen> {
  CollectionAccount? _account;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final account = await ref
          .read(collectionRepositoryProvider)
          .findById(widget.accountId);
      if (account == null) {
        throw StateError('الحساب غير موجود أو خارج مسار المحصل.');
      }
      if (mounted) setState(() => _account = account);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('تفاصيل حساب التحصيل'),
          actions: [
            IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
          ],
        ),
        body: _loading
            ? const LoadingState()
            : _error != null
                ? ErrorState(
                    message: 'تعذر التحقق من الحساب: $_error', onRetry: _load)
                : _content(_account!),
      );

  Widget _content(CollectionAccount account) {
    final scheme = Theme.of(context).colorScheme;
    final invoices = account.invoices
        .where((invoice) => invoice.amountResidual > 0)
        .toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: ListTile(
            leading: const Icon(Icons.person_outline),
            title: Text(account.customer.name,
                style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(
                '${account.customer.accountNumber} · عداد ${account.meter.meterNumber}'),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          color: invoices.isEmpty
              ? scheme.primaryContainer
              : scheme.errorContainer.withOpacity(.25),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _amount('فاتورة حالية', account.currentBill),
                _amount('متأخرات', account.debtAmount),
                _amount('الإجمالي', account.dueAmount, bold: true),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text('الفواتير القابلة للتحصيل',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (invoices.isEmpty)
          const EmptyState(
            icon: Icons.check_circle_outline,
            title: 'لا توجد فواتير مستحقة',
            subtitle: 'تمت مراجعة الرصيد مباشرة من النظام.',
          ),
        ...invoices.map((invoice) => Card(
              child: ListTile(
                leading: Icon(Icons.receipt_long_outlined,
                    color: invoice.status == InvoiceStatus.overdue
                        ? scheme.error
                        : scheme.primary),
                title: Text(invoice.invoiceNumber),
                subtitle: Text(
                    'المتبقي ${invoice.amountResidual.toStringAsFixed(2)} ر.ي'),
                trailing: TextButton(
                  onPressed: () => context.push(
                    '/collector/payment/${account.id}',
                    extra: invoice,
                  ),
                  child: const Text('تحصيل'),
                ),
              ),
            )),
      ],
    );
  }

  Widget _amount(String label, double value, {bool bold = false}) => Column(
        children: [
          Text(value.toStringAsFixed(2),
              style: TextStyle(
                fontWeight: bold ? FontWeight.w800 : FontWeight.w600,
                fontSize: bold ? 18 : 14,
              )),
          Text(label, style: const TextStyle(fontSize: 11)),
        ],
      );
}
