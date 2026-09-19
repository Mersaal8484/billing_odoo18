import 'package:flutter/services.dart' show rootBundle;
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart' as printing;

import '../../features/collections/domain/collection_models.dart';

/// Builds a PDF document for the collection receipt.
/// يُنتج PDF مطابقاً تماماً لشاشة إشعار "سند التحصيل" في التطبيق.
class PdfReceiptBuilder {
  static const _logoAssetPath = 'assets/icons/pec_logo.png';

  static Future<pw.Document> build(
    CollectionReceipt receipt, {
    String? collectorName,
  }) async {
    final doc = pw.Document(
      title: 'سند-${receipt.displayName.isNotEmpty ? receipt.displayName : receipt.reference}',
      author: 'المؤسسة العامة للكهرباء',
    );

    final logoImage = await _loadLogo();
    final arabicFont = await _loadArabicFont();
    final arabicFontBold = await _loadArabicFontBold();

    doc.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.a5,
        textDirection: pw.TextDirection.rtl,
        margin: const pw.EdgeInsets.symmetric(horizontal: 24, vertical: 32),
        build: (pw.Context ctx) => _buildBody(
          receipt: receipt,
          collectorName: collectorName,
          logoImage: logoImage,
          arabicFont: arabicFont,
          arabicFontBold: arabicFontBold ?? arabicFont,
        ),
      ),
    );

    return doc;
  }

  static pw.Widget _buildBody({
    required CollectionReceipt receipt,
    required String? collectorName,
    required pw.ImageProvider? logoImage,
    required pw.Font? arabicFont,
    required pw.Font? arabicFontBold,
  }) {
    final base = pw.TextStyle(font: arabicFont, fontSize: 13);
    final bold = pw.TextStyle(font: arabicFontBold, fontSize: 13, fontWeight: pw.FontWeight.bold);
    final title = pw.TextStyle(font: arabicFontBold, fontSize: 20, fontWeight: pw.FontWeight.bold);
    final dateSmall = pw.TextStyle(font: arabicFont, fontSize: 11, color: PdfColors.grey700);
    final amountStyle = pw.TextStyle(
      font: arabicFontBold,
      fontSize: 14,
      fontWeight: pw.FontWeight.bold,
      color: PdfColors.green700,
    );

    final dateStr = DateFormat('HH:mm:ss yyyy-MM-dd').format(receipt.paidAt);
    final paymentLabel = _methodLabel(receipt.method);
    final receiptNo = receipt.displayName.isNotEmpty
        ? receipt.displayName
        : receipt.reference;

    // قائمة صفوف البيانات بنفس ترتيب الشاشة
    final rows = <_RowData>[
      _RowData('رقم السند', receiptNo, isBold: true, textDirection: pw.TextDirection.ltr),
      _RowData('المشترك', receipt.account.customer.name, textDirection: pw.TextDirection.rtl),
      _RowData('رقم الحساب', receipt.account.customer.accountNumber, textDirection: pw.TextDirection.ltr),
      _RowData('رقم العداد', receipt.account.meter.meterNumber, textDirection: pw.TextDirection.ltr),
      _RowData('المبلغ المحصّل', '${receipt.amount.toStringAsFixed(0)} ريال', isAmount: true, textDirection: pw.TextDirection.rtl),
      _RowData('طريقة الدفع', paymentLabel, textDirection: pw.TextDirection.rtl),
      _RowData('التاريخ', dateStr, textDirection: pw.TextDirection.ltr),
      if (collectorName != null && collectorName.trim().isNotEmpty)
        _RowData('المحصل', collectorName.trim(), textDirection: pw.TextDirection.rtl),
    ];

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.stretch,
      children: [
        // ── الشعار في المنتصف ──────────────────────────────────────────
        pw.Center(
          child: logoImage != null
              ? pw.Image(logoImage, width: 80, height: 80, fit: pw.BoxFit.contain)
              : pw.SizedBox(height: 80),
        ),
        pw.SizedBox(height: 10),

        // ── عنوان السند ────────────────────────────────────────────────
        pw.Center(child: pw.Text('سند قبض ($paymentLabel)', style: title)),
        pw.SizedBox(height: 4),

        // ── التاريخ ────────────────────────────────────────────────────
        pw.Center(child: pw.Text(dateStr, style: dateSmall, textDirection: pw.TextDirection.ltr)),
        pw.SizedBox(height: 20),

        // ── بطاقة البيانات الرمادية ────────────────────────────────────
        pw.Container(
          width: double.infinity,
          decoration: const pw.BoxDecoration(
            color: PdfColors.grey100,
            borderRadius: pw.BorderRadius.all(pw.Radius.circular(10)),
          ),
          padding: const pw.EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: pw.Table(
            columnWidths: {
              0: const pw.FlexColumnWidth(1.5), // التسمية (يسار) — تُدفع لأقصى الحافة اليسرى
              1: const pw.FlexColumnWidth(1.5), // القيمة (يمين) — تُدفع لأقصى الحافة اليمنى
            },
            border: const pw.TableBorder(
              horizontalInside: pw.BorderSide(color: PdfColors.grey300, width: 0.5),
            ),
            children: rows.map((row) {
              final valueStyle = row.isAmount
                  ? amountStyle
                  : row.isBold
                      ? bold.copyWith(fontSize: 14)
                      : base;
              return pw.TableRow(
                children: [
                  // العمود 0 = التسمية — الآن تُحاذى لأقصى اليسار الحقيقي
                  // (بدل الاتجاه نحو خط المنتصف الذي كان يسبب تكدّس النصين معاً)
                  pw.Padding(
                    padding: const pw.EdgeInsets.symmetric(vertical: 9),
                    child: pw.Text(
                      row.label,
                      style: base.copyWith(color: PdfColors.grey700),
                      textDirection: pw.TextDirection.rtl,
                      textAlign: pw.TextAlign.left,
                    ),
                  ),
                  // العمود 1 = القيمة — الآن تُحاذى لأقصى اليمين الحقيقي
                  pw.Padding(
                    padding: const pw.EdgeInsets.symmetric(vertical: 9),
                    child: pw.Text(
                      row.value,
                      style: valueStyle,
                      textDirection: row.textDirection,
                      textAlign: pw.TextAlign.right,
                    ),
                  ),
                ],
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  // ─── Font & Image Loaders ──────────────────────────────────────────────────

  static Future<pw.ImageProvider?> _loadLogo() async {
    try {
      final data = await rootBundle.load(_logoAssetPath);
      return pw.MemoryImage(data.buffer.asUint8List());
    } catch (_) {
      return null;
    }
  }

  static Future<pw.Font?> _loadArabicFont() async {
    try {
      return await printing.PdfGoogleFonts.amiriRegular();
    } catch (_) {
      try {
        return await printing.PdfGoogleFonts.cairoRegular();
      } catch (_) {
        return null;
      }
    }
  }

  static Future<pw.Font?> _loadArabicFontBold() async {
    try {
      return await printing.PdfGoogleFonts.amiriBold();
    } catch (_) {
      try {
        return await printing.PdfGoogleFonts.cairoBold();
      } catch (_) {
        return null;
      }
    }
  }

  static String _methodLabel(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };
}

class _RowData {
  final String label;
  final String value;
  final bool isBold;
  final bool isAmount;
  final pw.TextDirection textDirection;

  const _RowData(this.label, this.value, {this.isBold = false, this.isAmount = false, this.textDirection = pw.TextDirection.rtl});
}
