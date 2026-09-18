# BILLING ENGINE

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `b97bea78aaba6b91575dd9b8cd2c14d685c64fd5`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.3
**Last Verified Date:** 2026-09-18
**Status:** Current V1 + Target V2

**Document Type:** Billing Domain & Execution Specification

> المرجع الملزم لمحرك فوترة الكهرباء، مكوناته، invariants، التسعير، التزامن والتصحيحات.

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


## 1. Billing Identity

الوحدة المالية الأساسية:

```text
Utility Account + Reading Period
```

ينتج عنها:

```text
ONE Active Utility Bill
```

حتى لو مر الحساب بعدة عدادات داخل نفس الدورة.

---

## 2. Canonical Inputs

- Periodic Billing Anchor.
- Zero or more approved pending `replacement_closing` readings.
- Opening readings التي تحدد بداية Segment الجديد.
- Account Contract/Tariff.
- Meter multipliers.
- Historical last billed boundary.

---

## 3. Frozen Segment Model

`utility.bill.reading.component` هو Snapshot لا يعاد حسابه من Master Data لاحقًا.

يحفظ:
- reading.
- account.
- meter.
- purpose.
- period boundaries.
- previous/current reading.
- multiplier.
- consumption.
- company.

بعد Billing يصبح Immutable.

---

## 4. Replacement Aggregation Example

```text
Last billed periodic = 1000

Old Meter A:
closing = 1300
segment = 300

Meter B:
opening = 20
closing = 170
segment = 150

Meter C:
opening = 5
periodic = 105
segment = 100
```

النتيجة:

```text
Bill Consumption = 550
Components = [300, 150, 100]
ONE Sale Order
ONE Accounting Invoice
```

---

## 5. Billing Algorithm & Automated Approval Pipeline

1. **Image Review Gate:** Before approval, verify that `image_state == 'clear'`. Approvals without a verified clear image are blocked with a `ValidationError`.
2. **Reading Classification (`is_billable`):**
   - **Commercial / Subscriber & Private Transformer:** Periodic readings with `is_billable = True` immediately enter the billing queue (`state = 'queued'`) upon supervisor approval.
   - **Technical Network Readings (Feeders & Public Transformers):** `is_billable = False`. Upon approval, they remain in `state = 'approved'` as physical operational records and NEVER generate bills or invoices.
3. **Automated Invoice Generation Pipeline:**
   - On transition to `queued`, `_queue_approved_billable_readings` triggers `action_generate_bill()` with a database savepoint guard.
   - If `date_range_id` is missing on the reading, the billing queue auto-resolves and links the active current reading period (`date.range`).
   - The engine validates account/period and locks the target billing identity with `SELECT ... FOR UPDATE`.
   - Rejects existing active bill for account+period (enforcing idempotency and single bill per cycle).
   - Locks pending replacement-closing readings and persists `utility.bill.reading.component` snapshots.
   - Calculates order lines according to active contract version snapshot (flat, tier, block, service fees, local fees).
   - Creates `sale.order`, confirms it to `state = 'sale'`, creates and posts the customer invoice (`account.move` to `state = 'posted'`).
   - Sets reading `state = 'billed'` and clears any `billing_error`.
   - Fault-isolation: If automated billing fails (e.g., missing contract template or accounting setup), the transaction rolls back to the savepoint, logs a warning, records the error in `billing_error`, and safely retains the reading in `state = 'queued'`.

### 5.1 Review Console Scope & Visibility
- In the Reading Review Console (`utility.reading.review.service`), the "معتمدة" (Approved) queue tab and KPI statistics query `['approved', 'queued', 'billed']`.
- This ensures approved technical network readings (`approved`), queued readings (`queued`), and fully invoiced readings (`billed`) remain continuously visible in the operational workspace without disappearing after approval.
- In-row action controls allow operators to inspect meter images, evaluate image states (`action_mark_image_clear`, `action_mark_image_not_clear`, `action_set_image_state`), and execute single or bulk approvals safely.

