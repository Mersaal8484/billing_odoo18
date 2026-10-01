# UTILITY ERP MASTER ARCHITECTURE V2
## المعمارية الرئيسية المستهدفة لمنصة إدارة وفوترة وتشغيل الكهرباء
### Domain + Application + Data + Integration + Scale + Production Architecture

**Document Type:** Master Target Architecture / Production Architecture
**Platform:** Odoo 16 Community
**Baseline Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Architecture Baseline SHA:** `13df4c5263abe2e211fc12dc0c3c62f86e87a048`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Architecture Status:** Current V1 + Target V2 Architecture
**Version:** 3.2
**Last Verified Date:** 2026-08-24

**Architecture Precedence:** هذه الوثيقة تحفظ قرارات Target V2، لكنها لا تلغي دليل التنفيذ الحالي أو قرارًا معماريًا أحدث مقبولًا.
**Source Synthesis:** تم دمج المعمارية الوظيفية والتقنية السابقة مع مراجعة السعة والتنفيذ الخاصة بهدف يصل إلى **1,000,000 مشترك**.
**Current Runtime vs Target Runtime:** يجب التمييز بين ما يعمل حاليًا داخل Odoo وما هو Target Production Architecture؛ وجود Target مستقبلي لا يفرض إدخال بنيته التحتية قبل اجتياز Gates التنفيذية.

---

## Current Implementation Baseline

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Branch:** `development`
**Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Documentation Version:** `3.2`
**Documentation Status:** Current V1 + Target V2

**Architecture baseline:** القرارات المعمارية الأصلية المثبتة في وثائق V2، ومرجعها التاريخي منفصل في `Architecture Baseline SHA`.
**Implementation baseline:** كود فرع `development` عند `Implementation SHA` أعلاه. أي hardening لاحق لا يُفترض أنه غائب بسبب SHA قديم في وثائق سابقة.

### Mandatory classification

- **CURRENT V1:** سلسلة التشغيل الحالية هي `date_range → utility_core → utility_inventory → utility_operations → utility_billing`. Odoo/PostgreSQL، `account.move`، وStandard Odoo Stock هي مصادر الحقيقة الحالية. `utility_prepaid` خارج V1.
- **TARGET V2:** PgBouncer، التوسع الأفقي، backend وسائط قابل للتوسع، partition planning، micro-batch billing على نطاق كبير، وHybrid/Temporal orchestration عند الحاجة.
- **DEFERRED:** runtime/CI proof، load benchmarking، rollout فعلي للتقسيم، وتحسين `stock.quant` N+1 حتى يثبت profiling أثرًا إنتاجيًا.
- **OUT OF SCOPE:** إدخال customer wallet أو دفتر مالي/مخزون موازٍ، وضم `utility_prepaid` إلى Release V1.

### Current V1 workflow corrections

- `utility.reading` محفوظ بحالات `draft → under_review → approved → queued → billed` مع `error` كحالة فعلية؛ لا يوجد `billing_state` منفصل كتنفيذ حالي.
- Core يملك operational reading truth، وBilling يرث `utility.reading` ويملك الحقول والسلوك التجاري: `is_billable`, `billing_anchor_id`, `billing_component_ids`, `included_sale_order_id`, `carried_consumption`, `billing_consumption`, `billing_error`.
- Reading Batch الحالي يستخدم `uploaded → processing → done / partial / error` مع Cron bounded processing و`FOR UPDATE NOWAIT` وSQLSTATE `55P03` handling، ويعرض `image_count`, `progress_percent`, active/attention filters.
- Bill هو تمثيل تجاري لـ`sale.order`، بينما Accounting Invoice هو `account.move`؛ توجد smart navigation من Bill إلى الفواتير المحاسبية والدفعات.
- Write-off الحالي هو `draft → approved → applied`، وله invariant: **One write-off → at most one generated Credit Note**.
- Security CURRENT V1 يثبت Role-Based groups، `assigned_region_ids`/`assigned_route_ids`، وشركة كحد أعلى مع قواعد Region/Route محددة؛ أما unified `GLOBAL/RESTRICTED` Region/Branch isolation الشامل فهو **TARGET V1 SECURITY HARDENING**.

### Current V1 operational diagrams

```text
Reading → Bill (sale.order) → Accounting Invoice (account.move)
                           → Payment (account.payment)
                           → Allocation/Reconciliation → Settlement

Physical stock/serial → installation → operational meter → replacement/removal

Upload → Confirm → Processing → Done / Partial / Error
```

The current operational lifecycles are also explicit: Installation `draft → installed → verified` with failure paths; Work Order `draft → assigned → in_progress → completed → verified` with terminal cancellation; Inspection `scheduled → completed/cancelled`; Alarm `open → acknowledged → investigating → resolved/dismissed`.

---

# 0. V2 Executive Architecture Decisions

هذه النسخة تثبت القرارات التالية بصورة نهائية ما لم يصدر Architecture Change Request رسمي:

1. **Odoo 16 Community يبقى System of Record** للـUtility Domain والمحاسبة.
2. **`utility.bill.reading.component` يبقى Immutable Billing Segment Snapshot** ولا يعاد تصميمه.
3. **Reading + Review مرحلة تشغيلية واحدة**، وPayment Period فترة مستقلة مرتبطة بنفس `cycle_key`.
4. **الاستبدال لا يولد فاتورة منفصلة لكل عداد**؛ جميع `replacement_closing` segments تدخل مع الـPeriodic Anchor في فاتورة واحدة للحساب/الفترة.
5. **`utility.media.asset` هو Canonical Media Model**.
6. **التخزين الحالي عبر Attachment هو Compatibility Backend فقط**؛ Target Production هو Organized Filesystem خارج Odoo مع تسليم NGINX، خلف Media Adapter.
7. **Media storage API يبقى Storage-Agnostic**.
8. **Payment reconciliation يجب أن يكون Targeted/Explicit**؛ يمنع Partner-wide automatic reconciliation.
9. **Hybrid Workflow Architecture**:
   - Odoo/local execution للمعاملات القصيرة والذرية.
   - Temporal للعمليات الطويلة التي تنتظر بشرًا أو تمتد زمنيًا.
   - Temporal لتنسيق Reading Batch orchestration عند الحجم الكبير.
   - لا Workflow مستقل لكل فاتورة أو إشعار بسيط.
10. **PgBouncer جزء من Target Production Infrastructure** عند التشغيل متعدد الـworkers والعقد.
11. **Redis يستخدم للـRate Limiting والـCache التشغيلي المحدد**، وليس كمصدر حقيقة.
12. **Partitioning يجب أن يدخل في تصميم قواعد البيانات قبل الوصول إلى حجم عشرات الملايين من القراءات**، وليس كحل إسعافي بعد التضخم.
13. **Billing at Scale يعمل بMicro-Batches مستقلة** مع Idempotency وPartial Failure، وليس Transaction واحدة لمليون حساب.
14. **`utility.reading.batch.line` Staging دائم Crash-Safe** ويجب عدم استبداله بجدول مؤقت.
15. **Partial Failure هو السلوك المطلوب لدفعات القراءات**؛ خطأ عنصر لا يسقط الدفعة كاملة.
16. **No Customer Wallet** في Utility Postpaid.
17. **No Taxes** في Utility Billing Flow الحالي.
18. **Single operational institution**؛ Geographic/Operational Scope هو وسيلة التقسيم الرئيسية وليس Business Multi-Company.
19. **Walking Skeleton يسبق نشر البنية التحتية الثقيلة** لإثبات المسار End-to-End قبل التوسع.
20. **Production Readiness تقاس بالـGates والاختبارات والأرقام الفعلية، لا بمجرد نجاح Demo.**

