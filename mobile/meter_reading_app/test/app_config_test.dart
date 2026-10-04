import 'package:flutter_test/flutter_test.dart';
import 'package:meter_reading_app/core/config/app_config.dart';

void main() {
  test('uses the local Odoo 18 environment by default', () {
    expect(AppConfig.odooBaseUrl, 'http://192.168.8.134:9001');
    expect(AppConfig.odooDatabase, 'invoice_odoo18_db');
  });
}
