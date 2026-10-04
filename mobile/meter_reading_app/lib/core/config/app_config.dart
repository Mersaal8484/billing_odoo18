/// إعدادات مشتركة للتطبيق.
///
/// اسم قاعدة البيانات في odoo.conf — القيمة الوحيدة المعتمدة، يُستخدم من
/// main.dart و LoginScreen معاً. لا تكتب اسم القاعدة كنص حرفي في أي مكان
/// آخر بالكود؛ استورد `kOdooDb` من هنا دائماً.
///
/// (هذا الملف الجديد يحل المشكلة اللي كانت بالصورة: LoginScreen كان يرسل
/// db='invoice_utility_erp' مكتوبة يدوياً بدل الاعتماد على kOdooDb، فكان
/// يطلب قاعدة بيانات غير موجودة على السيرفر بغض النظر عن أي جلسة محفوظة.)
/// Central build-time configuration. Override these values with
/// `--dart-define` for non-local environments; do not duplicate them in UI
/// or networking code.
abstract final class AppConfig {
  static const odooBaseUrl = String.fromEnvironment(
    'ODOO_BASE_URL',
    defaultValue: 'http://192.168.8.134:9001',
  );

  static const odooDatabase = String.fromEnvironment(
    'ODOO_DATABASE',
    defaultValue: 'invoice_odoo18_db',
  );
}
