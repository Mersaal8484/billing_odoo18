import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/collections/domain/collection_models.dart';
import '../features/collections/presentation/collection_account_screen.dart';
import '../features/collections/presentation/collection_history_screen.dart';
import '../features/collections/presentation/collection_report_screen.dart';
import '../features/collections/presentation/collector_home_screen.dart';
import '../features/collections/presentation/payment_screen.dart';
import '../features/collections/presentation/qr_scanner_screen.dart';
import '../features/collections/presentation/receipt_screen.dart';
import '../features/auth/presentation/login_screen.dart';
import '../features/customers/presentation/customer_detail_screen.dart';
import '../features/customers/presentation/customer_list_screen.dart';
import '../features/dashboard/presentation/dashboard_screen.dart';
import '../features/readings/presentation/photo_capture_screen.dart';
import '../features/readings/presentation/reading_entry_screen.dart';
import '../features/settings/presentation/settings_screen.dart';
import '../features/supervisor/presentation/supervisor_dashboard_screen.dart';
import '../features/sync/presentation/queue_monitor_screen.dart';
import '../features/sync/presentation/sync_center_screen.dart';
import '../shared/widgets/state_widgets.dart';
import 'providers.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final loggedIn = ref.read(authStateProvider);
      final onLogin = state.matchedLocation == '/login';
      if (!loggedIn && !onLogin) return '/login';
      if (loggedIn && onLogin) return '/dashboard';

      // Navigation visibility is not an authorization boundary (Odoo enforces
      // that server-side), but direct/deep links must still honour the latest
      // capabilities returned for this signed-in user.
      final roles =
          ref.read(currentUserProvider)?.roles ?? const <String, bool>{};
      final location = state.matchedLocation;
      final readerRoute = location == '/customers' ||
          location.startsWith('/customers/') ||
          location.startsWith('/readings/');
      final collectorRoute =
          location == '/collector' || location.startsWith('/collector/');
      final supervisorRoute = location == '/supervisor';
      if ((readerRoute && roles['is_meter_reader'] != true) ||
          (collectorRoute && roles['is_collector'] != true) ||
          (supervisorRoute && roles['is_supervisor'] != true)) {
        return '/dashboard';
      }
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
      GoRoute(
          path: '/dashboard',
          builder: (context, state) => const DashboardScreen()),
      GoRoute(
          path: '/customers',
          builder: (context, state) => const CustomerListScreen()),
      GoRoute(
        path: '/customers/qr',
        builder: (context, state) => const QrScannerScreen(isReaderMode: true),
      ),
      GoRoute(
        path: '/customers/:id',
        builder: (context, state) =>
            CustomerDetailScreen(assignmentId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/readings/new/:assignmentId',
        builder: (context, state) => ReadingEntryScreen(
            assignmentId: state.pathParameters['assignmentId']!),
      ),
      GoRoute(
          path: '/readings/photo',
          builder: (context, state) => const PhotoCaptureScreen()),
      GoRoute(
          path: '/collector',
          builder: (context, state) => const CollectorHomeScreen()),
      GoRoute(
        path: '/collector/accounts/:id',
        builder: (context, state) =>
            CollectionAccountScreen(accountId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/collector/payment/:id',
        builder: (context, state) => PaymentScreen(
          accountId: state.pathParameters['id']!,
          initialInvoice: state.extra is CollectionInvoice
              ? state.extra as CollectionInvoice
              : null,
        ),
      ),
      GoRoute(
        path: '/collector/receipt/:id',
        builder: (context, state) {
          final receipt = state.extra;
          if (receipt is CollectionReceipt) {
            return ReceiptScreen(receipt: receipt);
          }
          return const Scaffold(
            body: EmptyState(
              icon: Icons.receipt_long_outlined,
              title: 'الإيصال غير متاح',
              subtitle: 'افتح الإيصال بعد تسجيل عملية تحصيل جديدة.',
            ),
          );
        },
      ),
      GoRoute(
          path: '/collector/history',
          builder: (context, state) => const CollectionHistoryScreen()),
      GoRoute(
          path: '/collector/report',
          builder: (context, state) => const CollectionReportScreen()),
      GoRoute(
          path: '/supervisor',
          builder: (context, state) => const SupervisorDashboardScreen()),
      GoRoute(
          path: '/sync', builder: (context, state) => const SyncCenterScreen()),
      GoRoute(
          path: '/sync/queue',
          builder: (context, state) => const QueueMonitorScreen()),
      GoRoute(
          path: '/settings',
          builder: (context, state) => const SettingsScreen()),
    ],
  );
});