---

---

# 1. Purpose

تهدف هذه الوثيقة إلى تثبيت **المعمارية المستهدفة** لنظام Utility ERP بعد مراجعة شاملة للـDomain والـRepository والمناقشات المتعلقة بالفترات، القراءات، Media، الفوترة، المحاسبة، التحصيل، الاستبدال، العمليات، المخزون، الأمن والتكاملات.

الهدف ليس إعادة بناء النظام من الصفر، وإنما:

1. الحفاظ على المكونات التي أثبتت صحتها.
2. تثبيت Sources of Truth لكل Domain.
3. إزالة تكرار Business Logic والمسارات المتعارضة.
4. حماية التاريخ المالي والتشغيلي من التعديل المباشر.
5. فصل الـDomain عن العرض والتخزين والتكاملات الخارجية.
6. جعل النظام قابلًا للتدقيق والاختبار والهجرة للإنتاج.
7. توفير مرجع معماري يمكن اشتقاق SRS وAPI Specification وSecurity Matrix وUAT منه.

---

# 2. Architectural Principles

## 2.1 Odoo First

Odoo 16 Community هو **System of Record** للعمليات الأساسية:

- العملاء والحسابات.
- العدادات.
- الشبكة الجغرافية والفنية.
- الفترات.
- القراءات.
- الفوترة.
- المحاسبة.
- التحصيل.
- العمليات الميدانية.
- المخزون التسلسلي.
- التدقيق.

لا يتم إدخال Kafka أو Microservices كشرط عام. أما Temporal فيستخدم ضمن **Hybrid Workflow Architecture** وبنطاق محدد: العمليات الميدانية الطويلة وReading Batch orchestration عند الحاجة، وليس كل معاملة قصيرة.

## 2.2 Single Operational Institution

التشغيل الحالي يستهدف مؤسسة واحدة. تبقى `company_id` وآليات Odoo القياسية للتوافق التقني، لكن التقسيم التشغيلي والأمني الأساسي يعتمد على المنطقة والبنية الفنية، وليس على Multi-Company كحد أعمال.

```text
Region
  └── Area
       └── Zone
            └── Route
```

والبنية الفنية:

```text
Substation
  └── Feeder
       └── Transformer
            └── Meter
```

## 2.3 No Customer Wallet

لا توجد Customer Wallet في Utility ERP. التحصيل يتم عبر Accounting Payments وPayment Providers ومطابقة ذمم صريحة.

```text
Customer Receivable
        ↓
Posted Invoice
        ↓
Payment
        ↓
Explicit Allocation/Reconciliation
```

## 2.4 No Taxes in Current Utility Billing

دورة الكهرباء الحالية بدون ضرائب، وبالتالي بنود Utility Billing تبقى بدون Taxes ما لم يظهر Requirement رسمي مستقل لاحقًا.

---

# 3. Target Module Landscape

الوحدات الأساسية الحالية:

```text
utility_core
utility_billing
utility_operations
utility_inventory
utility_prepaid
```

قدرات Portal وIntegration تبقى ضمن الوحدات الحالية، ولا يتم إنشاء Module جديد لمجرد فصل Feature صغير.

`utility_prepaid` موجود، لكنه ليس ضمن مسار Production Hardening الحالي للـPostpaid؛ يتم تجميده أثناء تثبيت Core/Billing/Operations/Inventory.

---

# 4. Module Responsibilities

## 4.1 utility_core — Domain Foundation

مسؤول عن:

- Geographic hierarchy.
- Network hierarchy.
- Utility Customer/Account.
- Meter master data.
- Subscriber categories/types.
- Contract templates and tariffs.
- Formula engine.
- Date Range / cycle foundation.
- Canonical meter replacement domain.
- Media Asset abstraction.
- Integration provider registry.
- Notifications.
- Workflow command/outbox foundation.
- Migration mappings.
- User geographic scope.
- Shared security/services/adapters.

لا يجب أن يصبح Core مكانًا لتنفيذ تحصيل الفواتير أو Stock execution أو POS prepaid vending.

## 4.2 utility_billing — Postpaid Revenue Engine

مسؤول عن:

- Reading batches.
- Reading review workspace.
- VEE/exceptions.
- Periodic billing.
- `utility.bill.reading.component`.
- Tariff execution.
- Sale Order utility bills.
- Accounting invoice generation/posting.
- Payment registration/allocation.
- Payment gateway transactions.
- Penalties.
- Write-offs.
- Financial settlements.
- Deposits.
- Statements/reports.
- Customer billing portal capabilities.

## 4.3 utility_operations — Field Operations Orchestration

مسؤول عن:

- Service orders.
- Work orders.
- Assignment/scheduling.
- Installation/removal.
- Inspection/test.
- Disconnection/reconnection.
- Tamper/maintenance/alarm flows.
- Field evidence.
- Orchestration حول Meter Replacement.

**قاعدة:** لا يعيد `utility_operations` تنفيذ Domain Logic للاستبدال؛ المصدر الرسمي هو `utility.meter.replacement` في Core.

## 4.4 utility_inventory — Physical Meter Logistics

المصدر الفيزيائي للعدادات:

```text
stock.lot = physical serialized item
utility.meter = logical utility device
```

المسار المستهدف:

```text
Supplier
  ↓
Receipt
  ↓
Central/Regional Warehouse
  ↓
Technician Custody
  ↓
Installed
  ↓
Removed
  ↓
Quarantine / Repair / Return / Scrap
```

---

# 5. Layered Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ Presentation                                                 │
│ Odoo Views | OWL Review | Portal | Reports | API            │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Application Services                                         │
│ Billing | Media | Workflow | Payment Allocation | Operations│
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Domain                                                       │
│ Account | Meter | Reading | Period | Bill | Replacement     │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Infrastructure Adapters                                      │
│ Accounting | Stock | Media Adapter | HTTP | Workflow Adapter│
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Persistence                                                  │
│ PostgreSQL | Filestore/Attachment | Future Shared FS            │
└──────────────────────────────────────────────────────────────┘
```

---

# 6. Customer & Account Domain

```text
res.partner
    └── identity/contact

utility.customer
    └── electricity account / utility contract account
