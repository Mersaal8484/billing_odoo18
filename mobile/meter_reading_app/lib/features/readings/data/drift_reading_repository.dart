import 'dart:async';

import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../../../core/database/app_database.dart';
import '../domain/reading.dart';

class DriftReadingRepository implements ReadingRepository {
  final AppDatabase _db;
  static const _uuid = Uuid();

  DriftReadingRepository(this._db);

  @override
  Stream<List<MeterReading>> watchReadingsForPeriod(int periodId) {
    final query = _db.select(_db.readings)
      ..orderBy([(t) => drift.OrderingTerm.desc(t.readingDate)]);
    return query.watch().map((rows) => rows.map(_toModel).toList());
  }

  @override
  Future<MeterReading> saveDraft(MeterReading reading) async {
    final now = DateTime.now();
    final id = reading.id.isEmpty ? _uuid.v4() : reading.id;
    await _db.into(_db.readings).insertOnConflictUpdate(
          ReadingsCompanion(
            id: drift.Value(id),
            remoteId: drift.Value(reading.remoteId),
            meterRemoteId: drift.Value(reading.meterRemoteId),
            readingValue: drift.Value(reading.readingValue),
            readingDate: drift.Value(reading.readingDate),
            capturedPeriodId: drift.Value(reading.capturedPeriodId),
            readingCategory: drift.Value(reading.category.name),
            isEstimated: drift.Value(reading.isEstimated),
            remarks: drift.Value(reading.remarks),
            imageLocalPath: drift.Value(reading.imageLocalPath),
            syncStatus: const drift.Value('draft'),
            syncAttempts: const drift.Value(0),
            createdAt: drift.Value(now),
            updatedAt: drift.Value(now),
          ),
        );
    return reading.copyWith(syncStatus: ReadingSyncStatus.draft);
  }

  @override
  Future<void> enqueueForSync(String readingId) =>
      _setStatus(readingId, 'pending');

  @override
  Future<void> retry(String readingId) =>
      _setStatus(readingId, 'pending', clearError: true);

  Future<List<MeterReading>> getByStatus(String status) async {
    final rows = await (_db.select(_db.readings)
          ..where((t) => t.syncStatus.equals(status))
          ..orderBy([(t) => drift.OrderingTerm.asc(t.createdAt)]))
        .get();
    return rows.map(_toModel).toList();
  }

  Future<void> updateSyncStatus(String readingId, ReadingSyncStatus status,
      {String? error}) async {
    await (_db.update(_db.readings)..where((t) => t.id.equals(readingId)))
        .write(ReadingsCompanion(
      syncStatus: drift.Value(_statusToString(status)),
      lastError: drift.Value(error),
      updatedAt: drift.Value(DateTime.now()),
    ));
  }

  Future<void> saveImagePath(String readingId, {required String localPath}) async {
    await (_db.update(_db.readings)..where((t) => t.id.equals(readingId)))
        .write(ReadingsCompanion(
      imageLocalPath: drift.Value(localPath),
      updatedAt: drift.Value(DateTime.now()),
    ));
  }

  Future<void> _setStatus(String readingId, String status,
      {bool clearError = false}) async {
    await (_db.update(_db.readings)..where((t) => t.id.equals(readingId)))
        .write(ReadingsCompanion(
      syncStatus: drift.Value(status),
      lastError: clearError
          ? const drift.Value(null)
          : const drift.Value.absent(),
      updatedAt: drift.Value(DateTime.now()),
    ));
  }

  MeterReading _toModel(Reading row) => MeterReading(
        id: row.id,
        remoteId: row.remoteId,
        meterRemoteId: row.meterRemoteId,
        readingValue: row.readingValue,
        readingDate: row.readingDate,
        capturedPeriodId: row.capturedPeriodId,
        category: ReadingCategory.values.firstWhere(
          (c) => c.name == row.readingCategory,
          orElse: () => ReadingCategory.customer,
        ),
        isEstimated: row.isEstimated,
        remarks: row.remarks,
        imageLocalPath: row.imageLocalPath,
        syncStatus: _statusFromString(row.syncStatus),
        lastError: row.lastError,
      );

  static ReadingSyncStatus _statusFromString(String s) => switch (s) {
        'pending' => ReadingSyncStatus.pendingDataSync,
        'uploading' => ReadingSyncStatus.pendingDataSync,
        'dataSynced' => ReadingSyncStatus.dataSynced,
        'pendingImageSync' => ReadingSyncStatus.pendingImageSync,
        'synced' => ReadingSyncStatus.synced,
        'error' => ReadingSyncStatus.error,
        _ => ReadingSyncStatus.draft,
      };

  static String _statusToString(ReadingSyncStatus s) => switch (s) {
        ReadingSyncStatus.draft => 'draft',
        ReadingSyncStatus.pendingDataSync => 'pending',
        ReadingSyncStatus.dataSynced => 'dataSynced',
        ReadingSyncStatus.pendingImageSync => 'pendingImageSync',
        ReadingSyncStatus.synced => 'synced',
        ReadingSyncStatus.error => 'error',
      };
}
