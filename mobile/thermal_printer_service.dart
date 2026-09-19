import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:print_bluetooth_thermal/print_bluetooth_thermal.dart';

import '../../features/collections/domain/collection_models.dart';
import 'collection_receipt_builder.dart';

class ThermalPrinterDevice {
  final String name;
  final String mac;

  const ThermalPrinterDevice({required this.name, required this.mac});

  @override
  bool operator ==(Object other) =>
      other is ThermalPrinterDevice && other.mac == mac;

  @override
  int get hashCode => mac.hashCode;
}

class ThermalPrinterException implements Exception {
  final String message;

  const ThermalPrinterException(this.message);

  @override
  String toString() => message;
}

/// Bluetooth ESC/POS thermal printer bridge for field collection receipts.
class ThermalPrinterService {
  static const _macKey = 'thermal_printer_mac';
  static const _nameKey = 'thermal_printer_name';

  final FlutterSecureStorage _storage;

  ThermalPrinterService({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  Future<bool> isSupportedPlatform() async {
    if (kIsWeb) return false;
    return Platform.isAndroid || Platform.isIOS;
  }

  Future<void> ensureReady() async {
    if (!await isSupportedPlatform()) {
      throw const ThermalPrinterException(
          'الطباعة الحرارية متاحة على Android و iOS فقط');
    }

    if (!await _ensurePermissions()) {
      throw const ThermalPrinterException(
          'يلزم منح صلاحية Bluetooth للاتصال بالطابعة');
    }

    if (!await PrintBluetoothThermal.bluetoothEnabled) {
      throw const ThermalPrinterException('فعّل Bluetooth على الجهاز أولاً');
    }
  }

  Future<bool> _ensurePermissions() async {
    if (await PrintBluetoothThermal.isPermissionBluetoothGranted) {
      return true;
    }

    if (Platform.isAndroid) {
      final statuses = await [
        Permission.bluetoothConnect,
        Permission.bluetoothScan,
        Permission.location,
      ].request();
      if (statuses.values.any((status) => status.isPermanentlyDenied)) {
        return false;
      }
    }

    return PrintBluetoothThermal.isPermissionBluetoothGranted;
  }

  Future<List<ThermalPrinterDevice>> pairedDevices() async {
    await ensureReady();
    final devices = await PrintBluetoothThermal.pairedBluetooths;
    return devices
        .map(
          (device) => ThermalPrinterDevice(
            name: device.name.isEmpty ? device.macAdress : device.name,
            mac: device.macAdress,
          ),
        )
        .toList(growable: false);
  }

  Future<ThermalPrinterDevice?> savedDevice() async {
    final mac = await _storage.read(key: _macKey);
    if (mac == null || mac.isEmpty) return null;
    final name = await _storage.read(key: _nameKey);
    return ThermalPrinterDevice(name: name ?? mac, mac: mac);
  }

  Future<void> saveDevice(ThermalPrinterDevice device) async {
    await _storage.write(key: _macKey, value: device.mac);
    await _storage.write(key: _nameKey, value: device.name);
  }

  Future<bool> isConnected() => PrintBluetoothThermal.connectionStatus;

  Future<bool> connect(ThermalPrinterDevice device) async {
    await ensureReady();
    final connected = await PrintBluetoothThermal.connect(
      macPrinterAddress: device.mac,
    );
    if (connected) {
      await saveDevice(device);
    }
    return connected;
  }

  Future<void> disconnect() => PrintBluetoothThermal.disconnect;

  Future<bool> printBytes(List<int> bytes) async {
    if (!await PrintBluetoothThermal.connectionStatus) {
      throw const ThermalPrinterException('الطابعة غير متصلة');
    }
    final ok = await PrintBluetoothThermal.writeBytes(bytes);
    if (!ok) {
      throw const ThermalPrinterException('فشل إرسال البيانات إلى الطابعة');
    }
    return ok;
  }

  /// Prints a collection receipt on the selected or saved thermal printer.
  Future<void> printCollectionReceipt(
    CollectionReceipt receipt, {
    ThermalPrinterDevice? device,
  }) async {
    final connectedDevice = await ensureConnected(device: device);
    if (connectedDevice == null) {
      throw const ThermalPrinterException(
        'لم يتم اختيار طابعة حرارية. اختر طابعة من الإعدادات أولاً.',
      );
    }

    final bytes = await CollectionReceiptBuilder.build(receipt);
    await printBytes(bytes);
  }

  /// Connects to the saved printer when possible, otherwise returns null.
  Future<ThermalPrinterDevice?> ensureConnected(
      {ThermalPrinterDevice? device}) async {
    await ensureReady();

    final target = device ?? await savedDevice();
    if (target == null) return null;

    if (await isConnected()) {
      return target;
    }

    final connected = await connect(target);
    if (!connected) {
      throw ThermalPrinterException('تعذر الاتصال بالطابعة ${target.name}');
    }
    return target;
  }
}
