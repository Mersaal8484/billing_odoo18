import 'package:esc_pos_utils_plus/esc_pos_utils_plus.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:image/image.dart' as img;

import '../../features/collections/domain/collection_models.dart';

/// Builds ESC/POS bytes for 80mm Bluetooth thermal printers.
class CollectionReceiptBuilder {
  static const _logoAssetPath = 'assets/icons/pec_logo.png';

  // Cached after first successful load so we don't decode the PNG on every
  // print. If loading/decoding ever fails, this stays null and the receipt
  // simply prints without a logo — it never blocks or breaks printing.
  static img.Image? _logoImage;
  static bool _logoLoadAttempted = false;

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

  static Future<void> _loadLogo() async {
    if (_logoLoadAttempted) return;
    _logoLoadAttempted = true;
    try {
      final data = await rootBundle.load(_logoAssetPath);
      final decoded = img.decodeImage(data.buffer.asUint8List());
      if (decoded == null) return;
      // 80mm paper prints at ~576 dots wide; keep the logo comfortably
      // narrower than that so it stays centered with margin either side.
      final resized = img.copyResize(decoded, width: 300);
      _logoImage = resized;
    } catch (_) {
      // Logo missing or undecodable: receipt still prints without it.
      _logoImage = null;
    }
  }

  static Future<List<int>> build(
    CollectionReceipt receipt, {
    String? collectorName,
  }) async {
    await _loadLogo();

    final profile = await CapabilityProfile.load();
    final generator = Generator(PaperSize.mm80, profile);
    final bytes = <int>[];

    bytes.addAll(generator.reset());

    if (_logoImage != null) {
      bytes.addAll(generator.image(_logoImage!, align: PosAlign.center));
      bytes.addAll(generator.emptyLines(1));
    }

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
    if (collectorName != null && collectorName.trim().isNotEmpty) {
      bytes.addAll(_row(generator, 'اسم المحصل', collectorName.trim()));
    }
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
