import 'dart:async';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

/// Thrown when a request needs an authenticated session but none exists,
/// or the server rejected the session (expired / logged out elsewhere).
class OdooSessionExpiredException implements Exception {
  final String message;
  OdooSessionExpiredException([this.message = 'Session expired']);
  @override
  String toString() => message;
}

/// Thrown for any other Odoo JSON-RPC error (validation, access rights, etc).
class OdooApiException implements Exception {
  final String message;

  /// JSON-RPC uses a numeric code, while the business API returns stable
  /// string codes such as `READER_SCOPE_NOT_ASSIGNED`.
  final Object? code;
  OdooApiException(this.message, {this.code});
  @override
  String toString() => 'OdooApiException($code): $message';
}

/// Central HTTP client for all Odoo API calls.
///
/// - Persists the session cookie across app restarts (via cookie_jar on disk).
/// - Exposes [callKw]/[postJson] for JSON-RPC style endpoints (type='json').
/// - Exposes [dio] directly for multipart uploads (type='http').
/// - Base URL is configurable at runtime (local network IP can change).
class OdooApiClient {
  static const _baseUrlKey = 'odoo_base_url';

  final Dio dio;
  final FlutterSecureStorage _storage;
  PersistCookieJar? _cookieJar;
  String _baseUrl;

  OdooApiClient._(this.dio, this._storage, this._baseUrl);

  /// Call this once at app startup (e.g. in a provider) and await it
  /// before making any requests, so the cookie jar is ready.
  static Future<OdooApiClient> create({
    required String defaultBaseUrl,
    FlutterSecureStorage? storage,
  }) async {
    final secureStorage = storage ?? const FlutterSecureStorage();
    final savedUrl = await secureStorage.read(key: _baseUrlKey);
    final baseUrl = _normaliseBaseUrl(savedUrl ?? defaultBaseUrl);

    final dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
      // Odoo returns 200 even for JSON-RPC errors; we inspect the body.
      validateStatus: (status) => status != null && status < 500,
    ));

    final appDocDir = await getApplicationDocumentsDirectory();
    final cookieJar = PersistCookieJar(
      storage: FileStorage('${appDocDir.path}/.cookies/'),
    );
    dio.interceptors.add(CookieManager(cookieJar));

    final client = OdooApiClient._(dio, secureStorage, baseUrl);
    client._cookieJar = cookieJar;
    return client;
  }

  String get baseUrl => _baseUrl;

  static String _normaliseBaseUrl(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw ArgumentError.value(
        value,
        'baseUrl',
        'A complete server URL is required.',
      );
    }
    return value.trim().replaceFirst(RegExp(r'/+$'), '');
  }

  /// Update the server address at runtime (Settings screen) and persist it.
  Future<void> setBaseUrl(String newBaseUrl) async {
    final baseUrl = _normaliseBaseUrl(newBaseUrl);
    _baseUrl = baseUrl;
    dio.options.baseUrl = baseUrl;
    await _storage.write(key: _baseUrlKey, value: baseUrl);
  }

  /// Clears the session cookie (used on logout / session-expired).
  Future<void> clearSession() async {
    await _cookieJar?.deleteAll();
  }

  /// Whether we currently hold a session cookie for the active host.
  Future<bool> hasSessionCookie() async {
    if (_cookieJar == null) return false;
    final uri = Uri.parse(_baseUrl);
    final cookies = await _cookieJar!.loadForRequest(uri);
    return cookies.any((c) => c.name == 'session_id');
  }

  /// Standard Odoo JSON-RPC envelope for `type='json'` controller routes.
  ///
  /// [path] example: '/api/v1/utility/reading/batch/upload_data'
  /// [params] is whatever the controller's `**kwargs` / named args expect.
  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> params,
  ) async {
    final response = await dio.post(
      path,
      data: {
        'jsonrpc': '2.0',
        'method': 'call',
        'params': params,
      },
    );

    final body = response.data;
    if (body is! Map<String, dynamic>) {
      throw OdooApiException('Unexpected response shape from $path');
    }

    if (body.containsKey('error')) {
      final error = body['error'] as Map<String, dynamic>;
      final code = error['code'];
      final data = error['data'] as Map<String, dynamic>?;
      final message = (data?['message'] as String?) ??
          (error['message'] as String?) ??
          'Unknown Odoo error';

      // Odoo raises 100 (SessionExpiredException) when auth='user' and
      // there is no valid session.
      if (code == 100 ||
          message.toLowerCase().contains('session') &&
              message.toLowerCase().contains('expired')) {
        throw OdooSessionExpiredException(message);
      }
      throw OdooApiException(message, code: code);
    }

    final result = body['result'];
    if (result is Map<String, dynamic>) {
      if (result['success'] == false) {
        throw OdooApiException(
          (result['error'] as String?) ?? 'The server rejected the request',
          code: result['code'],
        );
      }
      return result;
    }
    // Some endpoints might return a list/primitive; wrap it.
    return {'result': result};
  }
}
