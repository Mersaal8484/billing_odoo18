import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'app_database.g.dart';

/// Mirrors utility.customer (utility_core). Local cache, refreshed on
/// assignment sync. `remoteId` is the authoritative Odoo record id.
class Customers extends Table {
  IntColumn get remoteId => integer()();
  TextColumn get accountNumber => text()();
  TextColumn get name => text()();
  TextColumn get address => text().nullable()();
  IntColumn get routeId => integer().nullable()();
  DateTimeColumn get lastReadingDate => dateTime().nullable()();
  RealColumn get lastReadingValue => real().nullable()();
  DateTimeColumn get lastSyncedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {remoteId};
}

/// Mirrors utility.meter (utility_core).
class Meters extends Table {
  IntColumn get remoteId => integer()();
  TextColumn get meterNumber => text()();
  TextColumn get serialNumber => text().nullable()();
  IntColumn get customerRemoteId =>
      integer().references(Customers, #remoteId)();
  TextColumn get meterType => text().nullable()();
  TextColumn get paymentType => text()(); // postpaid | prepaid | manual
  TextColumn get communicationType => text().nullable()();
  IntColumn get routeId => integer().nullable()();
  BoolColumn get isCouplingMeter =>
      boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {remoteId};
}

/// A reader's assignment for the active billing period — the working set
/// downloaded before going offline into the field. Mirrors what
/// utility.route + date.range imply for "who reads what, this period".
class Assignments extends Table {
  TextColumn get id => text()(); // uuid, local
  IntColumn get meterRemoteId => integer().references(Meters, #remoteId)();
  IntColumn get periodId => integer()(); // date.range id
  TextColumn get status =>
      text().withDefault(const Constant('pending'))(); // pending|read|skipped
  DateTimeColumn get downloadedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Local billing periods cache, mirrors date.range (type_id.billing_period=true).
class Periods extends Table {
  IntColumn get id => integer()();
  TextColumn get name => text()();
  DateTimeColumn get dateStart => dateTime().nullable()();
  DateTimeColumn get dateEnd => dateTime().nullable()();
  BoolColumn get isCurrent => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

/// Local draft/synced meter readings. This is the primary working record —
/// created offline, then synced via Pipeline A. Field set mirrors
/// utility.reading's STATE_EDITABLE contract on the ERP side so that
/// nothing captured here becomes unwritable once uploaded.
class Readings extends Table {
  TextColumn get id => text()(); // uuid, local primary key
  IntColumn get remoteId =>
      integer().nullable()(); // set once ERP creates utility.reading
  IntColumn get meterRemoteId => integer().references(Meters, #remoteId)();
  RealColumn get readingValue => real()();
  DateTimeColumn get readingDate => dateTime()();
  /// بصمة الفترة (date.range id) المفتوحة وقت التقاط القراءة ميدانياً —
  /// يمنع SyncEngine من إلصاق قراءة قديمة غير مُزامَنة بفترة جديدة مختلفة
  /// عند الرفع. nullable لتوافق الصفوف القديمة قبل هذا العمود (migration v3).
  IntColumn get capturedPeriodId => integer().nullable()();
  TextColumn get readingCategory =>
      text().withDefault(const Constant('customer'))();
  BoolColumn get isEstimated => boolean().withDefault(const Constant(false))();
  TextColumn get remarks => text().nullable()();
  TextColumn get imageLocalPath =>
      text().nullable()(); // processed JPEG, local disk
  TextColumn get imageSecondaryLocalPath => text().nullable()();
  IntColumn get imageAttachmentRemoteId =>
      integer().nullable()(); // ir.attachment id once uploaded
  TextColumn get syncStatus => text().withDefault(const Constant('draft'))();
  // draft -> pending_sync -> synced -> error
  IntColumn get syncAttempts => integer().withDefault(const Constant(0))();
  TextColumn get syncBatchId => text().nullable().references(SyncBatches, #id)();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Unified ZIP-based sync batches tracking.
class SyncBatches extends Table {
  TextColumn get id => text()(); // batch_uuid
  TextColumn get status => text().withDefault(const Constant('pending'))();
  // pending | uploading | success | failed
  TextColumn get archivePath => text().nullable()();
  IntColumn get readingCount => integer()();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get lastAttemptAt => dateTime().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(tables: [
  Customers,
  Meters,
  Assignments,
  Periods,
  Readings,
  SyncBatches,
])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (Migrator m) async {
        await m.createAll();
      },
      onUpgrade: (Migrator m, int from, int to) async {
        if (from < 2) {
          await customStatement('DROP TABLE IF EXISTS sync_queue_items');
          await customStatement('DROP TABLE IF EXISTS image_upload_queue_items');
          await m.addColumn(readings, readings.syncAttempts);
          await m.addColumn(readings, readings.syncBatchId);
          await m.createTable(syncBatches);
        }
        if (from < 3) {
          await m.addColumn(readings, readings.capturedPeriodId);
        }
      },
    );
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'meter_reading.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}
