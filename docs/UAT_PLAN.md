# UAT PLAN

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `b97bea78aaba6b91575dd9b8cd2c14d685c64fd5`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.3
**Last Verified Date:** 2026-09-18
**Status:** Current V1 (Including Implemented Organizational Region/Branch Data Isolation)

**Document Type:** User Acceptance Test Plan

> خطة قبول أعمال شاملة لكل المسارات الحرجة قبل Release Candidate وGo-Live.

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


## 1. UAT Objectives

إثبات أن النظام:
- صحيح وظيفيًا.
- صحيح ماليًا.
- قابل للتشغيل.
- آمن حسب الأدوار.
- قابل للتتبع.
- يتحمل السيناريوهات الاستثنائية الأساسية.

---

## 2. Entry Criteria

- P0 defects مغلقة.
- migration rehearsal complete.
- test environment production-like.
- accounting configuration approved.
- tariff test data approved.
- users/roles configured.
- backup/restore drill complete or scheduled before exit.
- Golden Billing tests pass.

---

## 3. Test Data

Include:
- monthly account.
- semi-monthly H1/H2.
- flat tariff.
- tier.
- progressive.
- discounted/sponsored.
- account with replacement(s).
- overdue.
- deposit.
- multiple regions/roles.
- AMI/manual.
- media variants.
- concurrent payment target.

---

## 4. Core UAT Scenarios

### UAT-001 Account & Meter
create/activate account and meter.

### UAT-002 Period Generation
monthly and semi-monthly pair.

### UAT-003 Manual Reading
upload image, review, approve.

### UAT-004 Batch Reading
10k-style functional subset with partial errors.

### UAT-005 AMI
authenticated callback, duplicate prevention.

### UAT-006 Billing Normal
periodic → one bill → accounting invoice.

### UAT-007 Replacement
old closing + new opening + next periodic → combined one bill.

### UAT-008 Multiple Replacements & Progressive Aggregation
multiple components same cycle:
- old meter closing reading + new meter periodic reading in same period;
- verify exactly ONE `sale.order` bill is generated with multiple `utility.bill.reading.component` records;
- verify total combined consumption is calculated across progressive tariff blocks (`block`) seamlessly;
- verify posted `account.move` reflects combined energy charge and valid pricing snapshot.

### UAT-009 Tariff Modes & Block Discounts with Sponsor Fund
flat/tier/block/discount/min/max:
- multi-tier progressive block tariffs (e.g. 0-100 @ 10, 100-300 @ 20, 300+ @ 30);
- tiered block discount relief with sponsor partner tracing to `partner_sponsor_fund` ("الصندوق");
- verify zero consumption maintains fixed service charges without division-by-zero errors;
- verify meter multiplier scaling applies accurately before block tiering.

### UAT-010 Payment Full & Targeted Allocation
explicit allocation/reconciliation:
- targeted allocation to specific invoice;
- verify overpayment exceeding invoice residual is blocked (`ValidationError`);
- verify cancelling an allocation cleanly un-reconciles entries and restores invoice residual without cross-invoice debt leakage.

### UAT-011 Payment Partial
correct residual isolation.

### UAT-012 Concurrent Payment
no over-allocation.

### UAT-013 Gateway Duplicate
callback idempotency.

### UAT-014 Penalty
eligibility/apply/waive/reversal policy.

### UAT-015 Deposit
collector settlement and bank deposit:

- confirm a collector settlement and verify its posted accounting move;
- create a bank deposit with collector, amount, bank journal, and reference,
  without manual allocation lines;
- verify automatic reference-priority/FIFO allocation and exact deposit-clearing
  partial reconciliation;
- repeat the internal post call and verify no second accounting move is made;
- attempt a duplicate company-scoped settlement key and verify rejection;
- verify no bank statement line or later bank-matching action is required.

### UAT-016 Writeoff/Settlement & Immutability
approval and accounting:
- draft → approved → applied lifecycle;
- generates exactly one Credit Note (`out_refund`) and reconciles against target invoice;
- immutability: verify applying or reverting applied write-off twice is strictly blocked.

