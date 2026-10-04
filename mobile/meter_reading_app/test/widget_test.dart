import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:meter_reading_app/app/app.dart';

void main() {
  testWidgets('shows login screen', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: MeterReadingApp()));

    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(2));
  });
}
