import 'dart:async';
import 'package:drift/drift.dart' as drift;
import 'package:flutter/foundation.dart' show visibleForTesting;
import '../../../core/database/app_database.dart' hide Customer, Meter;
import '../../../core/network/odoo_api_client.dart';
import '../domain/entities.dart';
import 'mock_assignment_repository.dart'
    show AssignmentRepository, ReadingAssignmentSyncResult;

class OdooAssignmentRepository implements AssignmentRepository {
  // nullable فقط لتسهيل الاختبارات (تجنّب بناء OdooApiClient حقيقي الذي
  // يحتاج FlutterSecureStorage/path_provider غير متاحين بـ flutter test
  // بدون منصة). بالتطبيق الفعلي الـ provider يمرر دائماً client حقيقي.
  final OdooApiClient? _client;
  final AppDatabase _db;
  final _changeHub = StreamController<List<ReadingAssignment>>.broadcast();
  List<ReadingAssignment> _all = [];
  bool _initialized = false;
  Future<ReadingAssignmentSyncResult>? _inFlightFetch;

  OdooAssignmentRepository(this._client, this._db);

  String? _lastError;
  String? get lastError => _lastError;

  Future<ReadingAssignmentSyncResult> _fetchData() {
    return _inFlightFetch ??= _fetchDataInternal().whenComplete(() {
      _inFlightFetch = null;
    });
  }

  Future<ReadingAssignmentSyncResult> _fetchDataInternal() async {
    try {
      final response =
          await _client!.postJson('/api/v1/utility/reader/subscribers', {});
      if (response['success'] == true) {
        final subs = response['subscribers'] as List<dynamic>? ?? const [];
        final rawPeriod = response['period'];
        final period =
            rawPeriod is Map ? Map<String, dynamic>.from(rawPeriod) : null;
        // ✅ مؤكَّد من كود الـ backend: period_data = {'id': current_period.id, ...}
        final periodId = period != null
            ? int.tryParse(period['id']?.toString() ?? '')
            : null;
        final list = <ReadingAssignment>[];
        final now = DateTime.now();

        for (int i = 0; i < subs.length; i++) {
          final s = Map<String, dynamic>.from(subs[i] as Map);
          final cId = int.tryParse(s['id']?.toString() ?? '');
          if (cId == null) continue;
          final mId = int.tryParse(s['meter_id']?.toString() ?? '');

          // ✅ مؤكَّد من كود الـ backend الفعلي (utility_reader_api.py):
          // last_reading_value = getattr(meter, 'last_reading_value', 0)
          // period['id'] = current_period.id — كلاهما مطابق تماماً.
          // ملاحظة: هذا الـ endpoint لا يُرجع last_reading_date إطلاقاً
          // (فقط last_reading_value)، فيبقى التاريخ null من مصدر الكاش هذا
          // بأمان — يُملأ لاحقاً من /reading/meter/lookup الحي عند الاتصال.
          final lastReadingValue =
              (s['last_reading_value'] as num?)?.toDouble();
          final lastReadingDateStr = s['last_reading_date']?.toString();
          final lastReadingDate = lastReadingDateStr != null
              ? DateTime.tryParse(lastReadingDateStr)
              : null;

          final customer = Customer(
            remoteId: cId,
            customerNumber: s['customer_number']?.toString() ?? '',
            accountNumber: _firstText(
              s,
              ['account_number', 'customer_number', 'subscriber_number'],
              fallback: 'ACC-$cId',
            ),
            name: s['name']?.toString() ?? '',
            address: s['address']?.toString(),
            regionName: s['route_name']?.toString(),
            lastReadingDate: lastReadingDate,
            lastReadingValue: lastReadingValue,
          );

          final meter = Meter(
            remoteId: mId ?? 0,
            meterNumber: s['meter_number']?.toString() ?? '',
            customerRemoteId: customer.remoteId,
            paymentType: MeterPaymentType.postpaid,
          );

          list.add(ReadingAssignment(
            id: 'assign-$cId',
            meter: meter,
            customer: customer,
            periodId: periodId,
            status: _assignmentStatusFromApi(s['reading_status']),
            scheduledAt: now,
            averageConsumption: 0.0,
          ));
        }

        _all = List.unmodifiable(list);
        _lastError = null;
        _notifyListeners();

        // يُشغَّل بالخلفية عمداً (لا await): كتابة الكاش المحلي لا يجب أن
        // تؤخّر عرض البيانات في الواجهة، وهي عملية مستقلة تماماً عن نجاح
        // الجلب نفسه. أي فشل بالكتابة لا يُفشل المزامنة (يُطبع فقط).
        unawaited(_writeToCache(list, periodId).catchError((e) {
          // ignore: avoid_print
          print('⚠️ Assignment cache write failed: $e');
        }));

        return ReadingAssignmentSyncResult(
          success: true,
          hasOpenPeriod: period != null,
          periodName: period?['name']?.toString(),
          count: list.length,
          message: response['message']?.toString(),
        );
      } else {
        _lastError =
            response['error']?.toString() ?? 'API returned success=false';
        _notifyListeners();
        return ReadingAssignmentSyncResult(
          success: false,
          hasOpenPeriod: false,
          count: _all.length,
          message: _lastError,
        );
      }
    } catch (e) {
      _lastError = e.toString();
      _notifyListeners();
      return ReadingAssignmentSyncResult(
        success: false,
        hasOpenPeriod: false,
        count: _all.length,
        message: _lastError,
      );
    }
  }

