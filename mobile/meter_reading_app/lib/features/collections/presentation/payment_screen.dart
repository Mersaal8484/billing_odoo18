import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

/// Posts cash to the current invoice then explicitly reconciles any remainder
/// against the same customer's prior receivables, oldest due invoice first.
class PaymentScreen extends ConsumerStatefulWidget {
  const PaymentScreen({super.key, required this.accountId, this.initialInvoice});
  final String accountId;
  final CollectionInvoice? initialInvoice;

  @override
  ConsumerState<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends ConsumerState<PaymentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amount = TextEditingController();
  CollectionAccount? _account;
  CollectionInvoice? _invoice;
  Object? _error;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
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
      final invoices = account.invoices
          .where((item) => item.amountResidual > 0)
          .toList();
      final initialId = widget.initialInvoice?.invoiceId;
      final selected = invoices.cast<CollectionInvoice?>().firstWhere(
            (item) => item?.invoiceId == initialId,
            orElse: () => invoices.isEmpty ? null : invoices.first,
          );
      if (selected == null) {
        throw StateError('لا توجد فاتورة محاسبية قابلة للتحصيل.');
      }
      _amount.text = account.dueTotal.toStringAsFixed(2);
      if (mounted) {
        setState(() {
          _account = account;
          _invoice = selected;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final account = _account!;
    final invoice = _invoice!;
    final amount = double.parse(_amount.text.trim());
    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('تأكيد التحصيل النقدي'),
            content: Text(
              'المشترك: ${account.customer.name}\n'
              'فاتورة الفترة الحالية: ${invoice.invoiceNumber}\n'
              'المبلغ: ${amount.toStringAsFixed(2)} ر.ي\n\n'
              'يسدد أولاً قيمة الفاتورة الحالية (${account.currentBill.toStringAsFixed(2)} ر.ي)، '
              'ثم المتأخرات الأقدم. أي زيادة تبقى رصيدًا دائنًا للمشترك.',
            ),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('إلغاء')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('تأكيد')),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;

    setState(() => _saving = true);
    try {
      final receipt = await ref.read(collectionRepositoryProvider).collect(
            accountId: account.id,
            invoice: invoice,
            amount: amount,
            method: PaymentMethod.cash,
          );
      if (mounted) {
        context.go('/collector/receipt/${account.id}', extra: receipt);
      }
    } on OdooSessionExpiredException {
      _show('انتهت الجلسة، سجّل الدخول مجدداً.', error: true);
    } on OdooApiException catch (error) {
      _show(error.message, error: true);
    } catch (error) {
      _show('تعذر تسجيل التحصيل: $error', error: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _show(String message, {required bool error}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? Theme.of(context).colorScheme.error : null,
    ));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('تحصيل نقدي')),
        body: _loading
            ? const LoadingState()
            : _error != null
                ? ErrorState(
                    message: 'تعذر تجهيز التحصيل: $_error', onRetry: _load)
                : _form(),
      );

  Widget _form() {
    final account = _account!;
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              title: Text(account.customer.name),
              subtitle: Text(
                  'عداد ${account.meter.meterNumber} · ${account.customer.accountNumber}'),
            ),
          ),
          const SizedBox(height: 12),
          InputDecorator(
            decoration: const InputDecoration(
              labelText: 'فاتورة الفترة الحالية',
              border: OutlineInputBorder(),
            ),
            child: Text(
              '${_invoice!.invoiceNumber} — ${_invoice!.amountResidual.toStringAsFixed(2)} ر.ي',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            color: Theme.of(context).colorScheme.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _AmountRow('الفاتورة الحالية', account.currentBill),
                  const SizedBox(height: 6),
                  _AmountRow('متأخرات سابقة', account.debtAmount),
                  const Divider(height: 18),
                  _AmountRow(
                    'إجمالي المطلوب',
                    account.dueTotal,
                    emphasized: true,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _amount,
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))
            ],
            decoration: const InputDecoration(
                labelText: 'المبلغ النقدي',
                suffixText: 'ر.ي',
                border: OutlineInputBorder()),
            validator: (value) {
              final amount = double.tryParse(value ?? '');
              if (amount == null || amount <= 0) {
                return 'أدخل مبلغاً صحيحاً أكبر من صفر.';
              }
              return null;
            },
          ),
          const SizedBox(height: 12),
          const Card(
            child: ListTile(
              leading: Icon(Icons.payments_outlined),
              title: Text('نقدي — عهدة المحصل'),
              subtitle: Text('لا يُنشأ سند أو تحصيل محلي قبل تأكيد السيرفر.'),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _saving ? null : _submit,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.check_circle_outline),
            label: Text(_saving ? 'جارٍ الترحيل...' : 'تأكيد التحصيل'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52)),
          ),
        ],
      ),
    );
  }
}

class _AmountRow extends StatelessWidget {
  const _AmountRow(this.label, this.amount, {this.emphasized = false});

  final String label;
  final double amount;
  final bool emphasized;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Expanded(child: Text(label)),
          Text(
            '${amount.toStringAsFixed(2)} ر.ي',
            style: TextStyle(
              fontWeight: emphasized ? FontWeight.w800 : FontWeight.w600,
              fontSize: emphasized ? 16 : 14,
            ),
          ),
        ],
      );
}
