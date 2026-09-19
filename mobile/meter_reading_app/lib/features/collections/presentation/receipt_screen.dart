import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:printing/printing.dart';

import '../../../app/providers.dart';
import '../../../core/printing/pdf_receipt_builder.dart';
import '../../../shared/widgets/info_row.dart';
import '../domain/collection_models.dart';

/// شاشة السند — تعرض تفاصيل العملية وتدعم الطباعة الحرارية
class ReceiptScreen extends ConsumerWidget {
  final CollectionReceipt receipt;
  const ReceiptScreen({super.key, required this.receipt});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final collectorName = ref.read(authServiceProvider).currentUser?.name;
    final scheme = Theme.of(context).colorScheme;
    final dateStr = DateFormat('yyyy-MM-dd HH:mm:ss').format(receipt.paidAt);
    
    // استخراج طريقة الدفع لإضافتها في العنوان
    final paymentMethodLabel = _methodLabel(receipt.method);

    return Scaffold(
      appBar: AppBar(
        title: const Text('سند التحصيل'),
        centerTitle: true,
        automaticallyImplyLeading: false,
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          // الشعار
          Center(
            child: Image.asset(
              'assets/icons/pec_logo.png',
              width: 80,
              height: 80,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) {
                // بديل في حال لم يتمكن من تحميل الشعار لأي سبب
                return const Icon(Icons.receipt_long, size: 52, color: Colors.grey);
              },
            ),
          ),
          const SizedBox(height: 12),
          Center(
            child: Text('سند قبض ($paymentMethodLabel)',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
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
              InfoRow(
                  label: 'رقم السند',
                  value: receipt.displayName.isNotEmpty
                      ? receipt.displayName
                      : receipt.reference,
                  labelFontSize: 13,
                  valueFontWeight: FontWeight.bold,
                  valueFontSize: 15),
              InfoRow(
                  label: 'المشترك',
                  value: receipt.account.customer.name,
                  labelFontSize: 13),
              InfoRow(
                  label: 'رقم الحساب',
                  value: receipt.account.customer.accountNumber,
                  labelFontSize: 13),
              InfoRow(
                  label: 'رقم العداد',
                  value: receipt.account.meter.meterNumber,
                  labelFontSize: 13),
              InfoRow(
                  label: 'المبلغ المحصّل',
                  value: '${receipt.amount.toStringAsFixed(0)} ﷼',
                  labelFontSize: 13,
                  valueFontWeight: FontWeight.bold,
                  valueColor: Colors.green,
                  valueFontSize: 15),
              InfoRow(
                  label: 'طريقة الدفع',
                  value: paymentMethodLabel,
                  labelFontSize: 13),
              InfoRow(label: 'التاريخ', value: dateStr, labelFontSize: 13),
              // إضافة اسم المحصل إذا كان موجوداً
              if (collectorName != null && collectorName.trim().isNotEmpty)
                InfoRow(
                    label: 'المحصل',
                    value: collectorName.trim(),
                    labelFontSize: 13),
            ],
          ),
          const SizedBox(height: 24),

          // زر الطباعة الحرارية
          OutlinedButton.icon(
            onPressed: () => _printReceipt(context, ref),
            icon: const Icon(Icons.print_outlined),
            label: const Text('طباعة حرارية'),
            style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 10),

          // زر طباعة / حفظ PDF
          OutlinedButton.icon(
            onPressed: () => _printPdf(context, ref),
            icon: const Icon(Icons.picture_as_pdf_outlined),
            label: const Text('حفظ / طباعة PDF'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              foregroundColor: Colors.deepOrange,
              side: const BorderSide(color: Colors.deepOrange),
            ),
          ),
          const SizedBox(height: 12),

          // زر العودة للقائمة
          FilledButton.icon(
            onPressed: () => context.go('/collector'),
            icon: const Icon(Icons.home_outlined),
            label: const Text('العودة للقائمة'),
            style:
                FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Future<void> _printReceipt(BuildContext context, WidgetRef ref) async {
    try {
      final printer = ref.read(thermalPrinterServiceProvider);
      // اسم المحصل المسجّل دخوله حالياً (نفس حساب Odoo)، يُطبع كسطر إضافي
      // في السند. إن لم تتوفر جلسة أو اسم، يُترك السطر فارغاً بدون أي خطأ.
      final collectorName = ref.read(authServiceProvider).currentUser?.name;
      await printer.printCollectionReceipt(
        receipt,
        collectorName: collectorName,
      );
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

  /// يبني PDF كاملاً (شعار + اسم المحصل + بيانات السند)
  /// ثم يفتح dialog معاينة النظام: طباعة WiFi، حفظ PDF، مشاركة.
  Future<void> _printPdf(BuildContext context, WidgetRef ref) async {
    try {
      final collectorName = ref.read(authServiceProvider).currentUser?.name;
      final doc = await PdfReceiptBuilder.build(
        receipt,
        collectorName: collectorName,
      );
      await Printing.layoutPdf(
        onLayout: (_) async => doc.save(),
        name: 'سند-قبض-${receipt.displayName.isNotEmpty ? receipt.displayName : receipt.reference}',
      );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('خطأ في إنشاء PDF: $e'),
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
          children:
              children.expand((w) => [w, const Divider(height: 16)]).toList()
                ..removeLast(),
        ),
      ),
    );
  }
}