```

`utility.customer` هو مركز التشغيل والفوترة ويرتبط بـ:

```text
Partner
Contract Template
Subscriber Category/Type
Region/Area/Zone
Route
Transformer/Feeder
Current Meter
Readings
Bills
Payments
Operations
```

الحسابات التجميعية يمكن أن تجمع Child Accounts إداريًا وماليًا، مع بقاء كل Child Account مستقلًا في القراءة والعداد والفاتورة.

---

# 7. Meter Architecture

`utility.meter` يمثل الجهاز منطقيًا ويدعم:

```text
not_connected
subscriber
private_transformer
transformer
feeder
```

في الوضع النهائي:

```text
utility.meter 1 ───── 1 stock.lot
```

مع قيود تمنع:

- نفس Serial/lot لعدة عدادات.
- تركيب عداد غير متوفر مخزنيًا.
- تركيب عداد في عهدة مستخدم آخر دون Transfer.
- تناقض حالة Utility Meter مع Stock Location.

---

# 8. Period & Cycle Architecture

## 8.1 Reading + Review = One Operational Phase

لا توجد Review Period مستقلة.

```text
Reading Period
=
Consumption Bounds
+
Reading Intake Window
+
VEE/Review
```

## 8.2 Payment Period Is Independent

كل دورة تحتوي:

```text
Cycle
├── Reading & Review Period
└── Payment Period
```

ويربطهما `cycle_key`.

مثال:

```text
SEMI-2026-08-H1
READ-SEMI-2026-08-H1
PAY-SEMI-2026-08-H1
```

## 8.3 State Machines

### Reading

```text
planned → open → closing → closed → locked
```

### Payment

```text
planned → open → closing → reconciled → locked
```

`reopened` ليست State. إعادة الفتح Action مدقق:

```text
closed/reconciled/closing
        ↓
action_reopen_period(reason)
        ↓
open
```

`locked` لا يفتح في التشغيل الطبيعي.

---

# 9. Period Generation

التوليد الرسمي يتم عبر `utility.period.generator` و`_create_cycle_pair()` في Transaction واحدة.

```text
Monthly:      MONTHLY-YYYY-MM
Semi Monthly: SEMI-YYYY-MM-H1
              SEMI-YYYY-MM-H2
```

H1 = 1–15، وH2 = 16–نهاية الشهر.

Offsets الافتراضية نسبة إلى `consumption_end`:

```text
reading_start_offset_days = -2
reading_end_offset_days   = +3
payment_start_offset_days = +1
payment_end_offset_days   = +13
```

التواريخ المحلية تتحول إلى UTC بصورة Timezone-aware.

---

# 10. Geographic Scope

مصدر الحقيقة لنطاق الفترة:

### Reading Period

```text
ALL active root regions matching billing cadence
```

لا يسمح لـCaller بتمرير Partial Region Set ليغيّر النطاق الرسمي بصمت.

### Payment Period

```text
payment.region_ids = exact snapshot of reading.region_ids
```

قبل `planned → open` يتم Final Scope Sync، وبعدها تصبح هذه الحقول محمية تاريخيًا:

```text
cycle_key
region_ids
billing_cadence
period_role
reading_period_id
```

---

# 11. Reading Architecture

كل قياس فيزيائي هو `utility.reading`.

الدلالات الأساسية:

```text
periodic
replacement_closing
opening
```

- `periodic` هي Billing Anchor.
- `replacement_closing` إغلاق العداد القديم.
- `opening` افتتاح العداد الجديد.

Opening consumption = 0 **حالة صحيحة** وليست Zero Consumption anomaly.

---

# 12. Meter Replacement Architecture

الـCanonical Engine:

```text
utility.meter.replacement
```

ويخدم Subscriber / Feeder / Transformer.

```text
Replacement
  ├── validate old meter
  ├── create approved replacement_closing
  ├── detach old meter
  ├── attach new meter
  ├── create approved opening
  ├── meter logs
  └── done
```

## Billing Impact

الـclosing لا تنشئ Bill منفصلة. يتم تجميع كل المقاطع حتى Periodic Anchor القادمة.

```text
Previous periodic = 1000
Closing A = 1300  → 300
B opening 20 / closing 170 → 150
C opening 5 / periodic 105 → 100

ONE Bill = 550
Components = 300 + 150 + 100
```

---

# 13. Billing Engine — Frozen Core

`utility.bill.reading.component` جزء معماري **Frozen**.

يمثل Historical Snapshot لكل Segment:

```text
sale_order
reading
account
meter
reading_purpose
period_start / period_end
previous_reading
current_reading
meter_multiplier
consumption
company
```

القاعدة:

```text
Utility Account + Reading Period = ONE Active Utility Bill
```

مع إمكانية وجود عدة Reading Components داخل الفاتورة الواحدة.

---

# 14. Tariff Architecture

المصدر المرجعي:

```text
utility.contract.template
```

يدعم:

```text
flat
 tier
block
seasonal
tou
```

- **Flat:** سعر موحد.
- **Tier:** اختيار شريحة واحدة حسب إجمالي الاستهلاك وتطبيق السعر على كامل الاستهلاك.
- **Block:** توزيع الاستهلاك تدريجيًا بين الشرائح.

كما يدعم:

```text
Energy
Fixed Fee
Service Charge
Local Fees
Discount
Minimum Charge
Maximum Charge
Sponsor Discount
Formula-based Quantity
```

---

# 15. Tariff Historical Snapshot

الفاتورة المنشورة يجب أن تبقى قابلة للتفسير حتى بعد تعديل التعرفة.

عند Billing تحفظ Snapshot تتضمن على الأقل:

```text
template_id
template_version/hash
pricing_mode
effective dates
applied blocks
service charge
local fees
discount policy
formula version/hash
```

لا تعاد حساب فاتورة تاريخية اعتمادًا على Config الحالية.

---

# 16. Formula Governance

`utility.formula` يبقى Controlled Calculation Engine.

القواعد:

- لا ORM env.
- لا Imports/System access.
- Code size limit.
- Validation before save.
- Version/hash لكل Formula مالية.
- Approval + test cases.
- أي Formula مستخدمة تاريخيًا لا تعدل؛ يتم إنشاء Version جديدة.

---

# 17. Accounting Architecture

## Utility Bill

```text
Reading
  ↓
Utility Sale Order
  ↓
Accounting Customer Invoice
  ↓
Posted Receivable
```

## Payment

```text
Payment Request
  ↓
Account Payment
  ↓
Posted Payment Move
  ↓
Explicit Allocation
  ↓
Target Invoice Receivable
```

---

# 18. Payment Allocation — Mandatory Rule

ممنوع:

```text
Reconcile all partner unreconciled receivable lines
```

المطلوب:

```text
Payment
  └── Allocation
       ├── Invoice A = X
       └── Invoice B = Y
```

وفي التزامن:

```text
Outstanding = 1000
Payment A = 600
Payment B = 600
```

يجب Lock/Serialize الهدف المالي بحيث النتيجة لا تتجاوز 1000.

---

# 19. Payment Gateway

```text
Portal/API
  ↓
Payment Intent
  ↓
utility.payment.gateway.transaction
  ↓
Provider
  ↓
Pending
  ↓
Webhook
  ↓
Lock Transaction
  ↓
Lock Bill
  ↓
Post Payment
  ↓
Explicit Reconciliation
  ↓
Done
```

Webhooks تستهدف:

```text
HMAC
Timestamp
Nonce
Replay Protection
Provider Reference Uniqueness
Constant-time Compare
```

---

# 20. Deposits

التأمين Liability وليس Customer Receivable عاديًا.

```text
Receive:
Dr Bank/Cash
Cr Customer Deposit Liability

Release:
Dr Customer Deposit Liability
Cr Bank/Cash

