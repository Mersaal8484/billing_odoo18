# Meter Reading App — Odoo 18

Flutter offline-first application for meter readers and collectors, integrated
with the Odoo 18 Utility ERP (`utility_core`, `utility_billing`, and
`utility_operations`). The app preserves the local Drift queue and separates
reading data synchronization from image synchronization.

The production providers use the Odoo API repositories. `Mock*Repository`
implementations are retained only for isolated UI and unit tests; UI code must
continue to depend on domain interfaces rather than a concrete data source.

## Environment configuration

The local Odoo 18 defaults are set centrally in `lib/core/config/app_config.dart`:

```text
http://192.168.8.134:9001
invoice_odoo18_db
```

Do not hard-code a server address or database name elsewhere. A non-local
build must override both values explicitly:

```text
--dart-define=ODOO_BASE_URL=https://erp.example.com
--dart-define=ODOO_DATABASE=your_odoo_database
```

## Run

```
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs   # generates app_database.g.dart
flutter run
```

Release APKs split by Android ABI:

```text
flutter build apk --release --split-per-abi --target-platform android-arm,android-arm64
```

## Structure

```
lib/
  app/                 theme, router, provider wiring (composition root)
  core/
    database/          Drift schema — the offline source of truth
    sync/              two-pipeline sync engine (simulated network in this phase)
    image/             on-device JPEG compression (<=60KB, no metadata/GPS)
    security/          (placeholder — secure storage wiring comes with auth phase)
  features/
    auth/               login (mock session only)
    dashboard/          reader home, progress, quick actions
    customers/          assignment list + detail (mock ERP customer/meter data)
    readings/           reading entry, photo capture, local validation
    sync/               sync center + per-item queue monitor
    settings/           profile, sync prefs, logout
  shared/widgets/       loading/empty/error/offline state widgets used everywhere
```

## Design decisions carried over from the existing ERP

Read directly from `utility_erp/utility_billing` and `utility_core` in the
provided repository (`utility_reading.py`, `utility_reading_batch.py`,
`utility_reader_api.py`, `utility_meter.py`, `utility_route.py`):

- **Reading state machine** (`draft → under_review → approved → queued →
  billed`, plus `error`) is respected by the local `ReadingSyncStatus`
  model — the app never invents states the ERP doesn't already understand.
- **Batch upload shape already exists server-side**: `date_range_id` +
  JSON payload of readings + separately-attached images keyed by
  filename, confirmed via `action_confirm`, processed by a chunked cron
  (`_cron_process_readings`). Pipeline A/B in this app are designed to
  produce exactly that shape later, without redesigning the ERP side.
- **Photo required for billable readings**: `action_submit_review`
  rejects customer-category readings with no `meter_image`. The reading
  entry screen enforces the same rule locally, before the record ever
  reaches a queue.
- **No GPS/location fields exist anywhere in the ERP models** examined
  (`utility.customer`, `utility.meter`, `utility.route`) — consistent with
  the "no GPS" requirement; nothing needs to be removed on the backend side.

## Known gaps to resolve in the backend phase (not addressed here on purpose)

- `utility_reader_api.py` uses Odoo's session-based `auth='user'`, not a
  mobile-appropriate token/API-key/OAuth scheme — needs a real auth
  strategy (refresh tokens, device registration) before going to production.
- The server's configured max image size (`utility.max_image_size_kb`,
  default 100KB) does not match this app's 60KB target — needs a config
  change or an explicit product decision before wiring Pipeline B for real.
- No dedicated "route assignment download" endpoint currently exists;
  `utility.route.customer_ids` / `inspector_ids` would need a thin new API
  to hand a reader their working set for a period. To be scoped and
  justified explicitly, per the integration ground rules, when that phase starts.