### UAT-016B Meter Lifecycle & Replacement Integrity
- verify replacing a meter with itself is strictly rejected (`ValidationError`);
- verify replacement closing reading lower than last invoiced reading is blocked;
- verify continuous `utility.meter.assignment` history recording.

### UAT-017 Reading Correction
original immutable; debit/credit correction.

### UAT-018 Disconnection/Reconnection
service order and account status.

### UAT-019 Inventory Custody
warehouse→technician→installed→removed.

### UAT-020 Security
other region denied in UI/API/media.

### UAT-021 Period Close/Reopen/Lock
audit and guards.

### UAT-022 Portal
own account only.

---

## 5. Financial Acceptance

For selected scenarios validate:
```text
Utility amount
= Accounting invoice amount
= Residual before payment
- allocated payment
= Residual after payment
```

Trace each amount back to reading/components.

---

## 6. Defect Severity

- P0: data loss/financial/security/history corruption.
- P1: critical business flow unusable.
- P2: significant workaround.
- P3: cosmetic/minor.

UAT exit:
- zero open P0.
- zero open unaccepted P1.
- P2 only with signed workaround/plan.

---

## 7. Performance UAT

Business validates:
- review queue usability.
- image responsiveness.
- batch progress visibility.
- billing operational window.
- report responsiveness under agreed scope.

Technical Load Test remains separate but contributes to exit.

---

## 8. Sign-Off

Required sign-off representatives:
- Billing.
- Accounting/Revenue.
- Operations.
- Inventory/Warehouse.
- IT/Security.
- Data Migration.
- Business Owner.

---

## 9. Exit Criteria

- scenarios pass.
- financial reconciliation signed.
- security matrix signed.
- migration validation signed.
- backup restore signed.
- go-live rollback decision path approved.

## V2.1 Current Safety Scenarios

The following scenarios are required test coverage targets. They are not marked PASS unless runtime evidence is attached:

| Area | Required scenarios |
|---|---|
| Reading | valid periodic reading; invalid reading; billing review; error state; replacement reading |
| Reading Batch | valid batch; malformed JSON; invalid totals; partial/error batch; retry; ownership restriction; active/attention filters |
| Installation | `draft → installed → verified`; failed path; invalid transition rejected |
| Work Order | full lifecycle; cancellation; direct state manipulation is not the user workflow |
| Inspection | complete; cancel; optional condition rating |
| Alarm | acknowledge; investigate; resolve; dismiss; create service order; repeated creation attempt |
| Meter Replacement | confirmation; stock movements; closing/opening readings |
| Billing | reading → Bill; Bill → Accounting Invoice navigation; Payment navigation; residual correctness |
| Payment | exact invoice; partial payment; repeated gateway callback; invalid token; wrong provider reference |
| Write-off | approve; approved → draft; apply; duplicate apply; reopen after applied; exactly one Credit Note; readonly evidence; Credit Note navigation |
| Security | generic internal user denied sensitive wizards; supervisor operational access; supervisor denied admin network-master creation; admin allowed |

**DEFERRED:** runtime/CI execution, concurrency proof, upgrade verification, and production load validation are separate release activities.

## Organizational Security UAT

These scenarios are required for the planned scope hardening and are not execution results:

1. Same role, different Regions: Region A user cannot read/write/assign/approve Region B data.
2. Multiple Regions: a Billing Manager assigned A+B can access A/B but not C.
3. Region plus explicit Branch: A plus B-02 grants all A branches and only B-02, not B-01/B-03.
4. Explicit Global: a Global user sees all permitted records within allowed companies.
5. Empty Restricted scope: no assigned Region/Branch yields no scoped operational records, never global access.
6. Wizard security: out-of-scope Customer, Meter, Route, Transformer, Feeder, Replacement, and operational mutations are rejected server-side.
7. API security: technically valid out-of-scope IDs are rejected, including when `sudo()` is used internally.
8. Reporting security: list views, dashboards, exports, reports, `search_count`, and `read_group` exclude out-of-scope data.
9. Accounting safety: Utility scope rules do not break central posting, reconciliation, payment allocation, or accounting reports.

Until these scenarios have runtime evidence, complete Region/Branch isolation remains **TARGET V1 SECURITY HARDENING**.