Forfeit:
Dr Customer Deposit Liability
Cr Fine/Other Revenue
```

---

# 21. Penalties & Due Date

Penalty Policy تدعم:

```text
Grace Period
Frequency
Percentage/Fixed
Maximum Cap
Eligibility
Waiver
Reversal
Dispute Hold
```

المرجع الرسمي للتأخير يجب أن يكون Accounting Due Date / Payment Policy، وليس `date_order` وحده.

```text
Due Date
+ Grace Days
+ Outstanding Amount
+ Account Status
+ Dispute Hold
→ Penalty/Disconnection Eligibility
```

---

# 22. Financial Corrections

بالنسبة للـgeneric correction documents غير المرتبطة مباشرة بنموذج `utility.writeoff`، يمكن أن يكون المسار المستهدف:

```text
Draft → Review → Approve → Post → Reverse if required
```

أما **CURRENT V1 `utility.writeoff`** فله lifecycle مختلف ومحدد:

```text
draft → approved → applied → Credit Note
           └──────→ draft    (قبل إنشاء الأثر المالي فقط)
```

بعد `applied` يمنع `draft` و`approved` وإعادة التطبيق. يحافظ `FOR UPDATE` و`move_id` المرتبط على invariant: **One write-off → at most one generated Credit Note**.

ويحفظ كل مستند:

```text
reason code
reason text
source document
approver
accounting move
period/date
user
```

---

# 23. Reading Settlement — Historical Integrity

القراءة المفوترة **Immutable**.

ممنوع تعديل `reading_value` الأصلية بعد صدور فاتورة منها.

```text
Original Reading
    immutable
       ↓
Original Bill Component
    immutable
       ↓
Reading Settlement
       ↓
Corrected Value
       ↓
Delta Consumption
       ↓
Debit Invoice / Credit Note
```

---

# 24. Media Architecture

## 24.1 Canonical Model

```text
utility.media.asset
```

هو مصدر الحقيقة للوسائط، و`ir.attachment` Backend حالي فقط.

## 24.2 Variants

```text
original
review
thumbnail
```

## 24.3 Display

```text
Reading
  ↓
image_asset_id
  ↓
asset_uuid
  ↓
/utility/media/<uuid>/<variant>
  ↓
Media Service
  ↓
Media Adapter
```

الواجهة لا تعتمد على computed Binary field كمسار العرض الرئيسي.

## 24.4 Storage Abstraction

```text
Media Service
  ├── Attachment Adapter [current / compatibility]
  └── Filesystem Adapter [target production]
         └── Organized filesystem outside Odoo
                └── NGINX / X-Accel-Redirect delivery
```

### Target Production Storage Rule

الملف النهائي لا يجب أن يبقى Business Payload داخل PostgreSQL أو يتطلب من Odoo Workers بث الملفات الكبيرة بأنفسهم.

المسار المستهدف:

```text
Upload Gateway
   ↓
Media Staging
   ↓
Validate / Rotate / Generate Variants
   ↓
Organized Filesystem
   ↓
utility.media.asset metadata
   ↓
NGINX delivers bytes
```

ويحافظ Media Adapter على استقلال الـDomain عن مسار التخزين الفعلي.

## 24.5 Raw Bytes Contract

العقد الداخلي:

```text
store_media(raw_bytes, ...)
```

التطبيع Base64 يحدث عند Boundary فقط.

## 24.6 Revision

استبدال الصورة ينشئ Revision جديدة ولا يمسح Evidence التاريخية.

## 24.7 Legacy Repair

أداة Repair تصنف:

```text
VALID
DOUBLE_BASE64
INVALID_IMAGE
MISSING_VARIANT
ORPHAN
BROKEN_ATTACHMENT
```

ثم تصلح ما يمكن إصلاحه بطريقة مدققة.

---

# 25. Reading Review / VEE

واجهة المراجعة OWL Workspace وتحتوي:

```text
Period/Region/Batch filters
Reading Queue
Exceptions
Account context
Review image
Previous/Next prefetch
Approve/Reject/Correct
Replacement context
Statistics
```

Media performance:

```text
Thumbnail → queue/list
Review    → reviewer
Original  → explicit only
```

لا يتم auto-prefetch للـOriginal.

تصنيف Exceptions المقترح:

```text
MISSING_READING
MISSING_IMAGE
INVALID_IMAGE
OUT_OF_WINDOW
NEGATIVE_CONSUMPTION
ZERO_CONSUMPTION
HIGH_VARIANCE
DUPLICATE_READING
METER_MISMATCH
PERIOD_MISMATCH
AMI_DUPLICATE
BILLING_ERROR
```

---

# 26. Operations Architecture

`utility.service.order` هو رأس العملية الميدانية.

```text
Request
  ↓
Approval
  ↓
Assignment
  ↓
Schedule
  ↓
Reserve Materials
  ↓
Field Execution
  ↓
Evidence
  ↓
Validation
  ↓
Stock Completion
  ↓
Domain Update
  ↓
Financial Charge if applicable
  ↓
Completed
```

Service types الأساسية:

```text
new_connection
meter_replacement
meter_removal
meter_test
inspection
disconnection
reconnection
tamper_investigation
site_survey
maintenance
other
```

---

# 27. Inventory & Custody Architecture

Business states المطلوبة للعداد الفيزيائي:

```text
Available
Reserved
In Technician Custody
Installed
Removed
Quarantine
Under Test
Repair
Returned
Scrapped
```

يتم اشتقاقها قدر الإمكان من Odoo Stock بدل إنشاء Quant Engine موازي.

Technician Custody تمثل Location منطقية:

```text
Warehouse → Technician Custody → Customer Installation
```

وعند الإزالة:

```text
Customer → Removed/Quarantine → Repair/Warehouse/Scrap
```

يجب توحيد Stock actions في Service واحدة مثل:

```text
issue_meter()
move_to_custody()
install_meter()
remove_meter()
return_meter()
move_to_quarantine()
scrap_meter()
```

ولا يتكرر `_create_stock_picking()` في Models متعددة.

---

# 28. Security Architecture

الأدوار المرجعية:

```text
Readonly
Cashier
Collector
Technician
Field Inspector
Supervisor
Billing Manager
Revenue Manager
Auditor
Administrator
```

مصدر الحقيقة الجغرافي:

```text
res.users.assigned_region_ids
```

Admin فقط unrestricted.

```text
non-admin + no assigned regions → deny geographically scoped records
```

أي Default يجب أن يكون **Default Deny** لا Full Access.

---

# 29. Unified Authorization Service

بدل تكرار Domains في Controllers:

```text
get_user_region_domain()
check_account_access()
check_meter_access()
check_reading_access()
check_media_access()
check_replacement_access()
check_service_order_access()
```

قاعدة API:

```text
sudo() ≠ authorization
```

يمكن استخدام `sudo()` بعد حساب Scope المسموح فقط.

---

# 30. Portal Architecture

Portal Presentation Channel لنفس Business Services.

المستهدف:

```text
Account Overview
Current Balance
Bills
Bill Details
Readings
Consumption History
Payments
Receipts
Service Requests
Disconnection Status
Notifications
Payment Intent
```

Portal User يرى فقط الحسابات المرتبطة بـPartner الخاص به.

---

# 31. Integration Architecture

Provider registry يدعم:

```text
SMS
AMI
Payment Gateway
Mobile Money
Bank Transfer
Direct Debit
```

الـTarget للـOutbound calls:

```text
Business Transaction
  ↓
