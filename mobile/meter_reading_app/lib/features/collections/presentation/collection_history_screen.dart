import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/metric_card.dart';

class CollectionHistoryScreen extends ConsumerWidget {
  const CollectionHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.watch(collectionRepositoryProvider);
    final summary = repo.dailySummary();
    final receipts = repo.receipts();

    return Scaffold(
      appBar: AppBar(title: const Text('سجل التحصيل في الجلسة')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                  child: MetricCard(
                      label: 'الإجمالي',
                      value:
                          '${summary.collectedAmount.toStringAsFixed(0)} ﷼',
                      valueStyle:
                          const TextStyle(fontWeight: FontWeight.w800))),
              const SizedBox(width: 8),
              Expanded(
                  child: MetricCard(
                      label: 'العمليات',
                      value: '${summary.operationCount}',
                      valueStyle:
                          const TextStyle(fontWeight: FontWeight.w800))),
              const SizedBox(width: 8),
              Expanded(
                  child: MetricCard(
                      label: 'حسابات معلقة',
                      value: '${summary.pendingAccounts}',
                      valueStyle:
                          const TextStyle(fontWeight: FontWeight.w800))),
            ],
          ),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.sync_rounded),
            label: const Text('السندات المرحّلة في الجلسة'),
          ),
          const SizedBox(height: 16),
          Text('آخر العمليات', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (receipts.isEmpty)
            const Card(
              child: ListTile(
                leading: Icon(Icons.info_outline),
                title: Text('لا توجد عمليات جديدة في هذه الجلسة'),
                subtitle: Text('تظهر هنا السندات التي أكد النظام ترحيلها في هذه الجلسة.'),
              ),
            )
          else
            ...receipts.map(
              (receipt) => Card(
                child: ListTile(
                  leading: const Icon(Icons.receipt_long_outlined),
                  title: Text(receipt.reference),
                  subtitle: Text(receipt.account.customer.name),
                  trailing: Text('${receipt.amount.toStringAsFixed(0)} ﷼'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

