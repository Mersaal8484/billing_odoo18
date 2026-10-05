# PAYMENT ALLOCATION

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Payment Allocation & Reconciliation Specification

> إلغاء المطابقة العامة للشريك واعتماد تخصيص صريح وآمن تحت التزامن.

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


## 1. Core Rule

```text
Payment
  → Allocation Lines
      → Explicit Accounting Invoice(s)
```

ممنوع:
```text
find all partner receivables
→ reconcile all
```

---

## 2. Data Model Target

Suggested allocation entity:
- payment_id.
- utility_sale_order_id.
- move_id.
- amount.
- currency.
- state.
- allocation_key.
- created_by/date.
- reconciliation reference.

يمكن التنفيذ كنموذج مستقل أو abstraction مناسبة، لكن يجب أن تكون العلاقة explicit/auditable.

---

## 3. Inbound Flow

1. Resolve Utility Bill.
2. Read current posted invoice residual.
3. Lock target order/invoice.
4. Validate bill payable.
5. Validate amount > 0.
6. Validate allocated total ≤ residual.
7. Create/post account.payment.
8. Select payment receivable line.
9. Select target invoice receivable line.
10. reconcile selected lines only.
11. persist allocation.
12. refresh bill state.

---

## 4. Multiple Bill Allocation

عند دعم Payment واحدة لعدة فواتير:
- sum allocations = payment amount, except approved unapplied balance policy.
- each allocation ≤ invoice residual.
- deterministic order if auto-allocation is allowed by explicit policy.
- user-visible allocation detail.

---

## 5. Concurrency

Example:
```text
Residual = 1000
A = 600
B = 600
```

Transaction A/B both must lock target before final validation.

Allowed final result:
```text
A=600
B=400 or B rejected/adjusted
```

Never 1200.

---

## 6. Gateway Callback

1. lock gateway transaction.
2. idempotency check.
3. lock target bill/invoice.
4. validate residual.
5. create payment once.
6. allocate.
7. mark transaction done.

Provider reference unique per provider.

---

## 7. Overpayment

No silent overpayment.

The Odoo 18 collector flow posts one standard `account.payment` on the
customer's Receivable account and partner subledger. It settles the selected
current invoice first, then that same customer's prior open invoices by oldest
due date (invoice date, then ID as stable tie-breakers). Any remaining amount
stays as the standard unreconciled customer credit on that same Receivable
account and partner. It is neither income nor a parallel customer wallet.

---

## 8. Refund / Outbound

Outbound payment must reference explicit source:
- credit note.
- approved refund.
- deposit release.
- other authorized accounting document.

---

## 9. Reversal

Payment reversal:
- reverse/unreconcile target allocation explicitly.
- maintain audit.
- restore residual deterministically.
- never delete posted financial history.

---

## 10. Payment Period

Every utility payment references Payment Period linked to bill's Reading Period.

Classification:
- on_time.
- late.
- exceptional.
- outside_window.

Due/late logic uses due date/payment policy rather than Sale Order date alone.

---

## 11. Acceptance

- full payment.
- partial.
- two partial payments.
- concurrent payments.
- multi-invoice allocation.
- duplicate callback.
- overpayment.
- cancelled/paid bill rejection.
- reversal.
- no unrelated partner line reconciled.

## V3.2 Current Implementation Synchronization

```text
Payment Entry Point
        ↓
Payment Allocation
        ↓
Specific Accounting Invoice
        ↓
Reconciliation
        ↓
Financial Artifacts
        ↓
Controlled Reversal
```

**CURRENT V1:** exact invoice allocation, payment/invoice locking, reconciliation, allocation records, gateway idempotency, and financial reversal orchestration are implemented in the Billing/Accounting boundary. No partner-wide arbitrary reconciliation is permitted.

**DEFERRED:** “Static implementation includes concurrency controls; runtime proof is separately deferred.”

## V3.3 Current Collector Allocation Policy

The collector app shows the current bill, prior arrears, and total due. A
payment is always posted against the partner Receivable account, not against a
separate invoice-only balance. Reconciliation is nevertheless explicit and
safe: only posted outgoing invoices with the same company, partner,
utility-customer account, compatible currency, and Receivable account qualify.

Allocation order is:

1. selected current invoice;
2. prior open invoices from older billing periods, oldest due invoice first;
3. any excess remains an unapplied receivable credit for that customer.

The policy never reconciles another customer's, company's, currency's, or
Receivable-account lines, and it retains the per-invoice allocation audit.