Durable Outbox
  ↓
Commit
  ↓
Worker/Cron
  ↓
Provider
  ↓
Retry / Backoff
```

---

# 32. Workflow / Outbox

## 32.1 Hybrid Workflow Architecture

يوجد مستويان منفصلان يجب عدم خلطهما:

### Current / Local Runtime

الإعداد الافتراضي الحالي أثناء التطوير والـProduction-Hardening:

```text
utility.workflow_adapter = local
```

ويعتمد على:

```text
utility.workflow.command
```

لحفظ:

```text
command_uuid
idempotency_key
state
attempt_count
max_attempts
scheduled_at
started_at
completed_at
result
error
payload
```

الحالات الأساسية:

```text
pending
processing
executed
failed
```

ويضاف `dead_letter` في Target Reliability Layer عند الحاجة.

### Target Production Workflow Scope

Temporal **ليس محركًا لكل شيء**، بل يستخدم فقط عندما تكون Durability الزمنية ذات قيمة فعلية.

| نوع العملية | التنفيذ المستهدف | القرار |
|---|---|---|
| تركيب/استبدال/فصل/إعادة توصيل/تحقيق تلاعب طويل | Temporal | إلزامي عند نشر Target Scale |
| Reading Batch orchestration / Chunking / Retry | Temporal | مناسب وموصى به للحجم الكبير |
| معالجة صورة واحدة | Local Worker أو Temporal بعد Benchmark | قرار قياسي بعد Walking Skeleton |
| توليد فاتورة Utility واحدة | Odoo transaction مباشرة | لا Temporal per invoice |
| Billing batch coordination | Batch Worker / optional Temporal orchestration | Coordination فقط، لا Workflow لكل فاتورة |
| Notification بسيطة | Outbox Worker | لا Temporal |
| Accounting posting القصير | Odoo atomic transaction | لا Temporal |

## 32.2 Architectural Rule

```text
Short atomic business transaction
        → Odoo / PostgreSQL

Long-running human workflow
        → Temporal

High-volume batch coordination
        → Temporal or durable batch orchestrator

External side effect
        → Outbox + retry
```

## 32.3 Idempotency

كل Command أو Workflow أو Batch يجب أن يمتلك Business Idempotency Key ثابتًا.

أمثلة:

```text
READING-BATCH:<batch_uuid>
BILLING:<account_id>:<period_id>
REPLACEMENT:<replacement_uuid>
MEDIA:<asset_uuid>:<revision>
PAYMENT-CALLBACK:<provider>:<provider_reference>
```

---

# 33. Integration Reliability

المطلوب:

```text
Exponential Backoff
Max Attempts
Dead Letter
Manual Retry
Idempotency
Secret Redaction
Timeout Policy
Provider Health
Request/Response Audit
```

---

# 34. AMI Architecture

```text
AMI Provider
  ↓
Authenticated Callback
  ↓
Meter Resolution
  ↓
Period Resolution
  ↓
Idempotency
  ↓
utility.reading
  ↓
VEE
  ↓
Review / Auto-Approval Policy
```

AMI لا يتجاوز Period/Geography/Reading lifecycle.

---

# 35. Notifications

يتم تسجيل Notification Domain أولًا ثم إرسالها إلى Channel Adapter:

```text
Portal
SMS
Future Email/Push
```

فشل SMS لا يلغي Posting مالي ناجح.

---

# 36. Data Immutability Rules

بعد Finalization/Posting تكون Immutable:

```text
Billed Reading
Bill Reading Component
Posted Accounting Move
Payment Allocation
Locked Period Scope
Replacement Closing Reading
Opening Reading
Historical Media Revision
```

التصحيح يتم بواسطة:

```text
Correction Document
Credit Note
Debit Invoice
Settlement
Reversal
New Media Revision
Audited Reopen Action
```

---

# 37. Audit Architecture

كل عملية حساسة يجب أن تجيب:

```text
Who?
When?
What?
Old Value?
New Value?
Why?
Source Document?
Resulting Document?
```

ويشمل ذلك:

```text
Period reopen
Reading correction/rejection
Replacement
Payment/refund
Writeoff
Settlement
Deposit release
Penalty waiver
Disconnection
Media replacement
Configuration changes
```

---

# 38. Performance Architecture

في Dashboards/Statistics:

ممنوع:

```text
search → load all records → filtered → len
```

عندما يكفي:

```text
search_count
read_group
SQL aggregate
```

ولا يتم تحميل Binary لمعرفة `has image`; يستخدم `image_asset_id` و`asset.state`.

Indexes المستهدفة تشمل:

```text
utility_reading:
  (meter_id, state, reading_date)
  (date_range_id, state, reading_purpose)
  (account_id, state, reading_date)
  billing_anchor_id
  included_sale_order_id

utility_media_asset:
  (reading_id, state)
  asset_uuid

utility_reading_batch:
  (date_range_id, state)

sale_order:
  (customer_id, bill_state, date_order)
  date_range_id
  reading_id

account_payment:
  (utility_sale_order_id, state, date)

utility_service_order:
  (customer_id, service_type, state)
```

---

# 39. Background Jobs

كل Cron يجب أن يكون:

```text
batched
ordered deterministically
idempotent
resumable
observable
```

ويشمل:

```text
Billing generation
Penalty calculation
Disconnection detection
Reminders
Media repair
Integration retry
AMI processing
```

---

# 40. Data Migration Architecture

```text
Extract → Stage → Normalize → Validate → Map → Import → Reconcile → Sign-off
```

الترتيب المقترح:

```text
1. Geography
2. Network
3. Partners
4. Utility Accounts
5. Contracts/Tariffs
6. Meters
7. Meter ↔ Stock Serial
8. Historical Readings
9. Last Billed Reading
10. Opening Receivables
11. Open Bills
12. Payments
13. Replacements
14. Media
15. Open Operational Items
```

أي تغيير States/Constraints/Data Contracts يتطلب:

```text
Pre-Migration
Schema Upgrade
Data Transformation
Post-Migration Validation
Recovery Plan
```

---

# 41. Compatibility Fields

حقول Legacy مثل:

```text
billing_period
work_type
attachment_id
meter_image
```

يمكن أن تبقى مؤقتًا فقط كـCompatibility Layer، وليست Source of Truth ولا تبنى Features جديدة عليها.

---

# 42. Testing Architecture

## Unit Tests
لكل Business Rule.

## Transaction Integration

```text
Reading → Bill
Bill → Invoice
Invoice → Payment
Replacement → Components → Bill
Operation → Stock
Deposit → Accounting
```

## Concurrency

```text
Bill generation
Payments
Gateway callbacks
Period generation
Batch ingestion
Replacement
```

## Security

لكل Role:

```text
Allowed Region
Forbidden Region
Allowed Action
Forbidden Action
API
Media
Portal
```

## Golden Billing Tests

```text
Flat
Tier
Block
Discount
Min Charge
Max Charge
Replacement
Multiple Replacement
Zero Opening
```

---


# 42A. Million-Subscriber Processing Architecture

## 42A.1 Reading Batch Staging

`utility.reading.batch.line` يجب أن يبقى Persistent Staging.

```text
Upload
  ↓
Batch Header
  ↓
Persistent Batch Lines
  ↓
Validation / Processing
  ├── success
  ├── business error
  └── technical retry
  ↓
