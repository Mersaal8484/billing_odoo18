import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/info_row.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/entities.dart';

class CustomerDetailScreen extends ConsumerWidget {
  final String assignmentId;

  const CustomerDetailScreen({super.key, required this.assignmentId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));

    return Scaffold(
      appBar: AppBar(title: const Text('تفاصيل العداد')),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: 'خطأ: $e'),
        data: (list) {
          final match = list.where((a) => a.id == assignmentId);
          if (match.isEmpty) {
            return const EmptyState(
                icon: Icons.error_outline, title: 'العنصر غير موجود');
          }
          final assignment = match.first;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(assignment.customer.name,
                                style: Theme.of(context).textTheme.titleLarge),
                          ),
                          SyncStatusChip(
                            label: _statusLabel(assignment.status),
                            color: _statusColor(context, assignment.status),
                            icon: _statusIcon(assignment.status),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(assignment.customer.address ?? '-',
                          style: Theme.of(context).textTheme.bodyMedium),
                      const Divider(height: 24),
                      InfoRow(
                          label: 'رقم المشترك',
                          value: assignment.customer.customerNumber,
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'رقم الحساب',
                          value: assignment.customer.accountNumber,
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'رقم العداد',
                          value: assignment.meter.meterNumber,
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'الرقم التسلسلي',
                          value: assignment.meter.serialNumber ?? '-',
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'نوع العداد',
                          value: assignment.meter.meterType ?? '-',
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'حالة الاتصال',
                          value:
                              assignment.meter.connectionStatus == 'connected'
                                  ? 'متصل'
                                  : 'مقطوع',
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                          label: 'المنطقة',
                          value:
                              '${assignment.customer.regionName} · ${assignment.customer.areaName}',
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          valueFontWeight: FontWeight.w700),
                      InfoRow(
                        label: 'آخر قراءة',
                        value: assignment.customer.lastReadingValue != null
                            ? '${assignment.customer.lastReadingValue!.toStringAsFixed(0)} kWh'
                            : '-',
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        valueFontWeight: FontWeight.w700,
                      ),
                      InfoRow(
                        label: 'تاريخ آخر قراءة',
                        value: assignment.customer.lastReadingDate != null
                            ? _date(assignment.customer.lastReadingDate!)
                            : '-',
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        valueFontWeight: FontWeight.w700,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              if (assignment.status == AssignmentStatus.read ||
                  assignment.status == AssignmentStatus.pendingDecision)
                const Card(
                  child: ListTile(
                    leading: Icon(Icons.lock_outline),
                    title: Text('القراءة مكتملة ولا يمكن إدخال قراءة أخرى'),
                    subtitle: Text(
                        'تُفتح القراءة فقط عند إعادتها من المراجعة للتصحيح.'),
                  ),
                )
              else
                FilledButton.icon(
                  icon: Icon(assignment.status == AssignmentStatus.rejected
                      ? Icons.replay_rounded
                      : Icons.speed_rounded),
                  label: Text(assignment.status == AssignmentStatus.rejected
                      ? 'إعادة إدخال القراءة'
                      : 'إدخال قراءة جديدة'),
                  onPressed: () =>
                      context.push('/readings/new/${assignment.id}'),
                ),
            ],
          );
        },
      ),
    );
  }

  String _date(DateTime date) =>
      '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  String _statusLabel(AssignmentStatus status) => switch (status) {
        AssignmentStatus.pending => 'متبقي',
        AssignmentStatus.pendingDecision => 'بانتظار قرار',
        AssignmentStatus.read => 'مكتمل',
        AssignmentStatus.rejected => 'مرفوض',
        AssignmentStatus.escalated => 'مصعد',
        AssignmentStatus.skipped => 'متجاوز',
      };

  IconData _statusIcon(AssignmentStatus status) => switch (status) {
        AssignmentStatus.pending => Icons.hourglass_empty_rounded,
        AssignmentStatus.pendingDecision => Icons.rule_rounded,
        AssignmentStatus.read => Icons.check_circle_outline,
        AssignmentStatus.rejected => Icons.cancel_outlined,
        AssignmentStatus.escalated => Icons.build_outlined,
        AssignmentStatus.skipped => Icons.skip_next_rounded,
      };

  Color _statusColor(BuildContext context, AssignmentStatus status) =>
      switch (status) {
        AssignmentStatus.pending => Colors.orange,
        AssignmentStatus.pendingDecision => Colors.blue,
        AssignmentStatus.read => Theme.of(context).colorScheme.primary,
        AssignmentStatus.rejected => Theme.of(context).colorScheme.error,
        AssignmentStatus.escalated => Colors.deepPurple,
        AssignmentStatus.skipped => Colors.grey,
      };
}
