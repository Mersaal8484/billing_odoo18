# SYSTEM REQUIREMENTS SPECIFICATION (SRS)

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 (Including Implemented Organizational Region/Branch Data Isolation)

**Document Type:** Formal System Requirements Specification

## Current Implementation Baseline

Repository: `AbdulrhmanBashammmakh/utility_erp`
Branch: `development`
Implementation SHA: `bf951a05a6031e94192e692dacbeb9dd01ca035e`
Documentation Version: `3.2`
Documentation Status: Current V1 (Including Implemented Organizational Region/Branch Data Isolation)

Requirements below distinguish current implementation from accepted target architecture. Current V1 is the `date_range (OCA) → utility_core → utility_inventory → utility_operations → utility_billing` chain; `utility_prepaid` and `additional` have been deleted from the repository.

### Current V1 lifecycle compatibility

`utility.reading` uses `draft`, `under_review`, `approved`, `queued`, `billed`, and `error`. A separate `billing_state` is not a current implementation requirement. Operational workflows use named actions and readonly/non-clickable state presentation where hardened.

### Current operational lifecycle compatibility

- Installation: `draft → installed → verified`; failure is possible from `draft` or `installed` and `failed` is terminal in the UI.
- Work Order: `draft → assigned → in_progress → completed → verified`; cancellation is limited to accepted source states and is terminal in the UI.
- Inspection: `scheduled → completed` or `scheduled → cancelled`; condition rating is supported where present.
- Alarm: `open → acknowledged → investigating → resolved/dismissed`; terminal alarms are excluded from active operational counts, and alarm-to-service-order creation is lock/idempotency protected.
- Meter replacement requires explicit confirmation before stock movement and meter lifecycle mutation.

Direct state editing is not equivalent to executing a workflow action because actions may assign users, write timestamps, create linked records, perform stock movement, and run business validation.

### Organizational security requirements

The security architecture SHALL keep functional roles independent from organizational scope. In the canonical `utility.region` hierarchy, `type='area'` is the organizational Branch. A complete `GLOBAL/RESTRICTED` scope mode, automatic Region-to-area expansion (`_get_effective_branch_ids()`), explicit Branch assignment, and server-side isolation via true global record rules (`global=True`, `groups=[(6, 0, [])]`) are **CURRENT V1 VERIFIED IMPLEMENTATION**.

An empty restricted scope SHALL be default-deny. UI domains SHALL NOT be treated as the security boundary. Any `sudo()` path SHALL resolve company and organizational scope before processing user-supplied identifiers.

> صياغة قابلة للاختبار للمتطلبات باستخدام معرفات ثابتة وعبارة SHALL.

---


## المبادئ المعمارية الملزمة

- Odoo 16 Community هو **System of Record** للـUtility Domain والمحاسبة.
- التشغيل المستهدف لمؤسسة تشغيلية واحدة؛ النطاق الأمني والتشغيلي يعتمد على Geography وليس Business Multi-Company.
- لا توجد Customer Wallet في Postpaid Utility.
- لا توجد Taxes في Utility Billing Flow الحالي.
- Reading + Review مرحلة تشغيلية واحدة.
- لكل Cycle فترة Reading وفترة Payment مستقلة مرتبطة بنفس `cycle_key`.
- `utility.bill.reading.component` هو Immutable Billing Segment Snapshot ولا يعاد تصميمه.
- `periodic` هو Billing Anchor، و`replacement_closing` و`opening` يحتفظان بدلالتهما.
- عدة عمليات Replacement داخل نفس Cycle تنتهي إلى **فاتورة واحدة** للحساب/الفترة مع عدة Reading Components.
- `utility.media.asset` هو Canonical Media Model.
- Payment Reconciliation يجب أن يكون Targeted/Explicit، وليس Partner-wide.
- التصحيحات التاريخية تتم بواسطة Correction/Reversal Documents، وليس بتعديل السجل التاريخي المنشور.
- Hybrid Workflow: المعاملات القصيرة داخل Odoo؛ Temporal للعمليات الطويلة وReading Batch orchestration عند Target Scale.
- Redis مساعد للـRate Limiting/Cache فقط، وليس Source of Truth.
- PgBouncer جزء من Target Production Scale عند تعدد العقد والـWorkers.
- Persistent Staging + Idempotency + Partial Failure هي القاعدة لدفعات القراءات.


