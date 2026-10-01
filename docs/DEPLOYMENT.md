# DEPLOYMENT

**Platform:** Odoo 16 Community
**Architecture Baseline:** `UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`
**Last Verified Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Target Scale:** Up to 1,000,000 subscribers (capacity-planning baseline)
**Documentation Version:** 3.2
**Last Verified Date:** 2026-08-24
**Status:** Current V1 + Target V2

**Document Type:** Target Production Deployment Specification

> تحديد topology والخدمات والشبكات والإعدادات وآلية الإصدار والتوسع.

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
- Annual database rotation is a target operating model, not a current V1 runtime fact: one active operational year is closed read-only, archived, and replaced by a new operational database only after rehearsal and approval.
- Initial sizing assumes shared Odoo Filestore for `ir.attachment`; MinIO and a DR site are excluded from the initial footprint.


## 1. Target Topology

```text
Internet/Internal Users
       ↓
NGINX / Load Balancer
       ↓
Odoo Nodes
       ↓
PgBouncer
       ↓
PostgreSQL Primary
       └── Optional Read Replica

Redis
Temporal Cluster (scoped) + separate PostgreSQL
Reading/Billing/Operations Workers
Media Filesystem + NGINX internal delivery
```

Logical separation does not require one physical server per service on day one.

---

## 2. Odoo Nodes

- same code/version.
- shared DB.
- shared canonical media storage access.
- no local-only persistent filestore assumption for target external media.
- consistent addons/config.
- health endpoint.
- log correlation/request IDs.

---

## 3. NGINX

Responsibilities:
- TLS termination.
- reverse proxy.
- load balancing.
- request size/timeouts.
- websocket/longpoll routing where required.
- media internal delivery.
- access logs.
- security headers.

---

## 4. PgBouncer

Placed between Odoo/workers and PostgreSQL in target scale.

Configuration validated with Odoo transaction/session behavior.

---

## 5. PostgreSQL

- dedicated persistent storage.
- SSD/NVMe.
- backups/WAL strategy.
- partition maintenance.
- index maintenance.
- connection limits.
- autovacuum tuning based on workload.
- optional replica for reporting only.

---

## 6. Redis

- persistence optional according to use because no canonical truth.
- bounded memory/eviction policy.
- authentication/network isolation.
- rate limit/cache keys with TTL.

---

## 7. Temporal

Deployed only when scope gate passed.

- 3-node target HA where business requires HA.
- separate PostgreSQL/resources from Odoo DB.
- versioned workers.
- workflow/task queue metrics.

---

## 8. Media Storage

Target:
- organized filesystem.
- durable volume.
- backup snapshot.
- path strategy not exposed externally.
- NGINX read access internal.
- application write permission least privilege.

---

## 9. Configuration

Externalized:
- DB credentials.
- Redis.
- Temporal.
- provider secrets.
- base URLs.
- media root.
- worker settings.
- batch sizes.
- log level.

No secrets in Git.

---

## 10. Release Procedure

1. tag/release build.
2. backup.
3. maintenance/traffic policy if schema migration.
4. deploy code to staging.
5. module upgrade/migration.
6. smoke tests.
7. rolling/controlled prod deployment.
8. validate DB/media.
9. monitor error/latency.
10. rollback if gate fails.

---

## 11. Scaling

Scale first by measured bottleneck:
- Odoo web nodes.
- reading workers.
- billing workers.
- media workers.
- DB resources.
- storage throughput.

Do not autoscale blindly against a saturated DB.

---

## 12. Deployment Acceptance

- fail one Odoo node without outage target violation.
- DB connection pool stable.
- media served.
- secrets unavailable to unauthorized user.
- migration repeatable in staging.
- rollback tested.

## 13. Annual Rotation and Initial Production Sizing

The target sizing baseline is documented in [`utility_erp_final_sizing_annual_db_ir_attachment_no_dr.md`](../utility_erp_final_sizing_annual_db_ir_attachment_no_dr.md). It targets 300,000 customers, 600–750 concurrent users, and up to 7.2 million readings/year.

The initial physical baseline is approximately three compute/virtualization hosts, two dedicated PostgreSQL hosts, and one protected shared-storage platform. The logical baseline is three Odoo application nodes, two job/media nodes, PostgreSQL Primary/Standby, shared Filestore with 4 TB usable capacity, and 12 TB initial archive/backup capacity.

Annual close must include completion of in-flight work, read-only controls, final backup, archive catalog registration, integrity checks, and a tested restore. Database archive retention and image-byte retention are separate lifecycles.

## V3.2 Current vs Target Topology

**CURRENT V1 supported topology:** one Odoo 16 application deployment using PostgreSQL, installed in dependency order `date_range → utility_core → utility_inventory → utility_operations → utility_billing`, with standard local/Odoo workflow execution and the configured media compatibility path.

**TARGET V2 / CONDITIONAL:** PgBouncer, multiple Odoo workers/nodes, scalable filesystem/NGINX media delivery, Redis helpers, Temporal workers, and partitioned high-volume tables. These are not mandatory V1 runtime dependencies and require load evidence, security review, migration rehearsal, and rollback planning.

**TARGET V2 / CONDITIONAL:** annual operational database rotation, shared HA Filestore at the stated capacity, read-only yearly archives, and the no-DR/no-MinIO initial footprint require the execution plan, policy approval, performance evidence, and restore rehearsal before production adoption.

**DEFERRED:** deployment runtime proof, upgrade rehearsal, load validation, and production restore timing.
