import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../app/providers.dart';
import '../domain/collection_models.dart';

/// شاشة السند — تعرض تفاصيل العملية وتدعم الطباعة الحرارية
class ReceiptScreen extends ConsumerWidget {
  final CollectionReceipt receipt;
  const ReceiptScreen({super.key, required this.receipt});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final dateStr =
        DateFormat('yyyy-MM-dd HH:mm:ss').format(receipt.paidAt);

    return Scaffold(
      appBar: AppBar(
        title: const Text('سند التحصيل'),
        centerTitle: true,
        automaticallyImplyLeading: false,
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          // أيقونة النجاح
          Center(
            child: Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.green.withOpacity(0.15),
              ),
              child: const Icon(Icons.check_circle_outline,
                  size: 52, color: Colors.green),
            ),
          ),
          const SizedBox(height: 12),
          const Center(
            child: Text('تم التحصيل بنجاح',
                style: TextStyle(
                    fontSize: 20, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(dateStr,
                style: TextStyle(color: scheme.outline, fontSize: 12)),
          ),
          const SizedBox(height: 24),

          // تفاصيل السند
          _ReceiptCard(
            children: [
              _ReceiptRow(
                  label: 'رقم السند',
                  value: receipt.displayName.isNotEmpty
                      ? receipt.displayName
                      : receipt.reference,
                  isBold: true),
              _ReceiptRow(
                  label: 'المشترك', value: receipt.account.customer.name),
              _ReceiptRow(
                  label: 'رقم الحساب',
                  value: receipt.account.customer.accountNumber),
              _ReceiptRow(
                  label: 'رقم العداد',
                  value: receipt.account.meter.meterNumber),
              _ReceiptRow(
                  label: 'المبلغ المحصّل',
                  value: '${receipt.amount.toStringAsFixed(0)} ﷼',
                  isBold: true,
                  valueColor: Colors.green),
              _ReceiptRow(
                  label: 'طريقة الدفع',
                  value: _methodLabel(receipt.method)),
              _ReceiptRow(label: 'التاريخ', value: dateStr),
            ],
          ),
          const SizedBox(height: 24),

          // زر الطباعة
          OutlinedButton.icon(
            onPressed: () => _printReceipt(context, ref),
            icon: const Icon(Icons.print_outlined),
            label: const Text('طباعة السند'),
            style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 12),

          // زر العودة للقائمة
          FilledButton.icon(
            onPressed: () => context.go('/collector'),
            icon: const Icon(Icons.home_outlined),
            label: const Text('العودة للقائمة'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Future<void> _printReceipt(BuildContext context, WidgetRef ref) async {
    try {
      final printer = ref.read(thermalPrinterServiceProvider);
      await printer.printCollectionReceipt(receipt);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تم الإرسال للطابعة ✓')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('خطأ في الطباعة: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    }
  }

  String _methodLabel(PaymentMethod m) => switch (m) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };
}

// ── Widgets مساعدة ────────────────────────────────────────────────────────────

class _ReceiptCard extends StatelessWidget {
  final List<Widget> children;
  const _ReceiptCard({required this.children});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: children
              .expand((w) => [w, const Divider(height: 16)])
              .toList()
            ..removeLast(),
        ),
      ),
    );
  }
}

class _ReceiptRow extends StatelessWidget {
  final String label;
  final String value;
  final bool isBold;
  final Color? valueColor;

  const _ReceiptRow({
    required this.label,
    required this.value,
    this.isBold = false,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
            style: TextStyle(
                color: Theme.of(context).colorScheme.outline,
                fontSize: 13)),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: TextStyle(
              fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
              color: valueColor,
              fontSize: isBold ? 15 : 13,
            ),
          ),
        ),
      ],
    );
  }
}
