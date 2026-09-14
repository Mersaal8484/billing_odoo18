/// Mirrors the subset of utility.reading (utility_core/utility_billing)
/// that the field app owns. Anything computed server-side (consumption,
/// consumption_alert, previous_reading) is NOT modeled here — the app
/// shows those only after the ERP returns them post-sync; it never
/// recomputes billing-relevant figures locally.
enum ReadingCategory { customer, transformer, feeder }

enum ReadingSyncStatus {
  draft,            // captured offline, not yet queued
  pendingDataSync,  // in Pipeline A queue
  dataSynced,       // ERP has the reading record; image may still be pending
  pendingImageSync, // in Pipeline B queue
  synced,           // fully synced, data + image
  error,            // Pipeline A failed after retries — needs user attention
}

class MeterReading {
  final String id;           // local uuid — stable identity before any remote id exists
  final int? remoteId;
  final int meterRemoteId;

  /// رقم العداد النصي (مثل "100004") — يطابق utility.meter.meter_number في Odoo.
  /// يُملأ من نتيجة readingApi.lookupMeter() أو من بيانات الـ assignment.
  /// الـ SyncEngine يستخدمه بدلاً من meterRemoteId.toString().
  final String? meterNumber;

  final double readingValue;
  final DateTime readingDate;
  final ReadingCategory category;
  final bool isEstimated;
  final String? remarks;
  final String? imageLocalPath;
  final String? imageSecondaryLocalPath;
  final String? photoUuid;
  final ReadingSyncStatus syncStatus;
  final String? lastError;

  /// بصمة الفترة (date.range id) التي كانت مفتوحة فعلياً وقت التقاط هذه
  /// القراءة ميدانياً — تُملأ من `_MeterInfo.currentPeriodId` عند الحفظ.
  /// [SyncEngine] يقارنها بالفترة المفتوحة حالياً وقت الرفع؛ إن اختلفتا لا
  /// تُرفع تلقائياً (تمنع إلصاق قراءة من فترة مغلقة بفترة جديدة بالخطأ).
  /// null فقط للقراءات القديمة المحفوظة قبل إضافة هذا الحقل.
  final int? capturedPeriodId;

  const MeterReading({
    required this.id,
    this.remoteId,
    required this.meterRemoteId,
    this.meterNumber,
    required this.readingValue,
    required this.readingDate,
    this.category = ReadingCategory.customer,
    this.isEstimated = false,
    this.remarks,
    this.imageLocalPath,
    this.imageSecondaryLocalPath,
    this.photoUuid,
    this.syncStatus = ReadingSyncStatus.draft,
    this.lastError,
    this.capturedPeriodId,
  });

  MeterReading copyWith({
    double? readingValue,
    String? meterNumber,
    String? remarks,
    String? imageLocalPath,
    String? photoUuid,
    ReadingSyncStatus? syncStatus,
    String? lastError,
  }) {
    return MeterReading(
      id: id,
      remoteId: remoteId,
      meterRemoteId: meterRemoteId,
      meterNumber: meterNumber ?? this.meterNumber,
      readingValue: readingValue ?? this.readingValue,
      readingDate: readingDate,
      category: category,
      isEstimated: isEstimated,
      remarks: remarks ?? this.remarks,
      imageLocalPath: imageLocalPath ?? this.imageLocalPath,
      imageSecondaryLocalPath: imageSecondaryLocalPath,
      photoUuid: photoUuid ?? this.photoUuid,
      syncStatus: syncStatus ?? this.syncStatus,
      lastError: lastError,
      capturedPeriodId: capturedPeriodId,
    );
  }

  /// Client-side sanity check only — mirrors the *shape* of the ERP's
  /// billable-reading photo requirement (action_submit_review) so the
  /// reader gets the same feedback offline that they'd get on submit.
  /// This is NOT a substitute for server-side validation.
  bool get requiresPhoto => category == ReadingCategory.customer;
  bool get isReadyToQueue => !requiresPhoto || imageLocalPath != null;

  /// رقم العداد الفعلي المُرسل للخادم — يُفضّل meterNumber إذا كان متاحاً
  String get effectiveMeterNumber =>
      meterNumber?.isNotEmpty == true ? meterNumber! : meterRemoteId.toString();
}

/// Repository contract the UI depends on.
abstract class ReadingRepository {
  Stream<List<MeterReading>> watchReadingsForPeriod(int periodId);
  Future<MeterReading> saveDraft(MeterReading reading);
  Future<void> enqueueForSync(String readingId);
  Future<void> retry(String readingId);
}
