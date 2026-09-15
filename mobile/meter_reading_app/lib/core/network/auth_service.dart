import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'odoo_api_client.dart';

class OdooUserInfo {
  final int uid;
  final String name;
  final String login;
  final String db;
  final Map<String, bool>? roles;
  
  const OdooUserInfo({
    required this.uid,
    required this.name,
    required this.login,
    required this.db,
    this.roles,
  });
}

/// True when the error text looks like a raw low-level DB/connection
/// failure (e.g. "FATAL: database ... does not exist") rather than a
/// normal validation/auth error, so we can show the user something
/// readable instead of a raw Postgres message.
bool _looksLikeRawDbError(String text) {
  final lower = text.toLowerCase();
  return lower.contains('does not exist') ||
      lower.contains('fatal') ||
      lower.contains('connection to server');
}

/// Handles login/logout against Odoo's built-in session controller.
/// This is separate from the custom `/api/v1/utility/*` routes: Odoo's
/// session cookie, once set here, is what makes `auth='user'` routes work.
class AuthService {
  static const _dbKey = 'odoo_db';
  static const _loginKey = 'odoo_login';

  final OdooApiClient _client;
  final FlutterSecureStorage _storage;
  
  OdooUserInfo? _currentUser;
  OdooUserInfo? get currentUser => _currentUser;

  AuthService(this._client, {FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  /// Logs in against `/web/session/authenticate` (standard Odoo endpoint,
  /// present in every Odoo instance, no custom code needed).
  Future<OdooUserInfo> login({
    required String db,
    required String login,
    required String password,
  }) async {
    Map<String, dynamic> result;
    try {
      result = await _client.postJson('/web/session/authenticate', {
        'db': db,
        'login': login,
        'password': password,
      });
    } on OdooApiException catch (e) {
      // Odoo wraps server-side exceptions (like a Postgres connection
      // failure for a missing db) into OdooApiException.message. Translate
      // that raw text into something a normal user can act on.
      if (_looksLikeRawDbError(e.message)) {
        throw OdooApiException(
          'تعذر الاتصال بقاعدة البيانات على السيرفر. جرّب مسح بيانات '
          'الجلسة المحلية من هذه الشاشة، أو تواصل مع الدعم الفني.',
          code: e.code,
        );
      }
      rethrow;
    }

    final uid = result['uid'];
    if (uid == null || uid == false) {
      throw OdooApiException('Invalid credentials or database name');
    }

    await _storage.write(key: _dbKey, value: db);
    await _storage.write(key: _loginKey, value: login);

    Map<String, bool>? userRoles;
    try {
      final roleResult = await _client.postJson('/api/v1/utility/auth/roles', {});
      if (roleResult['success'] == true) {
        final r = roleResult['roles'] as Map<String, dynamic>?;
        if (r != null) {
          userRoles = r.map((k, v) => MapEntry(k, v == true));
        }
      }
    } catch (_) {
      // Ignore if roles API fails, user will have basic access
    }

    _currentUser = OdooUserInfo(
      uid: uid as int,
      name: (result['name'] as String?) ?? login,
      login: login,
      db: db,
      roles: userRoles,
    );
    return _currentUser!;
  }

  Future<void> logout() async {
    try {
      await _client.postJson('/web/session/destroy', {});
    } catch (_) {
      // Ignore network errors on logout; clear locally regardless.
    }
    await _client.clearSession();
    await _storage.delete(key: _dbKey);
    await _storage.delete(key: _loginKey);
  }

  /// Clears all locally stored session data (cookie + saved db/login)
  /// without hitting the server. Wired to a "Clear local session data"
  /// button on the login screen, so users don't need manual Android
  /// settings steps when something is stuck locally.
  Future<void> clearLocalSession() async {
    try {
      await _client.clearSession();
    } catch (_) {
      // Ignore; we still want to clear local storage below.
    }
    await _storage.delete(key: _dbKey);
    await _storage.delete(key: _loginKey);
    _currentUser = null;
  }

  /// Quick check used at app startup to decide Login vs Home screen.
  Future<bool> isLoggedIn() => _client.hasSessionCookie();

  /// Restores session user info and roles if cookie is still valid
  Future<bool> restoreSession() async {
    final hasCookie = await isLoggedIn();
    if (!hasCookie) return false;

    final db = await _storage.read(key: _dbKey);
    final login = await _storage.read(key: _loginKey);
    if (db == null || login == null) return false;

    Map<String, bool>? userRoles;
    try {
      final roleResult = await _client.postJson('/api/v1/utility/auth/roles', {});
      if (roleResult['success'] == true) {
        final r = roleResult['roles'] as Map<String, dynamic>?;
        if (r != null) {
          userRoles = r.map((k, v) => MapEntry(k, v == true));
        }
      }
    } on OdooApiException catch (e) {
      if (_looksLikeRawDbError(e.message)) {
        // القاعدة المحفوظة محلياً لم تعد صالحة على السيرفر — امسح الجلسة
        // تلقائياً بدل ما يعلق المستخدم على نفس الخطأ في كل تشغيل.
        await clearLocalSession();
        return false;
      }
      // أي خطأ آخر (شبكة، صلاحيات...) — تجاهله وكمل بدون roles كالسابق.
    } catch (_) {}

    _currentUser = OdooUserInfo(
      uid: 0,
      name: login,
      login: login,
      db: db,
      roles: userRoles,
    );
    return true;
  }

  Future<String?> get savedDb => _storage.read(key: _dbKey);
  Future<String?> get savedLogin => _storage.read(key: _loginKey);
}