---

## 6. Tariff Modes

### Flat
`total = consumption × flat price`

### Tier (Single Flat Tier)
حدد الشريحة على أساس إجمالي الاستهلاك ثم طبق سعرها على كامل الاستهلاك.

### Progressive Block
وزع الاستهلاك على الشرائح بصورة تصاعدية مع حساب الكمية والسعر لكل شريحة.

### Unsupported Modes in V1 (Explicitly Blocked)
- `seasonal` (الموسمي): غير مدعوم في V1 لعدم اكتمال دورة التسعير الشهرية/الموسمية في قراءات العدادات. يرفع `ValidationError`.
- `tou` (حسب وقت الاستخدام): غير مدعوم في V1 ويتطلب توفر قراءات فترية لحظية AMI/Interval Data. يرفع `ValidationError`.

### Additional Fees & Adjustments
- fixed/service charges (`service_charge`).
- local fees (`local_fee_per_kwh`, `local_fee_mu_allim`, `local_fee_cleaning`).
- discounts & sponsor discounts (`sponsor_id`, `discount_formula_id`, `discount_block_ids`).
- min/max charge adjustments.
- private transformer fee (`private_transformer_fee`).
- controlled formula quantities (`utility.formula`).

No taxes.

---

## 7. Tariff & Pricing Snapshots (Authoritative Models)

التنفيذ الفعلي يعتمد على الفصل التام بين الأدلة الفيزيائية للاستهلاك والأدلة التجارية للتسعير:

1. **النسخ التجارية للقوالب (`utility.contract.template.version`)**:
   - نموذج مخصص داخل `utility_core` يوثق التكوين التجاري لقالب العقد كلقطة ثابتة (`version_code`, `pricing_mode`, `price_per_kwh`, `service_charge`, `min_charge`, `max_charge`, `local_fee_*`, `pricing_snapshot_json`).
   - عند إنشاء قالب جديد يتم إنشاء Version 1 تلقائياً.
   - طالما لم يُستخدم الإصدار في أي فاتورة (`is_used_in_billing = False`)، يتم تحديث الإصدار في مكانه.
   - بمجرد استخدام الإصدار في إصدار فاتورة، فإن أي تعديل لاحق على القالب يُنشئ تلقائياً إصداراً جديداً برقم تصاعدي (V2, V3...).
   - تُمنع أي عمليات تعديل (`write`) أو حذف (`unlink`) مباشرة على الإصدارات المستخدمة برفع `UserError`.

2. **لقطة التسعير المطبقة في الفاتورة (`utility.bill.pricing.snapshot`)**:
   - نموذج مالي غير قابل للتعديل داخل `utility_billing` يُسجل عند احتساب الفاتورة `sale.order`.
   - يربط `sale_order_id`, `reading_id`, `customer_id`, `meter_id`, `contract_template_id`, `contract_template_version_id`, `version_code`, `billing_consumption`.
   - يحفظ تفاصيل المبالغ الناتجة: `amount_energy`, `amount_service`, `amount_local_fee`, `amount_discount`, `amount_private_transformer_fee`, `pre_adjustment_total`, `min_max_adjustment_amount`, `calculated_total`.
   - يوثق مخرجات معادلات الدعم والخصم والجهة الداعمة.

3. **أدلة الشرائح المطبقة (`utility.bill.pricing.block`)**:
   - أسطر تفصيلية مرتبطة بلقطة التسعير توثق بالضبط كل شريحة تم تطبيقها (`block_name`, `from_kwh`, `to_kwh`, `quantity`, `price_per_kwh`, `amount`, `is_discount`).

4. **سلسلة التدقيق التاريخي الكاملة (Authoritative Audit Chain)**:
   ```text
   Customer → Contract Template → Contract Version → Reading → Reading Snapshot (Component) → Pricing Snapshot (with Applied Blocks) → Sale Order → Accounting Invoice → Payment & Reconciliation
   ```