## 1. الجهات الفاعلة

- System Administrator.
- Billing Manager.
- Revenue Manager.
- Auditor.
- Supervisor.
- Cashier.
- Collector.
- Technician.
- Field Inspector.
- Portal Customer.
- AMI Provider.
- Payment Provider.
- Background Worker/Workflow Engine.

---

## 2. Functional Requirements

### Accounts & Network

**SRS-ACC-001** — SHALL maintain an electricity account separately from `res.partner`.
**SRS-ACC-002** — SHALL assign account geography and route.
**SRS-ACC-003** — SHALL support master/aggregate accounts without merging child operational documents.
**SRS-NET-001** — SHALL maintain Substation→Feeder→Transformer→Meter topology.
**SRS-MTR-001** — SHALL maintain unique meter number and serial identity.
**SRS-MTR-002** — SHALL maintain one logical current connection target per meter.

### Periods

**SRS-PER-001** — SHALL generate Reading and Payment periods atomically per cycle.
**SRS-PER-002** — SHALL support monthly and semi-monthly H1/H2 cycles.
**SRS-PER-003** — SHALL preserve immutable `cycle_key` after operational opening.
**SRS-PER-004** — SHALL use Reading states `planned/open/closing/closed/locked`.
**SRS-PER-005** — SHALL use Payment states `planned/open/closing/reconciled/locked`.
**SRS-PER-006** — SHALL record reopen as an audited action, not a state.
**SRS-PER-007** — SHALL prevent normal reopen of locked periods.
**SRS-PER-008** — SHALL snapshot payment regions from its Reading period.

### Reading

**SRS-RED-001** — SHALL accept manual and AMI readings.
**SRS-RED-002** — SHALL associate every billable periodic reading with exactly one Reading Period.
**SRS-RED-003** — SHALL distinguish `periodic`, `replacement_closing`, and `opening`.
**SRS-RED-004** — SHALL not treat zero-consumption `opening` reading as zero-consumption anomaly.
**SRS-RED-005** — SHALL reject duplicate source reading according to the defined idempotency key.
**SRS-RED-006** — SHALL isolate invalid batch lines without rejecting valid lines.

### Media

**SRS-MED-001** — SHALL represent canonical evidence as `utility.media.asset`.
**SRS-MED-002** — SHALL store evidence as standard single `ir.attachment` records (`attachment=True`) without redundant thumbnail variants or external object storage (S3/MinIO) in V1.
**SRS-MED-003** — SHALL accept raw bytes at the Media Service boundary.
**SRS-MED-004** — SHALL validate image bytes before marking asset ready.
**SRS-MED-005** — SHALL authorize media using the same geographic policy as the linked business record.
**SRS-MED-006** — SHALL create a new revision on evidence replacement.
**SRS-MED-007** — SHALL provide repair tooling for legacy corrupted/double-base64 assets.

### Billing

**SRS-BIL-001** — SHALL create at most one active Utility Bill per Account + Reading Period.
**SRS-BIL-002** — SHALL use `utility.bill.reading.component` as immutable segment snapshots.
**SRS-BIL-003** — SHALL include pending replacement-closing segments in the next periodic bill.
**SRS-BIL-004** — SHALL produce one bill for multiple replacement segments in the same cycle.
**SRS-BIL-005** — SHALL create/post the accounting invoice according to configured billing policy.
**SRS-BIL-006** — SHALL use no taxes in the current Utility Billing flow.
**SRS-BIL-007** — SHALL persist immutable pricing calculation evidence (`utility.bill.pricing.snapshot`) and applied block breakdown (`utility.bill.pricing.block`) at billing time.
**SRS-BIL-008** — SHALL be idempotent under retry/concurrent billing requests.

### Tariff & Contract Template Versioning

**SRS-TAR-001** — SHALL support flat pricing (`flat`).
**SRS-TAR-002** — SHALL support single-tier pricing applied to full consumption (`tier`).
**SRS-TAR-003** — SHALL support progressive block pricing (`block`).
**SRS-TAR-004** — SHALL block unsupported pricing modes (`seasonal`, `tou`) with explicit `ValidationError` in V1.
**SRS-TAR-005** — SHALL support fixed/service/local fees and private transformer fees.
**SRS-TAR-006** — SHALL support discounts, dynamic formulas, and sponsor policies.
**SRS-TAR-007** — SHALL validate full block coverage for tier- and block-based pricing templates.
**SRS-TAR-008** — SHALL maintain immutable contract template versioning (`utility.contract.template.version`), automatically creating new versions when billed templates are updated.
**SRS-TAR-009** — SHALL prevent direct modification or deletion of contract template versions and pricing snapshots linked to active or confirmed bills.
**SRS-TAR-010** — SHALL provide a clone wizard (`utility.contract.template.clone.wizard`) to create independent contract templates with new identity, fresh Version 1, and isolated historical data.

