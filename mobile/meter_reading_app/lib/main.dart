import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:workmanager/workmanager.dart';

import 'app/app.dart';
import 'app/providers.dart';
import 'core/database/app_database.dart';
import 'core/network/auth_service.dart';
import 'core/network/odoo_api_client.dart';
import 'core/network/reading_api_service.dart';
import 'core/sync/sync_engine.dart';
import 'core/sync/sync_settings_service.dart';
import 'features/readings/data/drift_reading_repository.dart';

// ──────────────────────────────────────────────────────────────────────────────
// ⚙️  اضبط هذا العنوان حسب بيئتك:
//   • محاكي Android ←  'http://10.0.2.2:8069'
//   • جهاز حقيقي على نفس الشبكة ← 'http://192.168.1.XX:8069'
//   • سيرفر إنتاج ← 'https://erp.example.com'
// ──────────────────────────────────────────────────────────────────────────────
const _kOdooBaseUrl = 'http://37.60.243.200:8069';

// ملاحظة: اسم قاعدة البيانات (kOdooDb) انتقل إلى core/config/app_config.dart
// حتى يستورده LoginScreen من نفس المصدر بدل كتابته يدوياً كنص منفصل.

// ──────────────────────────────────────────────────────────────────────────────
// Background sync dispatcher — يعمل في isolate منفصل عند إطلاق WorkManager
// ──────────────────────────────────────────────────────────────────────────────
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    if (task == 'sync_batch_task') {
      // في الـ background isolate نُنشئ كل شيء محلياً
      // (لا يوجد ProviderScope هنا)
      final db = AppDatabase();
      final apiClient = await OdooApiClient.create(
        defaultBaseUrl: _kOdooBaseUrl,
      );
      final repo = DriftReadingRepository(db);
      final readingApi = ReadingApiService(apiClient);
      final engine = SyncEngine(
        repo,
        db,
        SyncSettingsService(),
        readingApi,
      );
      try {
        await engine.syncNow();
      } finally {
        engine.dispose();
        await db.close();
      }
    }
    return true;
  });
}

// ──────────────────────────────────────────────────────────────────────────────
// main
// ──────────────────────────────────────────────────────────────────────────────
void main() {
  // نلتقط أي استثناء غير متوقّع (حتى لو صار قبل runApp) ونطبعه كاملاً في
  // الـ console بدل ما يختفي بصمت ("keeps stopping" بدون أي تفاصيل).
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // اطبع أي خطأ داخل شجرة الـ widgets بالتفصيل أيضاً (بدل الشاشة الحمراء
    // فقط في debug، وبدل الاختفاء الصامت في release).
    FlutterError.onError = (FlutterErrorDetails details) {
      FlutterError.dumpErrorToConsole(details);
    };

    // 1️⃣ بناء HTTP client (يحمّل cookie jar المحفوظ من آخر جلسة)
    final apiClient = await OdooApiClient.create(
      defaultBaseUrl: _kOdooBaseUrl,
    );

    // 2️⃣ فتح قاعدة البيانات المحلية
    final db = AppDatabase();

    // 3️⃣ التحقق من وجود session cookie صالح → نتخطى شاشة Login إذا كان موجوداً
    final authService = AuthService(apiClient);
    final isLoggedIn = await authService.restoreSession();

    // 4️⃣ تسجيل WorkManager للمزامنة الدورية في الخلفية.
    // مُحاط بـ try/catch عمداً: فشل تسجيل المزامنة الخلفية (مثلاً بسبب توافق
    // بلجن معيّن مع إصدار Android/الجهاز) لا يجب أن يمنع التطبيق من الإقلاع
    // إطلاقاً — أسوأ حالة نخسرها هي المزامنة التلقائية بالخلفية فقط، والمستخدم
    // ما زال يقدر يزامن يدوياً من داخل التطبيق.
    try {
      await Workmanager().initialize(callbackDispatcher);
      await Workmanager().registerPeriodicTask(
        'sync-task-id',
        'sync_batch_task',
        frequency: const Duration(minutes: 15),
        existingWorkPolicy:
            ExistingPeriodicWorkPolicy.keep, // لا تُعيد التسجيل إذا كانت موجودة
        constraints: Constraints(networkType: NetworkType.connected),
      );
    } catch (e, st) {
      // اطبع الخطأ بوضوح بدل تجاهله بصمت — يساعدنا نعرف فوراً لو هذا هو
      // سبب أي كراش مستقبلي عند الإقلاع.
      debugPrint('⚠️ WorkManager init failed (background sync disabled): $e');
      debugPrint(st.toString());
    }

    runApp(
      ProviderScope(
        overrides: [
          // ✅ تمرير OdooApiClient الحقيقي بدلاً من UnimplementedError
          odooApiClientProvider.overrideWithValue(apiClient),

          // ✅ نفس instance قاعدة البيانات في كل التطبيق
          databaseProvider.overrideWithValue(db),

          // ✅ حالة تسجيل الدخول من الـ cookie الحقيقي
          authStateProvider.overrideWith((ref) => isLoggedIn),

          // ✅ تمرير AuthService بعد استعادة بيانات الجلسة
          authServiceProvider.overrideWithValue(authService),

          // ✅ تمرير بيانات المستخدم (الاسم والأدوار) المُستعادة من التخزين المحلي
          // بدونها يبقى currentUserProvider فارغاً وتختفي بطاقات الكاشف/المتحصل/المشرف
          currentUserProvider.overrideWith((ref) => authService.currentUser),
        ],
        child: const MeterReadingApp(),
      ),
    );
  }, (error, stackTrace) {
    // أي استثناء غير ملتقط في أي مكان بعد هذي النقطة يُطبع كاملاً هنا
    // بدل ما يسبب "keeps stopping" صامت بدون أي أثر.
    debugPrint('🔴 UNCAUGHT ERROR: $error');
    debugPrint(stackTrace.toString());
  });
}
