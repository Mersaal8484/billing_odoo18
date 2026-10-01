# MASTER SPECIFICATION

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Master Functional & Non-Functional Specification

## Current Implementation Baseline

Repository: `AbdulrhmanBashammmakh/utility_erp`
Branch: `development`
Implementation SHA: `bf951a05a6031e94192e692dacbeb9dd01ca035e`
Documentation Version: `3.2`
Documentation Status: Current V1 + Target V2

This document separates implementation evidence at the reviewed SHA from accepted forward-looking V2 architecture. Current behavior is authoritative for V1; accepted newer ADRs supersede stale documentation. Target V2 components remain target/deferred until their trigger and runtime gate are satisfied.

### Current V1 scope

`date_range (OCA) → utility_core → utility_inventory → utility_operations → utility_billing`

> **`utility_meter_vision`** (OCR/AI Vision) هي وحدة مستقبلية قيد التطوير (`installable: False`) وليست جزءاً من V1. لا تُدرج كاعتمادية حالية.


`utility_prepaid` and `additional` have been **deleted from the repository**. V1 is strictly focused on Postpaid electricity distribution. There is no customer wallet architecture, no parallel financial ledger, and no duplicate stock ledger.

### Current workflow and safety baseline

- `utility.reading`: `draft`, `under_review`, `approved`, `queued`, `billed`, `error`; a separate `billing_state` is **TARGET / FUTURE OPTIONAL DESIGN**, not current V1.
- `utility.writeoff`: `draft → approved → applied`; only `approved → draft` is allowed before financial application. After application, reopening and duplicate application are forbidden.
- Operational state changes occur through named actions, not direct statusbar edits, for the hardened critical forms.
- Runtime/CI proof and production-scale performance validation remain **DEFERRED**.

### Current V1 business path

```text
Customer → Contract Template → Contract Version (`utility.contract.template.version`)
         → Reading → Reading Snapshot (`utility.bill.reading.component`)
         → Pricing Snapshot (`utility.bill.pricing.snapshot` + `utility.bill.pricing.block`)
         → Bill (`sale.order`) → Accounting Invoice (`account.move`)
                               → Payment (`account.payment`)
                               → Allocation/Reconciliation → Settlement
```

The Bill form provides direct smart-button navigation to related Pricing Snapshots, Reading Components, Accounting Invoices, Payments, and Billing Adjustments. Commercial pricing versions (`utility.contract.template.version`) and calculation snapshots (`utility.bill.pricing.snapshot`) guarantee full immutability and historical audit integrity.

### Organizational security classification

Functional role authorization is **CURRENT V1**. User-assigned Regions/Routes and selected company/Region/Route rules are also current. In the canonical `utility.region` hierarchy, `type='area'` is the organizational Branch. Complete `GLOBAL/RESTRICTED` scope mode, user-level explicit Branch assignments, Region-to-area expansion, and comprehensive scope rules across all operational/reporting paths are **TARGET V1 SECURITY HARDENING**. Empty restricted scope must be default-deny, never global.

> المرجع التنفيذي الأعلى للمتطلبات الوظيفية وغير الوظيفية التي يجب أن تحقق المعمارية المستهدفة.

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


## 1. الهدف والنطاق

تحدد هذه الوثيقة ما يجب أن يقدمه Utility ERP عند اكتمال Target Architecture، دون أن تعيد تعريف تفاصيل التنفيذ الموجودة في الوثائق المتخصصة.

### داخل النطاق

- إدارة حسابات الكهرباء والمشتركين.
- إدارة العدادات والبنية الفنية والجغرافية.
- إدارة دورات القراءة والفوترة والتحصيل.
- Manual/AMI reading ingestion.
- Reading Review/VEE.
- Media evidence.
- Postpaid billing.
- Accounting invoices.
- Collections and payment allocation.
- Payment gateway integration.
- Meter replacement.
- Field operations.
- Meter inventory/custody.
- Penalties, deposits, write-offs, financial settlements.
- Portal/API.
- Migration, security, observability, backup/restore، وGo-Live.

### خارج النطاق الحالي

- Customer Wallet.
- Tax Engine داخل Utility Billing.
- Kafka.
- Distributed SQL.
- Temporal per invoice/notification.
- Full redesign لـ`utility_prepaid`.
- Business Multi-Company partitioning.

---

## 2. مصادر الحقيقة

| المجال | Source of Truth |
|---|---|
| الشخص/الجهة | `res.partner` |
| حساب الكهرباء | `utility.customer` |
| العداد المنطقي | `utility.meter` |
| الجهاز الفيزيائي/السيريال | `stock.lot` |
| القراءة | `utility.reading` |
| دورة التشغيل | `date.range` |
| مكون استهلاك الفاتورة | `utility.bill.reading.component` |
| فاتورة الكهرباء التشغيلية | `sale.order` |
| الحقيقة المحاسبية | `account.move` / `account.move.line` |
| السداد | `account.payment` + explicit allocation |
| دليل الصورة | `utility.media.asset` |
| الاستبدال | `utility.meter.replacement` |
| العملية الميدانية | `utility.service.order` |
| Outbox/Workflow Command | `utility.workflow.command` |

---

## 3. المتطلبات الوظيفية العليا

### MS-FR-001 — Utility Accounts
يجب أن يدعم النظام حسابات كهرباء مستقلة عن Partner، مع Region/Area/Zone/Route، Contract Template، Current Meter، وحالة تشغيلية.