  AssignmentStatus _assignmentStatusFromApi(dynamic value) => switch (value) {
        'read' => AssignmentStatus.read,
        'rejected' => AssignmentStatus.rejected,
        'pending_decision' => AssignmentStatus.pendingDecision,
        'escalated' => AssignmentStatus.escalated,
        'skipped' => AssignmentStatus.skipped,
        _ => AssignmentStatus.pending,
      };

  String _firstText(
    Map<String, dynamic> values,
    List<String> keys, {
    String fallback = '',
  }) {
    for (final key in keys) {
      final value = values[key];
      if (value == null || value == false) continue;
      final text = value.toString().trim();
      if (text.isNotEmpty) return text;
    }
    return fallback;
  }

  String _cleanIdentifier(String value) => value.trim().toLowerCase();

  Set<String> _payloadCandidates(String payload) {
    final raw = payload.trim();
    final values = <String>{};
    void add(String? value) {
      if (value == null) return;
      final clean = _cleanIdentifier(value);
      if (clean.isNotEmpty) values.add(clean);
    }

    add(raw);
    if (raw.toLowerCase().startsWith('utility:')) {
      add(raw.substring('utility:'.length));
    }

    final parts = raw.split('|').map((part) => part.trim()).toList();
    if (parts.isNotEmpty && parts.first.toUpperCase().startsWith('UTILITY')) {
      // Official meter QR shape:
      // UTILITY-METER|company|meter_number|physical_serial|customer_number|...
      if (parts.length > 2) add(parts[2]);
      if (parts.length > 3) add(parts[3]);
      if (parts.length > 4) add(parts[4]);
      if (parts.length > 8) add(parts[8]);
    }
    return values;
  }

  Set<String> _assignmentIdentifiers(ReadingAssignment assignment) {
    final values = <String>{};
    void add(String? value) {
      if (value == null) return;
      final clean = _cleanIdentifier(value);
      if (clean.isNotEmpty) values.add(clean);
    }

    add(assignment.customer.accountNumber);
    add(assignment.customer.customerNumber);
    add(assignment.meter.meterNumber);
    add(assignment.meter.serialNumber);
    add('UTILITY:${assignment.customer.accountNumber}');
    add('UTILITY:${assignment.customer.customerNumber}');
    add('UTILITY:${assignment.meter.meterNumber}');
    return values;
  }

  void _notifyListeners() {
    if (!_changeHub.isClosed) _changeHub.add(List.unmodifiable(_all));
  }

  /// للاختبارات فقط: يُشغّل نفس مسار كتابة الكاش (_writeToCache) المُستخدَم
  /// داخل _fetchDataInternal بعد مزامنة ناجحة، بدون الحاجة لمحاكاة عميل
  /// HTTP كامل. لا يُستخدم إطلاقاً بالكود الفعلي للتطبيق.
  @visibleForTesting
  Future<void> debugSimulateSuccessfulSync(
          List<ReadingAssignment> list, int periodId) =>
      _writeToCache(list, periodId);