### Payment

**SRS-PAY-001** — SHALL allocate payments to explicit target invoices.
**SRS-PAY-002** — SHALL prohibit automatic reconciliation of unrelated receivable lines of the same partner.
**SRS-PAY-003** — SHALL lock the payment target before confirming concurrent payment.
**SRS-PAY-004** — SHALL reject allocation above current residual.
**SRS-PAY-005** — SHALL process a successful provider callback exactly once.
**SRS-PAY-006** — SHALL reject replay/duplicate provider references.
**SRS-PAY-007** — SHALL maintain payment period linkage to the exact reading period bill.

### Corrections

**SRS-COR-001** — SHALL keep billed reading and bill component immutable.
**SRS-COR-002** — SHALL calculate correction delta in a separate settlement.
**SRS-COR-003** — SHALL create debit invoice or credit note when correction has financial impact.
**SRS-COR-004** — SHALL retain the original historical reading.

### Meter Replacement

**SRS-REP-001** — SHALL create approved old-meter closing reading.
**SRS-REP-002** — SHALL create approved new-meter opening reading.
**SRS-REP-003** — SHALL ensure old and new meter differ.
**SRS-REP-004** — SHALL transfer logical connection from old to new meter.
**SRS-REP-005** — SHALL update stock/custody through the operations/inventory layer.
**SRS-REP-006** — SHALL preserve unbilled old-meter consumption for future combined billing.

### Inventory

**SRS-INV-001** — SHALL model serialized physical meter by `stock.lot`.
**SRS-INV-002** — SHALL prevent one stock serial from mapping to multiple active logical meters.
**SRS-INV-003** — SHALL support warehouse, technician custody, installed, quarantine, repair, return and scrap paths.
**SRS-INV-004** — SHALL prevent installation of unavailable/unreserved meter.
**SRS-INV-005** — SHALL record each custody transfer through Odoo Stock.

### Security

**SRS-SEC-001** — SHALL use `assigned_region_ids` as geographic source of truth.
**SRS-SEC-002** — SHALL default deny non-admin users with no assigned regions.
**SRS-SEC-003** — SHALL grant unrestricted geographic access only to Utility Admin.
**SRS-SEC-004** — SHALL apply equivalent authorization to UI, API, media, review and operations.
**SRS-SEC-005** — SHALL not treat `sudo()` as authorization.

### Integration

**SRS-INT-001** — SHALL persist external side effects in an outbox/command before asynchronous delivery where applicable.
**SRS-INT-002** — SHALL retry transient failures with bounded attempts/backoff.
**SRS-INT-003** — SHALL expose dead-letter/manual retry for exhausted commands.
**SRS-INT-004** — SHALL redact secrets from logs.
**SRS-INT-005** — SHALL use Temporal only for the approved workflow scope.

---

## 3. Non-Functional Requirements

**SRS-NFR-001** — SHALL tolerate partial batch failures.
**SRS-NFR-002** — SHALL process million-subscriber monthly cycles by deterministic micro-batches, not one giant transaction.
**SRS-NFR-003** — SHALL use PostgreSQL partition planning for high-growth reading/staging tables.
**SRS-NFR-004** — SHALL use connection pooling in target multi-worker topology.
**SRS-NFR-005** — SHALL deliver review images without automatically fetching originals.
**SRS-NFR-006** — SHALL collect metrics sufficient to measure latency, throughput, errors, queue depth and DB health.
**SRS-NFR-007** — SHALL support tested backup/restore.
**SRS-NFR-008** — SHALL preserve backward migration traceability.

---

## 4. Requirement Verification

كل Requirement يجب أن يرتبط بواحد أو أكثر من:

```text
Unit Test
Transaction Test
Concurrency Test
Security Test
Load Test
Migration Validation
UAT Scenario
Operational Drill
```

ولا تعتبر Requirement مكتملة بمجرد نجاح الشاشة يدويًا.