### MS-FR-002 — Meter Lifecycle
يجب أن يدعم العداد حالات الربط بالمشترك/الفيدر/المحول، وسجلًا تاريخيًا لاختلافات الربط والاستبدال.

### MS-FR-003 — Billing Cycles
يجب إنشاء Reading Period وPayment Period كزوج ذري لكل Cycle، بدورية شهرية أو نصف شهرية.

### MS-FR-004 — Reading Intake
يجب استقبال القراءات يدويًا أو عبر Batch/AMI مع Idempotency، والتحقق من الفترة والعداد والحساب.

### MS-FR-005 — Reading Review
يجب أن تمر القراءة بمرحلة Validation/VEE/Review قبل أن تصبح Approved/Billable وفق السياسة.

### MS-FR-006 — Media Evidence
يجب أن يرتبط دليل الصورة بـ`utility.media.asset` كمرفق Odoo قياسي موحد (`ir.attachment`) في الـ Filestore بدون توليد مصغرات (No Thumbnails) وبدون S3/MinIO في الإصدار V1.

### MS-FR-007 — Billing
يجب أن ينتج النظام فاتورة Utility واحدة لكل Account + Reading Period نشط، مع Reading Components Immutable.

### MS-FR-008 — Tariff
يجب دعم Flat, Tier, Progressive Block, service/fixed fees, local fees, discount, min/max charge, formula-driven quantity، مع Historical Snapshot.

### MS-FR-009 — Replacement
يجب أن يولد الاستبدال Closing Reading للعداد القديم وOpening Reading للجديد، ويضم الاستهلاك غير المفوتر إلى الفاتورة الدورية التالية.

### MS-FR-010 — Accounting
يجب أن تتحول Utility Bill إلى Accounting Invoice قابلة للتتبع إلى Reading Components.

### MS-FR-011 — Payment
يجب تسجيل المدفوعات مع Allocation صريح إلى فواتير محددة، ومنع Over-allocation تحت التزامن.

### MS-FR-012 — Operations
يجب أن يدير Service Order دورة Request→Approval→Assignment→Schedule→Execution→Evidence→Completion.

### MS-FR-013 — Inventory/Custody
يجب تتبع العداد الفيزيائي من Receipt حتى Installation ثم Removal/Quarantine/Repair/Return/Scrap.

### MS-FR-014 — Corrections
لا يجوز تعديل Billed Historical Reading بصورة destructive. يجب استخدام Settlement/Correction Document ينتج Debit/Credit Accounting Document عند الحاجة.

### MS-FR-015 — Portal/API
يجب أن توفر الواجهات الخارجية نفس قواعد Authorization والـDomain، دون Business Logic بديل.

---

## 4. المتطلبات غير الوظيفية

### MS-NFR-001 — Integrity
كل عملية مالية أو تاريخية يجب أن تكون قابلة لإعادة البناء من المستندات الأصلية.

### MS-NFR-002 — Idempotency
كل Batch/Payment Callback/Billing Command/Workflow حساس يجب أن يمتلك Idempotency Key.

### MS-NFR-003 — Concurrency
عمليات Billing/Payment/Callback يجب أن تستخدم Constraints وRow Locks حيث يلزم.

### MS-NFR-004 — Partial Failure
دفعات القراءات والفوترة واسعة النطاق يجب ألا تستخدم Fail-All.

### MS-NFR-005 — Security
النطاق الجغرافي Default-Deny لكل Non-Admin.

### MS-NFR-006 — Auditability
كل تعديل استثنائي يحفظ Who/When/What/Why/Old/New/Source/Result.

### MS-NFR-007 — Scale
يجب أن تصمم المنظومة لسعة تخطيطية تصل إلى مليون مشترك مع Batch Processing وPartition Planning.

### MS-NFR-008 — Recoverability
يجب اختبار Backup/Restore قبل Go-Live.

### MS-NFR-009 — Observability
يجب قياس معدلات ingestion, billing, payment, errors, queue depth, media latency, DB health.

### MS-NFR-010 — Compatibility
لا تبنى Features جديدة على Compatibility Fields مثل `meter_image`, `attachment_id`, legacy period fields.

---

## 5. Traceability Rule

أي مبلغ يجب أن يكون قابلًا للتتبع:

```text
Utility Account
  → Reading
  → Bill Reading Component
  → Sale Order
  → Accounting Invoice
  → Payment Allocation
  → Payment
```

وأي استبدال:

```text
Service Order
  → Replacement
  → Closing/Opening Readings
  → Stock Movements
  → Billing Components
```

---

## 6. Release Gates

1. **Critical Integrity:** Media legacy repair, period migration, targeted reconciliation, immutable reading corrections.
2. **Billing/Period Production:** tariff snapshot, period impact, due-date policy, concurrency.
3. **Operations/Inventory:** custody and canonical stock logistics.
4. **Security/Integration:** unified scope, webhook hardening, outbox retry.
5. **Portal/UX:** customer-facing completeness.
6. **Migration/Scale:** rehearsals, partitioning/load tests, backup restore.
7. **UAT/Release Candidate:** no new features.

---

## 7. Definition of Done

- جميع الـP0 المالية والتاريخية مغلقة.
- Billing Golden Tests تمر.
- Payment concurrency tests تمر.
- Media upload/display/repair تمر.
- Replacement end-to-end يمر.
- Inventory custody مترابط.
- Security matrix مطبقة.
- Migration rehearsed.
- Backup restored successfully.
- UAT signed off.