Canonical utility.reading
```

### Required Properties

```text
Crash Safe
Idempotent
Partial Failure
Retryable
Auditable
Chunkable
Measurable Progress
```

لا تستخدم Temporary Table كمصدر وحيد لدفعة لم تكتمل.

## 42A.2 Batch Idempotency

يجب توفر UUID في:

```text
batch
batch line / source reading
reading
media asset
workflow command
```

وتستخدم Database Constraints مع Idempotency معًا.

## 42A.3 Partial Failure

دفعة:

```text
10,000 readings
```

مع 37 خطأ لا تصبح:

```text
FAILED ALL 10,000
```

بل:

```text
9,963 accepted/processed
37 isolated failures
```

مع إمكانية إصلاح وإعادة محاولة الـ37 فقط.

## 42A.4 Billing at Scale

ممنوع:

```text
1,000,000 accounts
→ one ORM loop
→ one huge DB transaction
```

Target:

```text
Period Billing Coordinator
      ↓
Account ID ranges / deterministic chunks
      ↓
500–1000 accounts per unit of work
      ↓
Independent transaction
      ↓
commit
      ↓
next chunk
```

حجم 500–1000 هو Starting Benchmark Range وليس رقمًا مقدسًا؛ يثبت بالـLoad Test.

### Concurrency Guards

حتى مع Workers متوازية:

```text
UNIQUE account+period active bill
+
reading/component constraints
+
row locking where necessary
+
idempotency keys
```

هي خط الدفاع ضد التكرار.

## 42A.5 Billing Failure Model

```text
Batch 1 success
Batch 2 success
Batch 3 partial errors
Batch 4 success
...
```

لا يتم Rollback لمئات آلاف الفواتير بسبب Account واحدة ذات Configuration ناقصة.

يتم إنشاء:

```text
Billing Batch Result
Billing Error Queue
Retryable Errors
Permanent Business Errors
```

## 42A.6 Review Throughput

Review UI مصممة لعمل المراجع على Queue لا Form-by-Form.

Target behavior:

```text
Tree/OWL Queue
Thumbnail list
Review image on selection
Keyboard/rapid actions
Prefetch current ±1 ±2
No original auto-prefetch
No Binary fetch for counters
```

---

# 43. Production Readiness Gates

## Gate A — Data Integrity

```text
No invalid media
No orphan critical records
Period migration completed
No duplicate active bills
Meter/Serial consistency valid
```

## Gate B — Financial Integrity

```text
Targeted payment allocation
No partner-wide auto reconciliation
Corrections via accounting documents
Deposits use liability accounting
Concurrent payment protected
```

## Gate C — Billing Integrity

```text
Golden billing suite passes
Replacement components pass
Duplicate generation is idempotent
Tariff snapshots available
```

## Gate D — Security

```text
Default-deny geography
Admin-only unrestricted
Portal ownership isolation
API authorization
Media authorization
```

## Gate E — Operational Integrity

```text
Install
Remove
Replace
Disconnect
Reconnect
Stock
Custody
```

كلها End-to-End.

---

# 44. Deployment & Scale Architecture

## 44.1 Capacity Planning Baseline — 1,000,000 Subscribers

هذه الأرقام هي **Capacity Planning Assumptions** وليست قياسات Production فعلية حتى يتم إثباتها بالـLoad Test:

| المقياس | Baseline Planning Value |
|---|---:|
| Periodic readings / month | 1,000,000 |
| Realistic peak ingestion | ~50,000–65,000 readings/day |
| New reading images / month | ~1,000,000 |
| Media growth / month | ~90–110 GB |
| Media growth / year without archive | ~1.1–1.3 TB |
| Reading rows / year | ~12,000,000 |
| Reading rows / 5 years | 60M+ |
| Bills / month | up to 1,000,000 |
| Collections / month | up to 1,000,000 |

أكبر حمل داخل Odoo متوقع ليس رفع الصور وحده، بل:

```text
Billing generation
+
account.move
+
account.move.line
+
payment allocation
+
reconciliation
```

في نوافذ الذروة.

## 44.2 Target Production Topology

```text
                           ┌──────────────────────┐
                           │  Load Balancer/Nginx │
                           └──────────┬───────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
                 ▼                                         ▼
      ┌──────────────────────┐                   ┌──────────────────────┐
      │ Odoo 16 Node A       │                   │ Odoo 16 Node B/...   │
      │ Web + ORM Workers    │                   │ Web + ORM Workers    │
      └──────────┬───────────┘                   └──────────┬───────────┘
                 │                                          │
                 └──────────────────┬───────────────────────┘
                                    ▼
                          ┌──────────────────────┐
                          │      PgBouncer       │
                          └──────────┬───────────┘
                                     ▼
                    ┌────────────────────────────────┐
                    │ PostgreSQL — Odoo Primary      │
                    │ Partitioning + tuned indexes   │
                    └───────────────┬────────────────┘
                                    │
                                    └────► Read Replica [target/optional by measured need]

        ┌──────────────────┐          ┌──────────────────────────────┐
        │ Redis            │          │ Temporal Cluster [scoped]    │
        │ Rate Limit/Cache │          │ + separate PostgreSQL        │
        └──────────────────┘          └──────────────┬───────────────┘
                                                    │
                       ┌────────────────────────────┼───────────────────────────┐
                       ▼                            ▼                           ▼
              Reading Workers              Billing Workers           Operations Workers
                       │                            │                           │
                       └───────────────┬────────────┴─────────────┬─────────────┘
                                       │                          │
                                       ▼                          ▼
                             Media Processing Workers       External Providers
                                       │
                                       ▼
                           ┌─────────────────────────┐
                           │ Organized Media Storage │
                           │ SSD/FileSystem target   │
                           └────────────┬────────────┘
                                        ▼
                                      NGINX
```

الفصل أعلاه **منطقي** في البداية؛ لا يعني خادمًا ماديًا مستقلًا لكل Service. يمكن البدء بعدد محدود من الخوادم/VMs/Containers ثم الفصل الفعلي عندما يثبت القياس الحاجة.

## 44.3 PgBouncer

عند وجود:

```text
multiple Odoo nodes
multiple Odoo workers
Reading workers
Billing workers
Operations workers
Temporal workers
```

يصبح Connection Pooling جزءًا من Target Production Baseline.

الهدف:

- منع انفجار PostgreSQL backend connections.
- فصل عدد Application Workers عن عدد DB Connections.
- تثبيت السلوك تحت الذروة.

## 44.4 Redis

Redis ليس Database ولا Source of Truth.

الاستخدامات المستهدفة فقط:

### Rate Limiting

```text
Reading Upload Gateway
AMI endpoints
Selected public/webhook endpoints
```

### Bounded Cache

```text
Tariff lookup
Reference/master data
Reviewer repeated lookups
Short-lived expensive query results
```

لا تخزن فيه:

```text
official balances
bill state truth
reading truth
payment truth
```

## 44.5 PostgreSQL Partitioning

يجب وضع Partitioning Strategy قبل تضخم البيانات.

الأولوية:

```text
utility_reading
utility_reading_batch_line
```

ثم تقييم جداول المحاسبة الكبيرة مثل `account_move_line` وفق قياسات واختبارات Upgrade الفعلية، لأن Partitioning جداول Odoo القياسية يحتاج تصميم Migration واختبار ORM/Upgrade دقيق.

### Recommended Logical Partition Key

للقراءات:

```text
reading_date / billing period month
```

والهدف:

- Partition pruning.
- Faster archival.
- Easier maintenance.
- Controlled index size.
- Predictable retention operations.

## 44.6 Read Replica

الـReplica ليست Source of Truth لقرارات Transactional.

يمكن استخدامها مستقبلاً في:

```text
heavy reporting
historical analytics
supervisor dashboards
non-transactional exports
```

ولا تستخدم أثناء:

```text
billing
payment allocation
reconciliation
replacement commit
period transition
```

## 44.7 Media Delivery

Target:

```text
NGINX serves media
Odoo authorizes media
Storage holds media
```

المسار:

```text
Browser
  ↓
