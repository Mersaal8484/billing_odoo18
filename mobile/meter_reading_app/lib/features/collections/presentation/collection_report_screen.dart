import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/metric_card.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

class CollectionReportScreen extends ConsumerStatefulWidget {
  const CollectionReportScreen({super.key});

  @override
  ConsumerState<CollectionReportScreen> createState() =>
      _CollectionReportScreenState();
}

class _CollectionReportScreenState
    extends ConsumerState<CollectionReportScreen> {
  final _customerName = TextEditingController();
  final _customerNumber = TextEditingController();

  DateTime? _dateFrom;
  DateTime? _dateTo;
  CollectorReport? _report;
  Object? _error;
  bool _loading = false;
  bool _exporting = false;

  @override
  void initState() {
    super.initState();
    _loadReport();
  }

  @override
  void dispose() {
    _customerName.dispose();
    _customerNumber.dispose();
    super.dispose();
  }

  Future<void> _loadReport() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final report = await ref.read(collectionRepositoryProvider).collectorReport(
            customerName: _emptyToNull(_customerName.text),
            customerNumber: _emptyToNull(_customerNumber.text),
            dateFrom: _dateFrom,
            dateTo: _dateTo,
          );
      if (mounted) setState(() => _report = report);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String? _emptyToNull(String value) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }

  Future<void> _pickDate({required bool from}) async {
    final initial = from ? _dateFrom : _dateTo;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime(DateTime.now().year + 2),
    );
    if (picked == null) return;
    setState(() {
      if (from) {
        _dateFrom = picked;
      } else {
        _dateTo = picked;
      }
    });
  }

  Future<void> _exportCsv() async {
    final report = _report;
    if (report == null || report.transactions.isEmpty) {
      _show('لا توجد بيانات لتصديرها.', error: true);
      return;
    }

    setState(() => _exporting = true);
    try {
      final directory = await getApplicationDocumentsDirectory();
      final fileName =
          'collector_report_${DateTime.now().millisecondsSinceEpoch}.csv';
      final file = File('${directory.path}${Platform.pathSeparator}$fileName');
      final buffer = StringBuffer();
      buffer.writeln(
        [
          'رقم المستند',
          'المشترك',
          'رقم المشترك',
          'المبلغ',
          'التاريخ',
        ].map(_csv).join(','),
      );
      for (final tx in report.transactions) {
        buffer.writeln(
          [
            tx.receiptNumber,
            tx.customerName,
            tx.customerNumber,
            tx.amount.toStringAsFixed(2),
            _formatDateTime(tx.date),
          ].map(_csv).join(','),
        );
      }
      await file.writeAsString('\uFEFF$buffer');
      await Clipboard.setData(ClipboardData(text: file.path));
      _show('تم تصدير التقرير ونسخ مسار الملف: ${file.path}', error: false);
    } catch (error) {
      _show('تعذر تصدير التقرير: $error', error: true);
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  String _csv(Object? value) {
    final text = (value ?? '').toString().replaceAll('"', '""');
    return '"$text"';
  }

  void _show(String message, {required bool error}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error ? Theme.of(context).colorScheme.error : null,
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return 'اختر التاريخ';
    return '${date.year}/${date.month.toString().padLeft(2, '0')}/${date.day.toString().padLeft(2, '0')}';
  }

  String _formatDateTime(DateTime? date) {
    if (date == null) return '';
    return '${_formatDate(date)} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('تقارير التحصيل')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _filtersCard(),
          const SizedBox(height: 16),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: LoadingState(),
            )
          else if (_error != null)
            ErrorState(
              message: 'تعذر تحميل تقرير التحصيل: $_error',
              onRetry: _loadReport,
            )
          else
            _reportBody(),
        ],
      ),
    );
  }

  Widget _filtersCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'فترة التقرير',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _customerName,
              textInputAction: TextInputAction.search,
              decoration: const InputDecoration(
                labelText: 'البحث عن مشترك',
                prefixIcon: Icon(Icons.search_rounded),
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => _loadReport(),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _customerNumber,
              textInputAction: TextInputAction.search,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'بحث برقم المشترك',
                prefixIcon: Icon(Icons.numbers_rounded),
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => _loadReport(),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickDate(from: true),
                    icon: const Icon(Icons.date_range_rounded),
                    label: Text('من تاريخ: ${_formatDate(_dateFrom)}'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickDate(from: false),
                    icon: const Icon(Icons.date_range_rounded),
                    label: Text('إلى تاريخ: ${_formatDate(_dateTo)}'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _loading ? null : _loadReport,
                    icon: const Icon(Icons.search_rounded),
                    label: const Text('عرض التقرير'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: _exporting ? null : _exportCsv,
                    icon: _exporting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.download_rounded),
                    label: const Text('تصدير CSV'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _reportBody() {
    final report = _report ??
        const CollectorReport(
          totalAmount: 0,
          totalCount: 0,
          transactions: [],
        );

    if (report.transactions.isEmpty) {
      return const EmptyState(
        icon: Icons.receipt_long_outlined,
        title: 'لا توجد عمليات تحصيل',
        subtitle: 'غيّر الفلاتر أو نفّذ عمليات تحصيل ثم اعرض التقرير.',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: MetricCard(
                    icon: Icons.receipt_long_outlined,
                    label: 'إجمالي المعاملات',
                    value: '${report.totalCount}',
                    layout: MetricCardLayout.iconLabelValue,
                    card: false,
                    padding: EdgeInsets.zero,
                    iconSpacing: 8,
                    labelValueSpacing: 4,
                    labelTextAlign: TextAlign.center,
                    valueTextAlign: TextAlign.center,
                    valueStyle: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                Expanded(
                  child: MetricCard(
                    icon: Icons.payments_outlined,
                    label: 'المبلغ المدفوع',
                    value: '${report.totalAmount.toStringAsFixed(2)} ريال',
                    layout: MetricCardLayout.iconLabelValue,
                    card: false,
                    padding: EdgeInsets.zero,
                    iconSpacing: 8,
                    labelValueSpacing: 4,
                    labelTextAlign: TextAlign.center,
                    valueTextAlign: TextAlign.center,
                    valueStyle: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        ...report.transactions.map((tx) => _TransactionTile(transaction: tx)),
      ],
    );
  }
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({required this.transaction});

  final CollectorReportTransaction transaction;

  String _format(DateTime? date) {
    if (date == null) return '';
    return '${date.year}/${date.month.toString().padLeft(2, '0')}/${date.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Theme.of(context).colorScheme.primaryContainer,
          child: Icon(
            Icons.payments_outlined,
            color: Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
        title: Text(
          transaction.customerName,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          '${transaction.receiptNumber} · ${transaction.customerNumber} · ${_format(transaction.date)}',
        ),
        trailing: Text(
          '${transaction.amount.toStringAsFixed(0)} ريال',
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
    );
  }
}
