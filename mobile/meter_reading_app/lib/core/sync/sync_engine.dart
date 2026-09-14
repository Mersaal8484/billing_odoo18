import 'dart:async';
import 'dart:io';

import '../../features/readings/data/drift_reading_repository.dart';
import '../../features/readings/domain/reading.dart';
import '../database/app_database.dart';
import '../network/odoo_api_client.dart';
import '../network/reading_api_service.dart';
import 'sync_settings_service.dart';

enum ConnectivityState { online, offline }

class PipelineStats {
  final int pending;
  final int inProgress;
  final int succeeded;
  final int failed;
  const PipelineStats({
    this.pending = 0,
    this.inProgress = 0,
    this.succeeded = 0,
    this.failed = 0,
  });
}

class SyncSnapshot {
  final ConnectivityState connectivity;
  final PipelineStats batchPipeline;
  final DateTime? lastSuccessfulSync;

  /// true = انتهت الجلسة → وجّه المستخدم لشاشة تسجيل الدخول
  final bool sessionExpired;

  const SyncSnapshot({
    required this.connectivity,
    required this.batchPipeline,
    this.lastSuccessfulSync,
    this.sessionExpired = false,
  });
}

/// SyncEngine الإنتاجي — يستخدم [DriftReadingRepository] + [ReadingApiService].
///
/// ملاحظة meterNumber: الخادم يطابق القراءات بالعداد عبر
/// كل قراءة ترسل معرّف العداد في Odoo (`meter_id`) بوصفه المرجع المعتمد.
/// رقم العداد النصي يُرسل عندما يكون متاحاً لأغراض العرض والتدقيق، ولا يُستبدل
/// أبداً بالمعرّف الرقمي عند استعادة قراءة مؤجلة من قاعدة البيانات المحلية.
class SyncEngine {
  final DriftReadingRepository readingRepository;
  final AppDatabase db;
  final SyncSettingsService settingsService;
  final ReadingApiService readingApi;

  SyncSnapshot _last = const SyncSnapshot(
    connectivity: ConnectivityState.online,
    batchPipeline: PipelineStats(),
  );

  final _ctrl = StreamController<SyncSnapshot>.broadcast();
  Timer? _timer;
  ConnectivityState _connectivity = ConnectivityState.online;
  DateTime? _lastSuccess;

  SyncEngine(this.readingRepository, this.db, this.settingsService, this.readingApi);

  Stream<SyncSnapshot> get snapshots async* {
    yield _last;
    yield* _ctrl.stream;
  }

  void setConnectivity(ConnectivityState state) {
    _connectivity = state;
    _publish();
    if (state == ConnectivityState.online) _tick();
  }

  void start() {
    _timer = Timer.periodic(const Duration(seconds: 15), (_) => _tick());
    _publish();
  }

  void stop() => _timer?.cancel();

  void dispose() {
    stop();
    _ctrl.close();
  }