Authorized media URL/controller
  ↓
Access validation
  ↓
X-Accel-Redirect / controlled internal path
  ↓
NGINX
  ↓
Filesystem
```

هذا يمنع استهلاك Odoo Worker لبث Image bytes الكبيرة باستمرار.

## 44.8 Backup / Restore

Production baseline يجب أن يغطي بصورة منفصلة:

```text
PostgreSQL
Odoo Filestore/compatibility attachments
Target Media Filesystem
Temporal PostgreSQL if deployed
Configuration secrets
```

ويجب اختبار Restore فعلي وليس الاكتفاء بوجود Backup job.

---

# 45. Configuration as Data

لا تنشأ حسابات محاسبية أو Journals حساسة أثناء Business Transaction.

تتم Configuration مسبقًا لـ:

```text
Revenue Accounts
Penalty Accounts
Deposit Liability
Writeoff Accounts
Settlement Accounts
Collection Journals
Payment Journals
Stock Locations
Meter Warehouses
Custody Locations
```

عند نقص الإعداد:

```text
BLOCK + Clear Configuration Error
```

---

# 46. Frozen Architecture Decisions

لا يعاد تصميم التالي دون Architecture Change Request:

```text
utility.bill.reading.component = immutable billing segment snapshot
replacement_closing = old meter closing evidence
opening = new meter opening evidence
periodic = billing anchor
multiple replacements + periodic = ONE bill with multiple components
utility.media.asset = canonical media model
Reading + Review = one phase
Payment = paired independent period
Hybrid Workflow = Local/Odoo للمعاملات القصيرة + Temporal للعمليات الطويلة وReading Batch orchestration في Target Scale
No customer wallet
No taxes in current utility billing
```

---

# 47. Deferred / Explicitly Out-of-Scope Architecture

لا يلزم لإغلاق النظام الحالي:

```text
Kafka
Separate Media Microservice
Utility Wallet
Tax Engine
Full Prepaid Redesign
Complex Business Multi-Company Partitioning
Distributed SQL Database
Temporal workflow per individual bill
Temporal workflow per trivial notification
Temporal workflow per image unless benchmark proves value
```

### Temporal Clarification

Temporal نفسه **ليس Deferred بالكامل في V2**؛ هو جزء من Target Architecture ولكن **مقيد بالنطاق** ويأتي بعد Walking Skeleton وقياس فعلي.

---

# 48. End-to-End Postpaid Flow

```text
Utility Account
  ↓
Meter Installed
  ↓
Reading Period Open
  ↓
Manual / AMI Reading
  ↓
Media Evidence
  ↓
VEE / Review
  ↓
Approved Periodic Reading
  ↓
Collect Replacement Closing Segments
  ↓
Create ONE Utility Bill
  ↓
Create Bill Reading Components
  ↓
Tariff Snapshot
  ↓
Confirm Sale Order
  ↓
Create/Post Accounting Invoice
  ↓
Payment Period
  ↓
Payment / Gateway
  ↓
Explicit Allocation
  ↓
Reconciliation
  ↓
Payment Period Reconciled
  ↓
Historical Lock
```

---

# 49. End-to-End Replacement Flow

```text
Service Order
  ↓
Assign Technician
  ↓
Reserve New Meter
  ↓
Field Visit
  ↓
Old Closing Reading + Evidence
  ↓
Canonical Replacement Engine
  ├── replacement_closing
  ├── detach old meter
  ├── attach new meter
  └── opening
  ↓
Stock Movement
  ├── New Meter → Installed
  └── Old Meter → Quarantine/Return/Scrap
  ↓
Replacement Done
  ↓
Next Periodic Reading
  ↓
Combined Bill Components
```

---

# 50. End-to-End Collection Flow

```text
Posted Utility Invoice
  ↓
Payment Intent / Manual Collection
  ↓
Journal / Provider
  ↓
Lock Financial Target
  ↓
Create/Post Payment
  ↓
Explicit Allocation
  ↓
Reconcile Selected Receivable
  ↓
Update Utility Bill State
  ↓
Receipt / Notification
```

---

# 51. Traceability Rule

أي مبلغ يجب تتبعه في الاتجاهين:

```text
Utility Account
  ↓
Reading
  ↓
Bill Reading Component
  ↓
Sale Order
  ↓
Accounting Invoice
  ↓
Payment Allocation
  ↓
Payment
```

والعكس.

---

# 52. Architecture Roadmap

## V7.1 — Critical Integrity

```text
Media legacy repair
Period migration
Payment allocation
Reading settlement redesign
Billing golden regression
Operations/Inventory dependency integrity
```

## V7.2 — Billing & Period Production

```text
Period impact engine
Period statistics optimization
Tariff snapshots
Due-date policy
Accounting configuration validation
Concurrency hardening
```

## V7.3 — Operations & Inventory

```text
Service-order orchestration
Meter custody
Warehouse/location configuration
Replacement stock flow
Removed-meter disposition
```

## V7.4 — Security & Integration

```text
Unified geographic authorization
API hardening
Webhook security
Outbox retry/backoff
Audit hardening
```

## V7.5 — Portal & UX

```text
Customer portal completeness
Reading/bill/payment history
Service requests
Notifications
Arabic/English UX polish
```

## V7.6 — Migration & Scale

```text
Migration rehearsals
Legacy repair
Load testing
Index tuning
Backup/restore rehearsal
Monitoring
```

## V7.7 — UAT / Release Candidate

```text
No new features
Regression fixes
Security fixes
Performance fixes
Data reconciliation
Cutover rehearsal
```

---

# 53. Architecture Definition of Done

تعتبر المعمارية مطبقة عندما:

- لا توجد Business Logic مالية حرجة في UI فقط.
- لا توجد Historical destructive corrections.
- Media تمر عبر Canonical Media Service/Route.
- لا يوجد Partner-wide automatic reconciliation.
- Period lifecycle مهاجر ومطبق بالكامل.
- Billing Components immutable.
- Replacement end-to-end متسق.
- Inventory serial/custody lifecycle مكتمل.
- API والـMedia يستخدمان Authorization policy موحدة.
- External side effects Idempotent وقابلة لإعادة المحاولة.
- Critical flows مغطاة باختبارات.
- Migration وBackup/Restore جُربا قبل Go-Live.

---

# 54. Final Architectural Position

```text
Core       = Domain Truth
Billing    = Revenue Engine
Operations = Field Orchestration
Inventory  = Physical Custody
Media      = Evidence
Accounting = Financial Truth
Outbox     = Reliable Side Effects
Security   = Default-Deny Scoped Access
Audit      = Historical Accountability
```

نجاح النظام يقاس بقدرته على الإجابة لأي عملية:

```text
What happened?
Why?
Who did it?
When?
Against which account/meter/period?
What evidence supports it?
What financial document resulted?
Was it paid/reconciled?
Can the original historical state be reconstructed?
```

---

# 55. Canonical Architecture Summary

```text
                          ┌─────────────────────┐
                          │   Utility Account   │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │        Meter        │
                          └──────────┬──────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 │                                       │
                 ▼                                       ▼
        ┌─────────────────┐                    ┌─────────────────┐
        │ Physical Stock  │                    │     Reading     │
        │ Lot / Custody   │                    │ + Media Asset   │
        └─────────────────┘                    └────────┬────────┘
                                                       │
                                                       ▼
                                             ┌──────────────────┐
                                             │ Review / VEE     │
                                             └────────┬─────────┘
                                                      │
                                                      ▼
                                           ┌──────────────────────┐
                                           │ Billing Components   │
                                           │ Immutable Snapshots  │
                                           └──────────┬───────────┘
                                                      │
                                                      ▼
                                           ┌──────────────────────┐
                                           │ Utility Sale Order   │
                                           └──────────┬───────────┘
                                                      │
                                                      ▼
                                           ┌──────────────────────┐
                                           │ Accounting Invoice   │
                                           └──────────┬───────────┘
                                                      │
                                                      ▼
                                           ┌──────────────────────┐
                                           │ Payment Allocation   │
                                           └──────────┬───────────┘
                                                      │
                                                      ▼
                                           ┌──────────────────────┐
                                           │ Reconciliation       │
                                           └──────────────────────┘
