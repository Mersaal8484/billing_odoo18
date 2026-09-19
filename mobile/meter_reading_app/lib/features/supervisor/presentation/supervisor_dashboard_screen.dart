import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/metric_card.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../../customers/domain/entities.dart';

class SupervisorDashboardScreen extends ConsumerWidget {
  const SupervisorDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignments = ref.watch(assignmentsProvider(const AssignmentQuery()));
    final collectionSummary = ref.watch(collectorDailySummaryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('لوحة المشرف'),
        // ✅ زر رجوع صريح — يعيد المستخدم للداشبورد الرئيسي
        leading: Navigator.canPop(context)
            ? null // go_router سيضيف زر رجوع تلقائياً إذا كان هناك stack
            : IconButton(
                tooltip: 'الرئيسية',
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.of(context).maybePop(),
              ),
      ),
      body: assignments.when(
        loading: () => const LoadingState(),
        error: (e, _) => ErrorState(message: 'تعذر تحميل لوحة المشرف: $e'),
        data: (list) {
          final pendingDecision = list
              .where((a) => a.status == AssignmentStatus.pendingDecision)
              .toList();
          final rejected =
              list.where((a) => a.status == AssignmentStatus.rejected).toList();
          final escalated = list
              .where((a) => a.status == AssignmentStatus.escalated)
              .toList();

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  Expanded(
                    child: MetricCard(
                      icon: Icons.rule_folder_outlined,
                      label: 'بانتظار الاعتماد',
                      value: '${pendingDecision.length}',
                      layout: MetricCardLayout.iconValueLabel,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      iconSpacing: 10,
                      valueStyle: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricCard(
                      icon: Icons.report_problem_outlined,
                      label: 'مرفوضة',
                      value: '${rejected.length}',
                      layout: MetricCardLayout.iconValueLabel,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      iconSpacing: 10,
                      valueStyle: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: MetricCard(
                      icon: Icons.build_outlined,
                      label: 'مصعدة لفني',
                      value: '${escalated.length}',
                      layout: MetricCardLayout.iconValueLabel,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      iconSpacing: 10,
                      valueStyle: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricCard(
                      icon: Icons.payments_outlined,
                      label: 'تحصيل اليوم',
                      value: collectionSummary.when(
                        data: (summary) =>
                            '${summary.collectedAmount.toStringAsFixed(0)} ﷼',
                        loading: () => '…',
                        error: (_, __) => '—',
                      ),
                      layout: MetricCardLayout.iconValueLabel,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      iconSpacing: 10,
                      valueStyle: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text('قرارات عداد معلقة',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              if (pendingDecision.isEmpty)
                const EmptyState(
                  icon: Icons.check_circle_outline,
                  title: 'لا توجد قراءات معلقة الآن',
                  subtitle:
                      'ستظهر هنا قرارات الكاشفين التي تحتاج اعتمادًا.',
                )
              else
                ...pendingDecision.map((assignment) =>
                    _DecisionReviewTile(assignment: assignment)),
              const SizedBox(height: 20),
              Text('أداء الفرق',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              const EmptyState(
                icon: Icons.groups_outlined,
                title: 'بيانات أداء الفرق غير متاحة بعد',
                subtitle:
                    'ستظهر مهام الكاشفين والمتحصلين بعد توفير بيانات الأداء من النظام.',
              ),
            ],
          );
        },
      ),
    );
  }
}

class _DecisionReviewTile extends ConsumerWidget {
  final ReadingAssignment assignment;

  const _DecisionReviewTile({required this.assignment});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(assignment.customer.name,
                style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text(
                'عداد ${assignment.meter.meterNumber} · متوسط ${assignment.averageConsumption.toStringAsFixed(0)} kWh'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: () => _setStatus(context, ref,
                        AssignmentStatus.rejected, 'تم رفض القرار للمراجعة'),
                    icon: const Icon(Icons.close_rounded),
                    label: const Text('رفض'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => _setStatus(context, ref,
                        AssignmentStatus.read, 'تم اعتماد القراءة'),
                    icon: const Icon(Icons.check_rounded),
                    label: const Text('اعتماد'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _setStatus(BuildContext context, WidgetRef ref,
      AssignmentStatus status, String message) async {
    await ref
        .read(assignmentRepositoryProvider)
        .markStatus(assignment.id, status);
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }
}