  // ── كاش Drift محلي (offline-first) ────────────────────────────────────
  //
  // يُكتب بعد كل مزامنة ناجحة فقط. مرتبط ببصمة الفترة (Assignments.periodId
  // الموجود أصلاً بالجدول): مزامنة لنفس الفترة تُحدِّث السجلات القائمة
  // (insertOnConflictUpdate)، ومزامنة لفترة مختلفة تمسح الكاش بالكامل أولاً
  // حتى لا يبقى مشتركون من تكليف فترة سابقة معروضين بالخطأ.
  Future<void> _writeToCache(
      List<ReadingAssignment> list, int? periodId) async {
    if (periodId == null) {
      // لا يمكن ختم صف Assignments بدون periodId (العمود NOT NULL) —
      // نتجاهل كتابة الكاش لهذه الدفعة بأمان بدل رمي استثناء أو كتابة
      // بيانات بلا بصمة فترة صحيحة. البيانات تبقى معروضة من الذاكرة
      // (_all) لهذه الجلسة كما كانت قبل هذا التعديل.
      return;
    }

    await _db.transaction(() async {
      final existing =
          await (_db.select(_db.assignments)..limit(1)).getSingleOrNull();
      final previousPeriodId = existing?.periodId;

      if (previousPeriodId != null && previousPeriodId != periodId) {
        // فترة جديدة فُتحت: امسح كاش الفترة السابقة بالكامل قبل إدراج
        // بيانات الفترة الجديدة (ترتيب الحذف يحترم قيود FK: Assignments
        // يشير إلى Meters، وMeters يشير إلى Customers).
        await _db.delete(_db.assignments).go();
        await _db.delete(_db.meters).go();
        await _db.delete(_db.customers).go();
      }

      final now = DateTime.now();
      for (final a in list) {
        await _db.into(_db.customers).insertOnConflictUpdate(
              CustomersCompanion(
                remoteId: drift.Value(a.customer.remoteId),
                accountNumber: drift.Value(a.customer.accountNumber),
                name: drift.Value(a.customer.name),
                address: drift.Value(a.customer.address),
                lastReadingDate: drift.Value(a.customer.lastReadingDate),
                lastReadingValue: drift.Value(a.customer.lastReadingValue),
                lastSyncedAt: drift.Value(now),
              ),
            );

        if (a.meter.remoteId != 0) {
          await _db.into(_db.meters).insertOnConflictUpdate(
                MetersCompanion(
                  remoteId: drift.Value(a.meter.remoteId),
                  meterNumber: drift.Value(a.meter.meterNumber),
                  serialNumber: drift.Value(a.meter.serialNumber),
                  customerRemoteId: drift.Value(a.customer.remoteId),
                  meterType: drift.Value(a.meter.meterType),
                  paymentType: drift.Value(a.meter.paymentType.name),
                  isCouplingMeter: drift.Value(a.meter.isCouplingMeter),
                ),
              );

          await _db.into(_db.assignments).insertOnConflictUpdate(
                AssignmentsCompanion(
                  id: drift.Value(a.id),
                  meterRemoteId: drift.Value(a.meter.remoteId),
                  periodId: drift.Value(periodId),
                  status: drift.Value(a.status.name),
                  downloadedAt: drift.Value(now),
                ),
              );
        }
      }
    });
  }

  /// يُستخدم عند بدء التطبيق قبل أي محاولة اتصال بالشبكة: يقرأ آخر كاش
  /// محفوظ محلياً (إن وُجد) فيتيح عرض قائمة المهام فوراً حتى لو فُتح
  /// التطبيق من الصفر بدون اتصال بعد إغلاقه الكامل مسبقاً.
  Future<List<ReadingAssignment>> loadFromCache() async {
    final assignmentRows = await _db.select(_db.assignments).get();
    if (assignmentRows.isEmpty) return const [];

    final meterRows = await _db.select(_db.meters).get();
    final customerRows = await _db.select(_db.customers).get();
    final metersById = {for (final m in meterRows) m.remoteId: m};
    final customersById = {for (final c in customerRows) c.remoteId: c};

    final list = <ReadingAssignment>[];
    for (final row in assignmentRows) {
      final meterRow = metersById[row.meterRemoteId];
      if (meterRow == null) continue;
      final customerRow = customersById[meterRow.customerRemoteId];
      if (customerRow == null) continue;

      final customer = Customer(
        remoteId: customerRow.remoteId,
        customerNumber: customerRow.accountNumber,
        accountNumber: customerRow.accountNumber,
        name: customerRow.name,
        address: customerRow.address,
        lastReadingDate: customerRow.lastReadingDate,
        lastReadingValue: customerRow.lastReadingValue,
      );

      final meter = Meter(
        remoteId: meterRow.remoteId,
        meterNumber: meterRow.meterNumber,
        serialNumber: meterRow.serialNumber,
        customerRemoteId: meterRow.customerRemoteId,
        paymentType: MeterPaymentType.values.firstWhere(
          (t) => t.name == meterRow.paymentType,
          orElse: () => MeterPaymentType.postpaid,
        ),
        meterType: meterRow.meterType,
        isCouplingMeter: meterRow.isCouplingMeter,
      );

      list.add(ReadingAssignment(
        id: row.id,
        meter: meter,
        customer: customer,
        periodId: row.periodId,
        status: AssignmentStatus.values.firstWhere(
          (s) => s.name == row.status,
          orElse: () => AssignmentStatus.pending,
        ),
        scheduledAt: row.downloadedAt,
        averageConsumption: 0.0,
      ));
    }
    return list;
  }