```

---

---

# Appendix A — Architecture Decision Records (V2)

## ADR-001 — Odoo Remains the System of Record

**Decision:** Odoo/PostgreSQL يحتفظان بالحقيقة التشغيلية والمالية.
**Reason:** منع انتشار Consistency عبر خدمات عديدة دون حاجة.

## ADR-002 — Hybrid Workflow Rather Than Temporal Everywhere

**Decision:** Temporal scoped to long-running operations and batch orchestration.
**Not Used For:** one invoice, one notification, trivial synchronous transaction.
**Reason:** Durability حيث تستحقها دون Operational Complexity لكل عملية صغيرة.

## ADR-003 — Externalized Media Storage

**Decision:** `utility.media.asset` يحتفظ Metadata/identity بينما Target binary payload في Organized Filesystem خارج Odoo، مع NGINX delivery.
**Compatibility:** Attachment Adapter يبقى أثناء الانتقال.

## ADR-004 — Persistent Reading Staging

**Decision:** Batch lines persistent and crash-safe.
**Reason:** Retry, audit, partial failure, progress visibility.

## ADR-005 — Explicit Payment Allocation

**Decision:** Payment reconciles only explicitly selected Utility invoice receivable lines.
**Rejected:** partner-wide automatic reconciliation.

## ADR-006 — Immutable Billing Evidence

**Decision:** billed readings/components/accounting documents لا تعدل destructive.
**Correction:** Credit/Debit/Settlement/Reversal documents.

## ADR-007 — Partition Before Scale Pain

**Decision:** design reading/batch partitioning before 60M+ row lifecycle.
**Reason:** operational maintenance and predictable query/index behavior.

## ADR-008 — PgBouncer in Scale Topology

**Decision:** connection pooling أمام PostgreSQL في multi-node/multi-worker topology.

## ADR-009 — Redis Is Auxiliary Only

**Decision:** Redis للـrate limiting/cache؛ ليس مصدر مالي أو تشغيلي.

## ADR-010 — Micro-Batch Billing

**Decision:** million-account run splits into independent deterministic transactions.
**Rejected:** one giant monthly transaction.

---

# Appendix B — V2 Superseded Decisions

| V1 Position | V2 Position |
|---|---|
| Temporal fully deferred | Temporal is Target but strictly scoped |
| Local Workflow Adapter as final production target | Local remains current default; Hybrid workflow is scaled target |
| Attachment backend current, FS future | Attachment compatibility; Filesystem+NGINX is Target Production |
| Simple single-node deployment target | Right-sized horizontal topology for million-subscriber capacity |
| Generic DB performance tuning | PgBouncer + partition planning + batch architecture explicitly required |
| Billing execution mainly business-flow oriented | Billing execution also defined as micro-batched scale process |

---

# Appendix C — Capacity Assumptions to Validate

الأرقام المستخدمة في V2 هي Planning Baseline وليست SLA:

```text
Subscribers:                  1,000,000
Periodic readings/month:      1,000,000
Peak readings/day:            ~50,000–65,000
Media/month:                  ~90–110 GB
Media/year:                   ~1.1–1.3 TB
Reading rows/year:            ~12M
Five-year reading rows:       60M+
Bills/month:                  up to 1M
Collections/month:            up to 1M
```

يجب تحديثها بعد:

```text
Walking Skeleton
Production-like synthetic load
Real pilot telemetry
```

---

# Appendix D — Final Target Runtime Summary

```text
                                USERS / DEVICES / PORTAL
                                           │
                                           ▼
                                    NGINX / LB
                                           │
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
                Odoo Application                        Media Gateway
                       │                                       │
                       ▼                                       ▼
                   PgBouncer                          Media Authorization
                       │                                       │
                       ▼                                       ▼
                PostgreSQL Primary                      NGINX Internal
                       │                                       │
              ┌────────┴────────┐                              ▼
              ▼                 ▼                         Filesystem
      Transactional Data   Optional Replica                    │
                                                               │
          Redis ◄──── Rate Limit / Cache                       │
                                                               │
          Outbox / Commands                                    │
                 │                                             │
       ┌─────────┴──────────┐                                  │
       ▼                    ▼                                  │
 Local/Short Tasks       Temporal                              │
                         │                                     │
               ┌─────────┼──────────┐                          │
               ▼         ▼          ▼                          │
            Reading    Billing   Operations                    │
            Workers    Workers    Workers                      │
               │         │          │                          │
               └─────────┴──────────┴──────────────────────────┘
```

---

# Appendix E — Documentation Set Derived from This Master

هذه الوثيقة هي Parent Architecture Document.

يشتق منها:

```text
MASTER_SPECIFICATION.md
SRS.md
TECHNICAL_ARCHITECTURE.md
BILLING_ENGINE.md
PERIOD_LIFECYCLE.md
READING_BATCH_ARCHITECTURE.md
MEDIA_ARCHITECTURE.md
PAYMENT_ALLOCATION.md
ACCOUNTING_FLOWS.md
METER_REPLACEMENT.md
INVENTORY_CUSTODY.md
SECURITY_MATRIX.md
API_SPECIFICATION.md
INTEGRATION_ARCHITECTURE.md
CAPACITY_AND_PERFORMANCE.md
DATA_MIGRATION.md
DEPLOYMENT.md
BACKUP_RESTORE.md
OBSERVABILITY.md
UAT_PLAN.md
GO_LIVE_RUNBOOK.md
```

---

**End of UTILITY_ERP_MASTER_ARCHITECTURE_V2**
