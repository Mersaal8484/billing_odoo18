// اختبارات كاش Drift المرتبط بالفترة داخل OdooAssignmentRepository.
//
// يستخدم NativeDatabase.memory() فلا يلمس القرص، ويتجاوز شبكة HTTP كلياً
// عبر debugSimulateSuccessfulSync() (@visibleForTesting) الذي يُشغّل نفس
// مسار كتابة الكاش المُستخدَم فعلياً بعد أي مزامنة ناجحة حقيقية.
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meter_reading_app/core/database/app_database.dart'
    hide Customer, Meter;
import 'package:meter_reading_app/features/customers/data/odoo_assignment_repository.dart';
import 'package:meter_reading_app/features/customers/domain/entities.dart';

ReadingAssignment _assignment({
  required int customerId,
  required int meterId,
  required String meterNumber,
  double? lastReadingValue,
}) {
  final customer = Customer(
    remoteId: customerId,
    customerNumber: 'C$customerId',
    accountNumber: 'ACC-$customerId',
    name: 'Customer $customerId',
    lastReadingValue: lastReadingValue,
    lastReadingDate: lastReadingValue == null ? null : DateTime(2026, 8, 1),
  );
  final meter = Meter(
    remoteId: meterId,
    meterNumber: meterNumber,
    customerRemoteId: customerId,
    paymentType: MeterPaymentType.postpaid,
  );
  return ReadingAssignment(
    id: 'assign-$customerId',
    meter: meter,
    customer: customer,
    status: AssignmentStatus.pending,
    scheduledAt: DateTime.now(),
    averageConsumption: 0,
  );
}

void main() {
  // OdooAssignmentRepository يتطلب OdooApiClient بالـ constructor لكن لا
  // تستدعيه هذه الاختبارات إطلاقاً (تستخدم debugSimulateSuccessfulSync
  // مباشرة)، فتمرير null آمن هنا فقط لأغراض الاختبار.
  test(
    'بعد مزامنة ناجحة، إعادة إنشاء الـ repository بدون أي مزامنة جديدة '
    '(محاكاة إعادة تشغيل التطبيق: _all فارغة بالذاكرة من جديد) لا تزال '
    'تُرجع نفس البيانات — بما فيها lastReadingValue — من كاش Drift وحده',
    () async {
      final executor = NativeDatabase.memory();
      final db = AppDatabase.forTesting(executor);
      final repo1 = OdooAssignmentRepository(null, db);

      final x = _assignment(
          customerId: 1, meterId: 100, meterNumber: 'M-100',
          lastReadingValue: 1234.5);
      await repo1.debugSimulateSuccessfulSync([x], 55);

      // "إعادة تشغيل التطبيق": repository جديد كلياً بحالة ذاكرة فارغة
      // (_all == []) — بنفس اتصال قاعدة البيانات (يمثّل نفس ملف
      // meter_reading.sqlite على القرص بين تشغيلتين للتطبيق). لا نستدعي
      // debugSimulateSuccessfulSync هنا إطلاقاً — هذا بالضبط ما يثبت أن
      // القراءة أتت من Drift وليس من مزامنة جديدة.
      final repo2 = OdooAssignmentRepository(null, db);

      final result = await repo2.getById('assign-1');
      expect(result, isNotNull);
      expect(result!.customer.lastReadingValue, 1234.5);
      expect(result.meter.meterNumber, 'M-100');

      await db.close();
    },
  );

  test(
    'مزامنة فترة B مختلفة عن فترة A تمسح مشتركي A الذين لم يعودوا '
    'موجودين بالكامل من الكاش، لا تُبقيهم فقط مع مشتركي B',
    () async {
      final executor = NativeDatabase.memory();
      final db = AppDatabase.forTesting(executor);
      final repo = OdooAssignmentRepository(null, db);

      final x = _assignment(customerId: 1, meterId: 100, meterNumber: 'M-X');
      final y = _assignment(customerId: 2, meterId: 200, meterNumber: 'M-Y');
      final z = _assignment(customerId: 3, meterId: 300, meterNumber: 'M-Z');

      // فترة A: X وY
      await repo.debugSimulateSuccessfulSync([x, y], 10);
      var cached = await repo.loadFromCache();
      expect(cached.map((a) => a.id).toSet(), {'assign-1', 'assign-2'});

      // فترة B (مختلفة): Y وZ فقط — بدون X
      await repo.debugSimulateSuccessfulSync([y, z], 20);
      cached = await repo.loadFromCache();

      expect(
        cached.any((a) => a.id == 'assign-1'),
        isFalse,
        reason: 'مشترك الفترة السابقة (X) يجب أن يختفي بالكامل من الكاش '
            'بعد مزامنة فترة جديدة، لا أن يبقى معلَّقاً من فترة مغلقة.',
      );
      expect(cached.map((a) => a.id).toSet(), {'assign-2', 'assign-3'});

      await db.close();
    },
  );
}
