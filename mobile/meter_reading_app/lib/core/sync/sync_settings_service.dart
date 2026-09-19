import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum SyncMode {
  immediate,
  batch,
}

class SyncSettingsService {
  static const _modeKey = 'sync_mode';
  static const _batchSizeKey = 'sync_batch_size';

  final FlutterSecureStorage _storage;

  SyncSettingsService({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  Future<SyncMode> getSyncMode() async {
    final modeStr = await _storage.read(key: _modeKey);
    if (modeStr == SyncMode.batch.name) {
      return SyncMode.batch;
    }
    return SyncMode.immediate; // Default: do not leave field readings waiting.
  }

  Future<void> setSyncMode(SyncMode mode) async {
    await _storage.write(key: _modeKey, value: mode.name);
  }

  Future<int> getBatchSize() async {
    final sizeStr = await _storage.read(key: _batchSizeKey);
    if (sizeStr != null) {
      final size = int.tryParse(sizeStr);
      if (size != null && (size == 30 || size == 50 || size == 100)) {
        return size;
      }
    }
    return 50; // Default
  }

  Future<void> setBatchSize(int size) async {
    await _storage.write(key: _batchSizeKey, value: size.toString());
  }
}
