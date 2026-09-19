import 'package:esc_pos_utils_plus/esc_pos_utils_plus.dart';

import '../../features/collections/domain/collection_models.dart';

/// Builds ESC/POS bytes for 80mm Bluetooth thermal printers.
class CollectionReceiptBuilder {
  static const _headerStyles = PosStyles(
    align: PosAlign.center,
    bold: true,
    height: PosTextSize.size2,
    width: PosTextSize.size2,
    codeTable: 'CP864',
  );

  static const _titleStyles = PosStyles(
    align: PosAlign.center,
    bold: true,
    codeTable: 'CP864',
  );

  static const _labelStyles = PosStyles(
    bold: true,
    codeTable: 'CP864',
  );

  static const _valueStyles = PosStyles(
    align: PosAlign.right,
    codeTable: 'CP864',
  );

  static Future<List<int>> build(CollectionReceipt receipt) async {
    final profile = await CapabilityProfile.load();
    final generator = Generator(PaperSize.mm80, profile);
    final bytes = <int>[];

    bytes.addAll(generator.reset());
    bytes.addAll(generator.text(
      'المؤسسة العامة للكهرباء',
      styles: _headerStyles,
    ));
    bytes.addAll(generator.text(
      'إيصال تحصيل',
      styles: _titleStyles,
    ));
    bytes.addAll(generator.text(
      'صنعاء — اليمن',
      styles: const PosStyles(align: PosAlign.center, codeTable: 'CP864'),
    ));
    bytes.addAll(generator.hr());

    bytes.addAll(_row(generator, 'المرجع', receipt.reference));
    bytes.addAll(_row(generator, 'المشترك', receipt.account.customer.name));
    bytes.addAll(
        _row(generator, 'رقم الحساب', receipt.account.customer.accountNumber));
    bytes.addAll(
        _row(generator, 'رقم العداد', receipt.account.meter.meterNumber));
    bytes.addAll(_row(
      generator,
      'المبلغ',
      '${receipt.amount.toStringAsFixed(0)} YER',
    ));
    bytes.addAll(_row(generator, 'طريقة الدفع', _methodLabel(receipt.method)));
    bytes.addAll(_row(generator, 'التاريخ', _dateTime(receipt.paidAt)));

    bytes.addAll(generator.hr());
    bytes.addAll(generator.text(
      'شكراً لكم',
      styles: const PosStyles(align: PosAlign.center, codeTable: 'CP864'),
    ));
    bytes.addAll(generator.feed(2));
    bytes.addAll(generator.cut());
    return bytes;
  }

  static List<int> _row(Generator generator, String label, String value) {
    return generator.row([
      PosColumn(text: label, width: 5, styles: _labelStyles),
      PosColumn(text: value, width: 7, styles: _valueStyles),
    ]);
  }

  static String _methodLabel(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };

  static String _dateTime(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')} '
      '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
}