  /// يضمن وجود بيانات بـ_all قبل أي عملية بحث (getById/lookupByMeterNumber/
  /// resolveQr): يقرأ من الكاش فقط إذا كانت _all فارغة (بداية تشغيل باردة
  /// بدون اتصال بعد)، ولا يمس _all إن كانت معبأة بالفعل من هذه الجلسة.
  Future<void> _ensureLoaded() async {
    if (_all.isNotEmpty) return;
    final cached = await loadFromCache();
    if (cached.isNotEmpty) {
      _all = cached;
      _notifyListeners();
    }
  }

  List<ReadingAssignment> _applyFilters(
    List<ReadingAssignment> source, {
    String? query,
    AssignmentStatus? filter,
  }) {
    var result = source;
    if (filter != null) {
      result = result.where((a) => a.status == filter).toList();
    }
    if (query != null && query.trim().isNotEmpty) {
      final q = query.trim().toLowerCase();
      result = result
          .where((a) =>
              a.customer.name.toLowerCase().contains(q) ||
              a.customer.customerNumber.toLowerCase().contains(q) ||
              a.customer.accountNumber.toLowerCase().contains(q) ||
              a.meter.meterNumber.toLowerCase().contains(q) ||
              (a.meter.serialNumber?.toLowerCase().contains(q) ?? false))
          .toList();
    }
    return result;
  }

  @override
  Stream<List<ReadingAssignment>> watchAssignments(
      {String? query, AssignmentStatus? filter}) {
    return Stream<List<ReadingAssignment>>.multi((controller) {
      if (!_initialized) {
        _initialized = true;
        // يعرض الكاش المحلي فوراً (إن وُجد) قبل انتظار الشبكة، ثم يبدأ
        // المزامنة الحية فور اكتمال قراءة الكاش — offline-first حقيقي.
        unawaited(_ensureLoaded().whenComplete(() {
          unawaited(_fetchData());
        }));
      }
      try {
        controller.add(_applyFilters(List.unmodifiable(_all),
            query: query, filter: filter));
      } catch (e, st) {
        controller.addError(e, st);
      }
      final sub = _changeHub.stream.listen(
        (list) {
          try {
            controller.add(_applyFilters(list, query: query, filter: filter));
          } catch (e, st) {
            controller.addError(e, st);
          }
        },
        onError: controller.addError,
        onDone: controller.close,
      );
      controller.onCancel = sub.cancel;
    });
  }

  @override
  Future<ReadingAssignmentSyncResult> syncOpenPeriodAssignments() {
    _initialized = true;
    return _fetchData();
  }

  @override
  Future<ReadingAssignment?> getById(String id) async {
    await _ensureLoaded();
    try {
      return _all.firstWhere((a) => a.id == id);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber) async {
    await _ensureLoaded();
    try {
      return _all.firstWhere((a) => a.meter.meterNumber == meterNumber);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<ReadingAssignment?> resolveQr(String payload) async {
    await _ensureLoaded();
    try {
      final candidates = _payloadCandidates(payload);
      return _all.firstWhere(
        (a) => _assignmentIdentifiers(a).any(candidates.contains),
      );
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> markStatus(String assignmentId, AssignmentStatus status) async {
    final idx = _all.indexWhere((a) => a.id == assignmentId);
    if (idx == -1) return;
    final a = _all[idx];
    final updated = List<ReadingAssignment>.from(_all);
    updated[idx] = ReadingAssignment(
      id: a.id,
      meter: a.meter,
      customer: a.customer,
      periodId: a.periodId,
      status: status,
      scheduledAt: a.scheduledAt,
      averageConsumption: a.averageConsumption,
    );
    _all = List.unmodifiable(updated);
    _notifyListeners();
  }

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