### 7.1 معالج استنساخ قوالب العقود (`utility.contract.template.clone.wizard`)

يُتيح المعالج للمستخدمين المخولين (مدراء الفوترة والنظام) إنشاء قالب عقد جديد ومستقل بالكامل اعتماداً على تهيئة قالب موجود:

- **تدفق العمل (Business Flow)**:
  ```text
  Existing Contract Template
          ↓
  Clone Wizard (`utility.contract.template.clone.wizard`)
          ↓
  New Independent Contract Template
          ↓
  New Contract Version 1 (V1)
          ↓
  Optional Future Customer Assignment
  ```
- **ما يتم نسخه (Copied Configuration)**:
  - الأسعار الأساسية والحدود (`pricing_mode`, `price_per_kwh`, `service_charge`, `min_charge`, `max_charge`).
  - بنود العقد (`utility.contract.template.line`) كنسخ جديدة مستقلة ترتبط بالمنتجات والمعادلات المشتركة دون تكرار سجلات الماستر داتا.
  - شرائح التسعير (`utility.contract.template.block`) وشرائح الخصم كنسخ جديدة تتبع القالب الجديد حصراً.
  - الرسوم المحلية والدعم وإعدادات سير العمل والتكرار.
  - النطاق الجغرافي والمناطق المسموح بها مع إمكانية التجاوز والتعديل أثناء الاستنساخ.
- **ما يُمنع نسخه نهائياً (Strictly Isolated)**:
  - **سجل التاريخ (`history_ids`)**: لا يُنقل ويبدأ القالب الجديد بسجله الخاص.
  - **الإصدارات التاريخية (`version_ids`)**: يبدأ القالب الجديد حصراً بإصداره الأول (V1) ولا يرث إصدارات القالب المصدر السابقة.
  - **الفواتير، القراءات، لقطات التسعير، وتعيينات المشتركين**: استنساخ القالب لا يُعيّن المشتركين تلقائياً ولا يستنسخ أي حركات مالية سابقة.
- **تتبع الاستنساخ (Clone Provenance)**:
  - توثيق المصدر عبر حقول إرشادية غير ملزمة (`cloned_from_template_id`, `cloned_at`, `cloned_by`).

### 7.2 الخصومات بحسب الشرائح والجهة الداعمة (Block Discounts & Sponsor Fund)

يدعم محرك الفوترة منظومة خصومات ودعم مرنة ترتبط بشرائح الاستهلاك والجهات الراعية:

- **الخصم بحسب الشرائح (`utility.discount.block`)**:
  - إمكانية تعريف شرائح خصم متعددة لكل نوع مشترك (مثلاً الشريحة الأولى 0-100 kWh بخصم محدد، والشريحة الثانية 100-200 kWh).
  - احتساب مبلغ الخصم بدقة لكل شريحة وتوثيقه في أسطر لقطة التسعير (`utility.bill.pricing.block`) مع ضبط علامة `is_discount = True`.
  - التحقق الصارم من عدم تجاوز وحدات الخصم لاستهلاك الشريحة الفعلي.

- **تكامل الجهة الداعمة (`sponsor_id`)**:
  - ربط سجل الجهة الداعمة بشريك مستقل في النظام `res.partner` (المعرف القياسي: `partner_sponsor_fund` - باسم **"الصندوق"**).
  - تحديد الجهة الراعية في تصنيفات المشتركين المستحقين للدعم (`sub_category_public`، `sub_public_tenant`).
  - توثيق مبالغ الدعم في الفاتورة ولقطة التسعير بما يتيح تسوية مطالبات الدعم مع الجهة الراعية محاسبياً بصورة منفصلة.

---

## 8. Idempotency & Concurrency

### Constraints
- one active bill per account+period.
- unique bill+reading component.
- no duplicate active reading bill.

### Locks
- billing target/account/period.
- selected replacement closing readings.

### Retry
Retry لنفس business key يعيد نفس النتيجة أو يرفض duplicate بصورة deterministically.

---

