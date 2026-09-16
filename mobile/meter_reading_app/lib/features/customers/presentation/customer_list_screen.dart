import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../data/odoo_assignment_repository.dart';
import '../domain/entities.dart';

class CustomerListScreen extends ConsumerStatefulWidget {
  const CustomerListScreen({super.key});

  @override
  ConsumerState<CustomerListScreen> createState() => _CustomerListScreenState();
}

class _CustomerListScreenState extends ConsumerState<CustomerListScreen> {
  String _query = '';
  AssignmentStatus? _filter;
  bool _syncing = false;
  String? _periodName;
  String? _periodMessage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncAssignments());
  }

  Future<void> _syncAssignments() async {
    if (_syncing) return;
    setState(() => _syncing = true);

    final result = await ref
        .read(assignmentRepositoryProvider)
        .syncOpenPeriodAssignments();
    if (!mounted) return;

    setState(() {
      _periodName = result.periodName;
      _periodMessage = result.hasOpenPeriod
          ? null
          : (result.message ?? 'لا توجد فترة قراءة مفتوحة حاليًا.');
      _syncing = false;
    });

    final message = !result.success
        ? 'تعذر تحديث مهام الكاشف: ${result.message ?? 'خطأ غير معروف'}'
        : result.hasOpenPeriod
            ? 'تم تنزيل ${result.count} مشترك للفترة: ${result.periodName ?? ''}'
            : _periodMessage!;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor:
            result.success ? null : Theme.of(context).colorScheme.error,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final query = AssignmentQuery(text: _query, status: _filter);
    final assignments = ref.watch(assignmentsProvider(query));

    return Scaffold(
      appBar: AppBar(title: const Text('مهام الكاشف')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _syncing ? null : _syncAssignments,
                icon: _syncing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync_rounded),
                label: Text(
                  _syncing ? 'جارٍ تنزيل المشتركين...' : 'مزامنة المشتركين',
                ),
              ),
            ),
          ),
          if (_periodName != null || _periodMessage != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: _ReaderPeriodBanner(
                text: _periodName != null
                    ? 'فترة القراءة الحالية: $_periodName'
                    : _periodMessage!,
                active: _periodName != null,
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: FilledButton.icon(
              onPressed: () => context.push('/customers/qr'),
              icon: const Icon(Icons.qr_code_scanner_rounded),
              label: const Text('مسح QR'),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              onChanged: (value) => setState(() => _query = value),
              decoration: const InputDecoration(
                hintText: 'ابحث باسم المشترك أو رقم الحساب أو رقم العداد',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                _FilterChip(
                    label: 'الكل',
                    selected: _filter == null,
                    onTap: () => setState(() => _filter = null)),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'متبقي',
                  selected: _filter == AssignmentStatus.pending,
                  onTap: () =>
                      setState(() => _filter = AssignmentStatus.pending),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'مكتمل',
                  selected: _filter == AssignmentStatus.read,
                  onTap: () => setState(() => _filter = AssignmentStatus.read),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: assignments.when(
              loading: () => const LoadingState(),
              error: (e, _) => ErrorState(message: 'تعذر تحميل القائمة: $e'),
              data: (list) {
                // محاولة استخراج رسالة خطأ من المستودع لو فشل الـ API
                final error = (ref.read(assignmentRepositoryProvider) as OdooAssignmentRepository).lastError;
                if (error != null && list.isEmpty) {
                  return ErrorState(message: 'خطأ أثناء جلب البيانات: $error');
                }

                if (list.isEmpty) {
                  return const EmptyState(
                    icon: Icons.search_off_rounded,
                    title: 'لا توجد نتائج',
                    subtitle: 'جرّب تعديل كلمات البحث أو الفلتر.',
                  );
                }
                return ListView.separated(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 4),
                  itemBuilder: (context, i) =>
                      _AssignmentTile(assignment: list[i]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ReaderPeriodBanner extends StatelessWidget {
  const _ReaderPeriodBanner({required this.text, required this.active});

  final String text;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: active ? colors.primaryContainer : colors.errorContainer,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: active ? colors.onPrimaryContainer : colors.onErrorContainer,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip(
      {required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
        label: Text(label), selected: selected, onSelected: (_) => onTap());
  }
}

class _AssignmentTile extends StatelessWidget {
  final ReadingAssignment assignment;

  const _AssignmentTile({required this.assignment});

  @override
  Widget build(BuildContext context) {
    final status = _statusInfo(context, assignment.status);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: ListTile(
        onTap: () => context.push('/customers/${assignment.id}'),
        leading: CircleAvatar(
          backgroundColor: status.color.withValues(alpha: 0.14),
          child: Icon(status.icon, color: status.color),
        ),
        title: Text(assignment.customer.name,
            style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            '${assignment.customer.accountNumber} · عداد ${assignment.meter.meterNumber}'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(status.label,
                style: TextStyle(
                    color: status.color,
                    fontWeight: FontWeight.w800,
                    fontSize: 12)),
            Text(assignment.customer.areaName ?? '',
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }

  StatusVisual _statusInfo(BuildContext context, AssignmentStatus status) =>
      switch (status) {
        AssignmentStatus.pending =>
          const StatusVisual('متبقي', Icons.speed_rounded, Colors.orange),
        AssignmentStatus.pendingDecision =>
          const StatusVisual('قرار', Icons.rule_rounded, Colors.blue),
        AssignmentStatus.read => StatusVisual('مكتمل', Icons.check_rounded,
            Theme.of(context).colorScheme.primary),
        AssignmentStatus.rejected => StatusVisual(
            'مرفوض', Icons.close_rounded, Theme.of(context).colorScheme.error),
        AssignmentStatus.escalated =>
          const StatusVisual('مصعد', Icons.build_outlined, Colors.deepPurple),
        AssignmentStatus.skipped =>
          const StatusVisual('متجاوز', Icons.skip_next_rounded, Colors.grey),
      };
}
