import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

class CollectorHomeScreen extends ConsumerStatefulWidget {
  const CollectorHomeScreen({super.key});

  @override
  ConsumerState<CollectorHomeScreen> createState() =>
      _CollectorHomeScreenState();
}

class _CollectorHomeScreenState extends ConsumerState<CollectorHomeScreen> {
  String _query = '';
  bool _syncing = false;
  // حالة محلية للفترة المفتوحة — لا نعتمد على ref.watch(repo).currentPeriod
  // لأن collectionRepositoryProvider هو Provider عادي ولا يُعيد بناء الـ widget
  // عند تغيير الحقول الداخلية للـ repository.
  List<CollectionAccount> _syncedAccounts = const [];
  bool? _hasPeriod; // null = لم يتم المزامنة بعد، false = لا فترة، true = فترة مفتوحة

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncPeriodInvoices());
  }

  Future<void> _syncPeriodInvoices() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    try {
      final period =
          await ref.read(collectionRepositoryProvider).syncPeriodInvoices();
      if (!mounted) return;
      final syncedAccounts =
          ref.read(collectionRepositoryProvider).syncedAccounts;
      final invoiceCount =
          syncedAccounts.fold<int>(0, (sum, a) => sum + a.invoices.length);
      setState(() {
        _syncedAccounts = syncedAccounts;
        _hasPeriod = period != null; // ← تحديث الـ flag المحلي
      });
      _debugUiSync(period, syncedAccounts);
      final message = period == null
          ? (ref.read(collectionRepositoryProvider).periodMessage ??
              'لا توجد فترة تحصيل مفتوحة حالياً.')
          : 'تم تنزيل $invoiceCount فاتورة لـ ${syncedAccounts.length} مشترك في: ${period.name}';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('تعذر تحديث فواتير التحصيل: $error'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }


  List<_InvoiceListEntry> _syncedInvoiceEntries() {
    final entries = <_InvoiceListEntry>[];
    for (final account in _syncedAccounts) {
      for (final invoice in account.invoices) {
        entries.add(_InvoiceListEntry(account: account, invoice: invoice));
      }
    }
    entries.sort((a, b) {
      final dateComparison = b.invoice.dueDate.compareTo(a.invoice.dueDate);
      if (dateComparison != 0) return dateComparison;
      return b.invoice.invoiceId.compareTo(a.invoice.invoiceId);
    });
    return List.unmodifiable(entries);
  }

  List<_InvoiceListEntry> _filteredSyncedInvoices() {
    final query = _query.trim().toLowerCase();
    final entries = _syncedInvoiceEntries();
    if (query.isEmpty) return entries;
    final filtered = entries.where((entry) {
      return entry.searchableText.contains(query);
    }).toList(growable: false);
    _debugSearch(query, entries, filtered);
    return filtered;
  }

  void _debugUiSync(
    CollectionPeriod? period,
    List<CollectionAccount> accounts,
  ) {
    assert(() {
      debugPrint(
        '[collector-ui] sync_completed period=${period?.name} '
        'state_accounts=${accounts.length}',
      );
      for (final account in accounts.take(3)) {
        debugPrint(
          '[collector-ui] state_account=${jsonEncode({
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

  void _debugSearch(
    String query,
    List<_InvoiceListEntry> source,
    List<_InvoiceListEntry> filtered,
  ) {
    assert(() {
      debugPrint(
        '[collector-search] query="$query" '
        'source_accounts=${_syncedAccounts.length} '
        'source_invoices=${source.length} '
        'matched_invoices=${filtered.length}',
      );
      for (final entry in source.take(3)) {
        debugPrint(
          '[collector-search] candidate=${jsonEncode({
            'customer_number': entry.account.customer.customerNumber,
            'account_number': entry.account.customer.accountNumber,
            'meter_number': entry.account.meter.meterNumber,
            'invoice_number': entry.invoice.invoiceNumber,
            'name': entry.account.customer.name,
          })}',
        );
      }
      return true;
    }());
  }

  @override
  Widget build(BuildContext context) {
    final repository = ref.watch(collectionRepositoryProvider);
    final summary = repository.dailySummary();
    final period = repository.currentPeriod;
    final invoiceEntries = _filteredSyncedInvoices();

    return Scaffold(
      appBar: AppBar(
        title: const Text('المتحصل'),
        actions: [
          IconButton(
            tooltip: 'تقارير التحصيل',
            onPressed: () => context.push('/collector/report'),
            icon: const Icon(Icons.analytics_outlined),
          ),
        ],
      ),
      // ── Column + Expanded: بنفس بنية شاشة الكاشف، لا ListView خارجي ────
      body: Column(
        children: [
          // مربع البحث
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              textInputAction: TextInputAction.search,
              onChanged: (value) => setState(() => _query = value),
              decoration: const InputDecoration(
                hintText:
                    'بحث برقم المشترك أو الحساب أو العداد أو الاسم أو الفاتورة',
                prefixIcon: Icon(Icons.search_rounded),
              ),
            ),
          ),
          // ملخص الجلسة
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: _SummaryTile(
                    icon: Icons.payments_outlined,
                    label: 'هذه الجلسة',
                    value: '${summary.collectedAmount.toStringAsFixed(0)} ريال',
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _SummaryTile(
                    icon: Icons.receipt_long_outlined,
                    label: 'العمليات',
                    value: '${summary.operationCount}',
                  ),
                ),
              ],
            ),
          ),
          // أزرار المزامنة والسجل
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _syncing ? null : _syncPeriodInvoices,
                    icon: _syncing
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.sync_rounded),
                    label: Text(
                      _syncing ? 'جارٍ التحديث...' : 'مزامنة الفواتير',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => context.push('/collector/history'),
                  icon: const Icon(Icons.history_rounded),
                  label: const Text('السجل'),
                ),
              ],
            ),
          ),
          // ── القائمة — Expanded يمنع Overflow ومطابق لبنية شاشة الكاشف ───
          Expanded(
            child: invoiceEntries.isEmpty
                ? EmptyState(
                    icon: Icons.search_off_rounded,
                    title: _hasPeriod == false
                        ? 'لا توجد فترة تحصيل مفتوحة'
                        : _syncedAccounts.isEmpty
                            ? 'لا توجد فواتير لهذه الفترة'
                            : 'لا توجد نتائج مطابقة للبحث',
                    subtitle: _hasPeriod == false
                        ? 'افتح فترة تحصيل من النظام ثم اضغط مزامنة الفواتير.'
                        : _syncedAccounts.isEmpty
                            ? 'اضغط مزامنة الفواتير لتحديث القائمة.'
                            : 'ابحث برقم المشترك أو الحساب أو العداد أو الفاتورة.',
                  )
                : ListView.separated(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    itemCount: invoiceEntries.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 4),
                    itemBuilder: (context, i) => _SyncedInvoiceTile(
                      key: ValueKey(
                        'collector-period-invoice-'
                        '${invoiceEntries[i].account.id}-'
                        '${invoiceEntries[i].invoice.invoiceId}',
                      ),
                      entry: invoiceEntries[i],
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── مساعد لإنشاء إدخال بحث مُدمج من حساب + فاتورة ─────────────────────────
class _InvoiceListEntry {
  const _InvoiceListEntry({required this.account, required this.invoice});

  final CollectionAccount account;
  final CollectionInvoice invoice;

  String get searchableText => [
        account.customer.name,
        account.customer.customerNumber,
        account.customer.accountNumber,
        account.meter.meterNumber,
        invoice.invoiceNumber,
      ].join(' ').toLowerCase();
}

// ── بطاقة الفاتورة الموحدة ───────────────────────────────────────────────────
class _SyncedInvoiceTile extends StatelessWidget {
  const _SyncedInvoiceTile({super.key, required this.entry});

  final _InvoiceListEntry entry;

  @override
  Widget build(BuildContext context) {
    final account = entry.account;
    final invoice = entry.invoice;
    final colors = Theme.of(context).colorScheme;
    final canCollect = invoice.amountResidual > 0;
    final (badgeColor, badgeText) = switch (invoice.status) {
      InvoiceStatus.paid => (Colors.green.shade700, 'مسدد'),
      InvoiceStatus.partiallyPaid => (Colors.orange.shade700, 'مدفوع جزئياً'),
      InvoiceStatus.overdue => (colors.error, 'متأخرة'),
      InvoiceStatus.unpaid => (colors.outline, 'غير مسدد'),
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── الصف العلوي: أيقونة + بيانات المشترك + المبلغ + زر تحصيل ──
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  backgroundColor: colors.primaryContainer,
                  child: Icon(
                    Icons.person_outline_rounded,
                    color: colors.onPrimaryContainer,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        account.customer.name,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: colors.primary,
                          fontWeight: FontWeight.w800,
                          fontSize: 15,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'رقم المشترك: ${account.customer.customerNumber}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      Text(
                        'رقم العداد: ${account.meter.meterNumber}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                // زر التحصيل الأخضر على يمين اسم المشترك
                canCollect
                    ? FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: Colors.green.shade600,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                          // ── لازم نلغي minimumSize الموروث من filledButtonTheme
                          // (Size.fromHeight(56) = عرض لانهائي) وإلا فإن هذا
                          // الزر داخل Row يسبب BoxConstraints forces an
                          // infinite width ويفشل رسم كل العنصر (والقائمة كلها
                          // تظهر فارغة بصمت في release/profile).
                          minimumSize: const Size(80, 40),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        onPressed: () => context.push(
                          '/collector/payment/${account.id}',
                          extra: invoice,
                        ),
                        icon: const Icon(Icons.payments_outlined, size: 16),
                        label: const Text('تحصيل',
                            style: TextStyle(fontSize: 13)),
                      )
                    : OutlinedButton(
                        onPressed: null,
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                          minimumSize: const Size(80, 40),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: const Text('مسددة',
                            style: TextStyle(fontSize: 13)),
                      ),
              ],
            ),
            const SizedBox(height: 10),
            // ── الصف السفلي: رقم الفاتورة + المبلغ المتبقي + الحالة ────────
            Row(
              children: [
                Expanded(
                  child: Text(
                    'الفاتورة: ${invoice.invoiceNumber}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${invoice.amountResidual.toStringAsFixed(2)} ر.ي',
                  style: TextStyle(
                    color: canCollect ? colors.primary : Colors.green.shade700,
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(width: 8),
                _StatusBadge(color: badgeColor, text: badgeText),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ── شارة الحالة ──────────────────────────────────────────────────────────────
class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.color, required this.text});

  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── بطاقة ملخص الجلسة ────────────────────────────────────────────────────────
class _SummaryTile extends StatelessWidget {
  const _SummaryTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: Theme.of(context).textTheme.bodySmall),
                  Text(
                    value,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