## 9. Batch Billing at Scale

Coordinator يقسم الحسابات إلى micro-batches:

```text
500–1000 accounts starting benchmark
```

كل Unit:
- transaction مستقلة.
- deterministic ordering.
- error isolation.
- progress metrics.

الرقم النهائي يثبت بالـLoad Test.

---

## 10. Billing Error Taxonomy

- missing tariff.
- missing periodic anchor.
- duplicate active bill.
- invalid meter segment.
- negative consumption.
- incomplete block coverage.
- missing accounting configuration.
- posting failure.
- stale/concurrent state.

Business errors لا تعاد تلقائيًا بلا تعديل Configuration/Data.

Transient errors يمكن Retry.

---

## 11. Corrections

بعد Posting:
- لا تعديل order financial history مباشرة.
- لا تعديل billed reading.
- لا تعديل components.

التصحيح:
```text
Settlement
 → Delta Consumption
 → Reprice using approved correction policy
 → Debit Invoice / Credit Note
```

---

## 12. Golden Regression Matrix

- normal periodic.
- zero replacement.
- one replacement.
- multiple replacement.
- opening=0.
- flat.
- tier boundaries.
- progressive boundaries.
- discount blocks.
- min/max charge.
- concurrent billing.
- duplicate retry.
- accounting posting.
- correction after billing.

---

## 13. Billing Definition of Done

- Golden numeric results ثابتة.
- Invoice amount = component/tariff result.
- Components reconstruct bill.
- No duplicate under concurrency.
- Posted accounting document links back to Utility Bill.
- Historical tariff interpretation survives future configuration changes.

## V3.3 Current Implementation Synchronization

**CURRENT V1:** `utility_core.models.utility_reading` is operational truth. The Billing extension inherits `utility.reading` and owns commercial fields/behavior: `is_billable`, `billing_anchor_id`, `billing_component_ids`, `included_sale_order_id`, `carried_consumption`, `billing_consumption`, and `billing_error`. Core exposes hooks such as `_requires_billing_review()` and does not dynamically detect Billing installation.

- **Automated Approval-to-Invoice Pipeline:** Supervisor approval of billable readings (`is_billable = True`) immediately transitions the reading from `under_review` → `queued` → `billed`, auto-resolving the active reading period `date.range`, creating and confirming the `sale.order` bill (`state = 'sale'`), and creating and posting the customer invoice (`account.move` with `state = 'posted'`).
- **Network Readings (Feeders & Transformers):** Public network readings are non-billable (`is_billable = False`) and remain in `state = 'approved'` without generating invoices.
- **Image Review Gate:** Approvals require `image_state == 'clear'`. Dedicated review services and OWL console components provide in-row evaluation actions (`clear`, `not_clear`, `not_same`, `loss_read`) and lightbox inspection.
- **Approved Workspace Scope:** The review console "معتمدة" workspace and KPI cards aggregate `['approved', 'queued', 'billed']`, ensuring all approved technical and billed commercial readings remain visible to supervisors and auditors.
- **Contract Template Versioning & Blocks:** `utility.contract.template.version` provides immutable contract versioning. Modification of billed templates automatically triggers version increments (V1 → V2). Dynamic block replacement supports `skip_tier_validation` context guard to prevent false boundary errors during reconfiguration.
- **Pricing Snapshot Evidence:** Each confirmed `sale.order` bill generates an immutable `utility.bill.pricing.snapshot` and associated `utility.bill.pricing.block` records, locking calculated components (energy, service fees, discounts, local fees) against future tariff changes.

The current reading state compatibility is `draft`, `under_review`, `approved`, `queued`, `billed`, and `error`; a separate `billing_state` is **TARGET / FUTURE OPTIONAL DESIGN** only.

The Bill is `sale.order`, not `account.move`. The current Bill UI links to Accounting Invoices and Payments through smart buttons, then to explicit allocation/reconciliation. Historical evidence is corrected through controlled adjustment/reversal artifacts.
