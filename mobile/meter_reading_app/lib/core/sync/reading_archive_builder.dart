import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';

import '../../features/readings/domain/reading.dart';

/// Limits returned by ERP bootstrap. The server remains authoritative; no
/// image count or archive size is fixed in the mobile application.
class SyncBatchPolicy {
  final int maxImagesPerArchive;
  final int maxArchiveBytes;
  final int maxImageBytes;

  const SyncBatchPolicy({
    required this.maxImagesPerArchive,
    required this.maxArchiveBytes,
    required this.maxImageBytes,
  })  : assert(maxImagesPerArchive > 0),
        assert(maxArchiveBytes > 0),
        assert(maxImageBytes > 0);

  factory SyncBatchPolicy.fromBootstrap(Map<String, dynamic> settings) {
    int positiveInt(dynamic value, int fallback) {
      final parsed = value is int ? value : int.tryParse('$value');
      return parsed != null && parsed > 0 ? parsed : fallback;
    }

    final imageLimitKb = positiveInt(settings['max_image_size_kb'], 80);
    if (imageLimitKb != 60 && imageLimitKb != 80) {
      throw ArgumentError.value(
        imageLimitKb,
        'max_image_size_kb',
        'Only 60 KB or 80 KB is supported by the field application.',
      );
    }

    return SyncBatchPolicy(
      maxImagesPerArchive: positiveInt(settings['max_images_per_archive'], 50),
      maxArchiveBytes:
          positiveInt(settings['max_archive_size_mb'], 5) * 1024 * 1024,
      maxImageBytes: imageLimitKb * 1024,
    );
  }
}

/// Metadata needed to connect an archived image to its field reading.
/// Location data is intentionally absent.
class ArchiveReadingItem {
  final MeterReading reading;
  final int cycleId;
  final int customerId;
  final String? meterNumber;

  const ArchiveReadingItem({
    required this.reading,
    required this.cycleId,
    required this.customerId,
    this.meterNumber,
  });
}

class ReadingUploadArchive {
  final String batchUuid;
  final File archiveFile;
  final List<String> readingIds;
  final String sha256;

  const ReadingUploadArchive({
    required this.batchUuid,
    required this.archiveFile,
    required this.readingIds,
    required this.sha256,
  });
}

/// Builds a transport-neutral ZIP for the archive upload endpoint. JPEG files
/// are already compressed, so this primarily reduces request overhead and
/// carries reliable mapping metadata rather than materially shrinking bytes.
class ReadingArchiveBuilder {
  final Uuid _uuid;

  ReadingArchiveBuilder({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  Future<List<ReadingUploadArchive>> build({
    required List<ArchiveReadingItem> items,
    required SyncBatchPolicy policy,
    required Directory destination,
  }) async {
    await destination.create(recursive: true);
    final archives = <ReadingUploadArchive>[];
    final pending = <_PreparedImage>[];
    var pendingBytes = 0;

    for (final item in items) {
      final prepared = await _prepare(item, policy);
      if (prepared == null) {
        continue;
      }

      final exceedsCount = pending.length >= policy.maxImagesPerArchive;
      final exceedsSize = pending.isNotEmpty &&
          pendingBytes + prepared.bytes.length > policy.maxArchiveBytes;
      if (exceedsCount || exceedsSize) {
        archives.add(await _writeArchive(pending, destination));
        pending.clear();
        pendingBytes = 0;
      }

      pending.add(prepared);
      pendingBytes += prepared.bytes.length;
    }

    if (pending.isNotEmpty) {
      archives.add(await _writeArchive(pending, destination));
    }
    return archives;
  }

  Future<_PreparedImage?> _prepare(
    ArchiveReadingItem item,
    SyncBatchPolicy policy,
  ) async {
    final path = item.reading.imageLocalPath;
    if (path == null) {
      return null;
    }

    final image = File(path);
    if (!await image.exists()) {
      return null;
    }

    final bytes = await image.readAsBytes();
    if (bytes.length > policy.maxImageBytes) {
      throw ReadingArchiveException(
        readingId: item.reading.id,
        message: 'Image exceeds the configured per-image limit.',
      );
    }
    if (bytes.length > policy.maxArchiveBytes) {
      throw ReadingArchiveException(
        readingId: item.reading.id,
        message: 'Image exceeds the configured archive size limit.',
      );
    }

    final photoUuid = item.reading.photoUuid;
    if (photoUuid == null || photoUuid.isEmpty) {
      throw ReadingArchiveException(
        readingId: item.reading.id,
        message: 'A stable photo UUID is required before batching.',
      );
    }

    return _PreparedImage(item: item, bytes: bytes, photoUuid: photoUuid);
  }

  Future<ReadingUploadArchive> _writeArchive(
    List<_PreparedImage> images,
    Directory destination,
  ) async {
    final batchUuid = _uuid.v4();
    final archive = Archive();
    final readings = <Map<String, dynamic>>[];

    for (final image in images) {
      final filename = '${image.photoUuid}.jpg';
      final checksum = sha256.convert(image.bytes).toString();
      archive.addFile(
        ArchiveFile('images/$filename', image.bytes.length, image.bytes),
      );
      readings.add({
        'client_uuid': image.item.reading.id,
        'photo_uuid': image.photoUuid,
        'meter_id': image.item.reading.meterRemoteId,
        'meter_number': image.item.meterNumber,
        'customer_id': image.item.customerId,
        'cycle_id': image.item.cycleId,
        'reading_value': image.item.reading.readingValue,
        'reading_date':
            image.item.reading.readingDate.toUtc().toIso8601String(),
        'reading_category': image.item.reading.category.name,
        'is_estimated': image.item.reading.isEstimated,
        'remarks': image.item.reading.remarks,
        'image_filename': 'images/$filename',
        'size_bytes': image.bytes.length,
        'sha256': checksum,
      });
    }

    final manifest = <String, dynamic>{
      'schema_version': 1,
      'batch_uuid': batchUuid,
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'reading_count': readings.length,
      'readings': readings,
    };
    final manifestBytes = Uint8List.fromList(utf8.encode(jsonEncode(manifest)));
    archive.addFile(
      ArchiveFile('manifest.json', manifestBytes.length, manifestBytes),
    );

    final encoded = ZipEncoder().encode(archive);
    if (encoded == null) {
      throw StateError('Unable to encode the reading archive.');
    }
    final output = File(
      '${destination.path}${Platform.pathSeparator}$batchUuid.zip',
    );
    await output.writeAsBytes(encoded, flush: true);
    final archiveBytes = await output.readAsBytes();
    return ReadingUploadArchive(
      batchUuid: batchUuid,
      archiveFile: output,
      readingIds: images.map((image) => image.item.reading.id).toList(),
      sha256: sha256.convert(archiveBytes).toString(),
    );
  }
}

class ReadingArchiveException implements Exception {
  final String readingId;
  final String message;

  const ReadingArchiveException({
    required this.readingId,
    required this.message,
  });

  @override
  String toString() => 'ReadingArchiveException($readingId): $message';
}

class _PreparedImage {
  final ArchiveReadingItem item;
  final Uint8List bytes;
  final String photoUuid;

  const _PreparedImage({
    required this.item,
    required this.bytes,
    required this.photoUuid,
  });
}
