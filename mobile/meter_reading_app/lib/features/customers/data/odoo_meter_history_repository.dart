import 'package:drift/drift.dart' as drift;

import '../../../core/database/app_database.dart';
import '../../../core/network/odoo_api_client.dart';
import '../domain/entities.dart';

/// Synchronizes one meter's verified reading history without touching offline
/// reading drafts or the active-period assignment cache.
class OdooMeterHistoryRepository {
  final OdooApiClient _client;
  final AppDatabase _db;

  OdooMeterHistoryRepository(this._client, this._db);

  Stream<List<MeterReadingHistoryItem>> watchHistory(int meterRemoteId) {
    final query = _db.select(_db.meterReadingHistories)
      ..where((row) => row.meterRemoteId.equals(meterRemoteId))
      ..orderBy([
        (row) => drift.OrderingTerm.desc(row.readingDate),
        (row) => drift.OrderingTerm.desc(row.entryKey),
      ]);
    return query.watch().map(
          (rows) => rows
              .map(
                (row) => MeterReadingHistoryItem(
                  entryKey: row.entryKey,
                  meterRemoteId: row.meterRemoteId,
                  readingValue: row.readingValue,
                  readingDate: row.readingDate,
                  source: row.source,
                ),
              )
              .toList(growable: false),
        );
  }

  /// Refreshes only when the reader opens this meter online.  A failed request
  /// leaves the existing offline cache untouched.
  Future<void> syncMeterHistory({
    required int meterRemoteId,
    required String meterNumber,
  }) async {
    final response = await _client.postJson(
      '/api/v1/utility/reading/meter/lookup',
      {'meter_id': meterRemoteId, 'meter_number': meterNumber},
    );
    final rawHistory = response['reading_history'];
    if (rawHistory is! List) return;

    final history = <MeterReadingHistoryItem>[];
    for (final rawItem in rawHistory) {
      if (rawItem is! Map) continue;
      final item = Map<String, dynamic>.from(rawItem);
      final key = item['key']?.toString().trim();
      final value = (item['reading_value'] as num?)?.toDouble();
      final date = DateTime.tryParse(item['reading_date']?.toString() ?? '');
      if (key == null || key.isEmpty || value == null || date == null) continue;
      history.add(MeterReadingHistoryItem(
        entryKey: key,
        meterRemoteId: meterRemoteId,
        readingValue: value,
        readingDate: date,
        source: item['source']?.toString() ?? 'reading',
      ));
    }

    // A successful response is authoritative for this bounded history.  Do
    // not clear the old cache before a valid response has been parsed.
    await _db.transaction(() async {
      await (_db.delete(_db.meterReadingHistories)
            ..where((row) => row.meterRemoteId.equals(meterRemoteId)))
          .go();
      final syncedAt = DateTime.now();
      for (final item in history) {
        await _db.into(_db.meterReadingHistories).insertOnConflictUpdate(
              MeterReadingHistoriesCompanion(
                entryKey: drift.Value(item.entryKey),
                meterRemoteId: drift.Value(item.meterRemoteId),
                readingValue: drift.Value(item.readingValue),
                readingDate: drift.Value(item.readingDate),
                source: drift.Value(item.source),
                syncedAt: drift.Value(syncedAt),
              ),
            );
      }
    });
  }
}