  /// الواجهة الرئيسية: يُستدعى بعد حفظ القراءة من شاشة إدخال القراءة
  Future<void> enqueue(MeterReading reading) async {
    await readingRepository.updateSyncStatus(
        reading.id, ReadingSyncStatus.pendingDataSync);
    _publish();

    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate && _connectivity == ConnectivityState.online) {
      await _upload([reading]);
      return;
    }
    await _checkThreshold();
  }

  /// Returns failed readings to the queue, then uploads them immediately.
  /// This deliberately bypasses batch-threshold waiting for an explicit retry.
  Future<void> retryFailed() async {
    final failed = await readingRepository.getByStatus('error');
    for (final r in failed) {
      await enqueue(r);
    }
    await syncNow();
  }

  /// زر "مزامنة الآن" في sync_center_screen
  Future<void> syncNow() async {
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
    } else {
      await _buildAndUploadBatch();
    }
  }

  // ── Pipeline internals ────────────────────────────────────────────────────

  Future<void> _tick() async {
    if (_connectivity == ConnectivityState.offline) return;
    final mode = await settingsService.getSyncMode();
    if (mode == SyncMode.immediate) {
      await _uploadPendingSingles();
    } else {
      await _checkThreshold();
    }
  }

  Future<void> _checkThreshold() async {
    final threshold = await settingsService.getBatchSize();
    final pending = await readingRepository.getByStatus('pending');
    if (pending.length >= threshold) await _buildAndUploadBatch();
  }

  Future<void> _uploadPendingSingles() async {
    if (_connectivity == ConnectivityState.offline) return;
    final pending = await readingRepository.getByStatus('pending');
    for (final r in pending) {
      await _upload([r]);
    }
  }

  Future<void> _buildAndUploadBatch() async {
    if (_connectivity == ConnectivityState.offline) return;
    final size = await settingsService.getBatchSize();
    final pending = await readingRepository.getByStatus('pending');
    if (pending.isEmpty) return;
    await _upload(pending.take(size).toList());
  }

  /// المسار الموحد للرفع:
  /// 1. تحديد الفترة الحالية
  /// 2. إنشاء batch على الخادم
  /// 3. رفع بيانات القراءات (JSON)
  /// 4. رفع صور كل قراءة (multipart)
  /// 5. تأكيد الـ batch
  Future<void> _upload(List<MeterReading> readings) async {
    if (readings.isEmpty) return;

    // علامة "جاري الرفع"
    for (final r in readings) {
      await readingRepository.updateSyncStatus(
          r.id, ReadingSyncStatus.pendingDataSync);
    }
    _publish();

    // يُملأ داخل try بعد فلترة بصمة الفترة؛ يبقى متاحاً لكتل catch أدناه
    // حتى لا تُعاد كتابة رسالة الخطأ الواضحة لقراءات الفترة المغلقة
    // برسالة خطأ عامة عند فشل لاحق في نفس عملية الرفع.
    List<MeterReading> readingsToUpload = readings;

    try {
      final periodId = await readingApi.getCurrentPeriodId();

      // ── فلترة "بصمة الفترة" ──────────────────────────────────────────
      // قراءة أُخذت ميدانياً في فترة أُغلقت لاحقاً (لم تُزامَن في وقتها)
      // لا يجب أن تُلصق تلقائياً بالفترة المفتوحة الآن. القراءات القديمة
      // (قبل إضافة هذا الحقل، capturedPeriodId == null) تُعامل كما كانت
      // سابقاً حفاظاً على التوافق مع البيانات المحفوظة مسبقاً.
      final upload = <MeterReading>[];
      final staleReadings = <MeterReading>[];
      for (final r in readings) {
        if (r.capturedPeriodId != null && r.capturedPeriodId != periodId) {
          staleReadings.add(r);
        } else {
          upload.add(r);
        }
      }
      readingsToUpload = upload;
      if (staleReadings.isNotEmpty) {
        for (final r in staleReadings) {
          await readingRepository.updateSyncStatus(
            r.id,
            ReadingSyncStatus.error,
            error:
                'هذه القراءة أُخذت في فترة مغلقة (رقم ${r.capturedPeriodId}) '
                'وليست الفترة المفتوحة حالياً (رقم $periodId). لم تُرفع '
                'تلقائياً — راجعها من طابور المزامنة قبل إعادة المحاولة.',
          );
        }
      }
      if (readingsToUpload.isEmpty) {
        _publish();
        return;
      }

      final batchResult = await readingApi.createBatch(dateRangeId: periodId);
      final batchId = batchResult['batch_id'] as int;

      // رفع البيانات
      final payloads = <MeterReadingPayload>[];
      final imageFilesByReadingId = <String, File>{};
      for (final reading in readingsToUpload) {
        File? imageFile;
        if (reading.imageLocalPath != null) {
          final candidate = File(reading.imageLocalPath!);
          if (await candidate.exists()) {
            imageFile = candidate;
            imageFilesByReadingId[reading.id] = candidate;
          }
        }

        payloads.add(MeterReadingPayload(
          meterId: reading.meterRemoteId,
          meterNumber: reading.meterNumber,
          resubmitReadingId: reading.remoteId,
          readingValue: reading.readingValue,
          readingDate: reading.readingDate,
          readingCategory: reading.category.name,
          clientReadingUuid: reading.id,
          imageFilename:
              imageFile?.uri.pathSegments.isNotEmpty == true
                  ? imageFile!.uri.pathSegments.last
                  : null,
        ));
      }
      await readingApi.uploadData(batchId: batchId, readings: payloads);

      // رفع الصور
      for (final r in readingsToUpload) {
        final file = imageFilesByReadingId[r.id];
        if (file == null) continue;
        await readingApi.uploadImageMultipart(
          batchId: batchId,
          imageFile: file,
          readingUuid: r.id,
          filename: file.uri.pathSegments.last,
        );
      }

      // تأكيد الـ batch
      await readingApi.confirmBatch(batchId);

      // تحديث الحالة إلى synced — فقط للقراءات التي فعلاً رُفعت
      // (القراءات المتأخرة عن فترة مغلقة وُسمت بخطأ واضح أعلاه ولا تُلمس هنا)
      for (final r in readingsToUpload) {
        await readingRepository.updateSyncStatus(r.id, ReadingSyncStatus.synced);
      }
      _lastSuccess = DateTime.now();
      _publish();
    } on OdooSessionExpiredException catch (e) {
      // فقط القراءات التي كانت قيد الرفع الفعلي؛ قراءات الفترة المغلقة
      // (إن فُلترت قبل هذا الفشل) تحتفظ برسالتها التفصيلية الخاصة بها.
      for (final r in readingsToUpload) {
        await readingRepository.updateSyncStatus(
            r.id, ReadingSyncStatus.error, error: e.toString());
      }
      // أبلغ الـ UI بانتهاء الجلسة → يُعيد التوجيه لشاشة تسجيل الدخول
      _last = SyncSnapshot(
        connectivity: _connectivity,
        batchPipeline: _last.batchPipeline,
        lastSuccessfulSync: _lastSuccess,
        sessionExpired: true,
      );
      _ctrl.add(_last);
    } catch (e) {
      for (final r in readingsToUpload) {
        await readingRepository.updateSyncStatus(
            r.id, ReadingSyncStatus.error, error: e.toString());
      }
      _publish();
    }
  }

  void _publish() async {
    final pending = await readingRepository.getByStatus('pending');
    final synced = await readingRepository.getByStatus('synced');
    final failed = await readingRepository.getByStatus('error');

    _last = SyncSnapshot(
      connectivity: _connectivity,
      batchPipeline: PipelineStats(
        pending: pending.length,
        inProgress: 0,
        succeeded: synced.length,
        failed: failed.length,
      ),
      lastSuccessfulSync: _lastSuccess,
    );
    _ctrl.add(_last);
  }
}
