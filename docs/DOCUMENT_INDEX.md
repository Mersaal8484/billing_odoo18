# Utility ERP Architecture V2.1 — Documentation Index

**This file is the canonical documentation entry point.**

**Platform:** Odoo 16 Community\
**Repository:** `AbdulrhmanBashammmakh/utility_erp`\
**Branch:** `development`\
**Last verified implementation SHA:** `b97bea78aaba6b91575dd9b8cd2c14d685c64fd5`\
**Documentation version:** `3.3`\
**Reviewed Date:** `2026-09-18`\
**Status:** Current V1 + Target V2

اقرأ هذا الفهرس أولًا، ثم اتبع مسار المجال المطلوب فقط. هذه الصفحة تنظّم الوصول إلى الوثائق ولا تعيد كتابة مواصفاتها.

## Source-of-truth precedence

عند وصف **CURRENT V1**، اتبع هذا الترتيب:

1. الكود والاختبارات الحالية عند الـ HEAD الذي تتم مراجعته.
2. قرارات ADR المقبولة في [`ARCHITECTURE_DECISION_LOG.md`](ARCHITECTURE_DECISION_LOG.md).
3. لقطة التنفيذ الموثقة في [`CURRENT_V1_IMPLEMENTATION_BASELINE.md`](CURRENT_V1_IMPLEMENTATION_BASELINE.md).
4. وثيقة المجال ذات الصلة.
5. مهارات المستودع للتنفيذ والمراجعة فقط؛ ليست مصدرًا للحقيقة التجارية.

وثائق Target V2 لا تعني أنها مطبقة. ولا يجوز لوثيقة قديمة أن تتغلب على قرار تنفيذ أحدث مقبول.

## Current implementation

- [`CURRENT_V1_IMPLEMENTATION_BASELINE.md`](CURRENT_V1_IMPLEMENTATION_BASELINE.md)
- [`ARCHITECTURE_DECISION_LOG.md`](ARCHITECTURE_DECISION_LOG.md)
- [`RELEASE_TRACEABILITY_MATRIX.md`](RELEASE_TRACEABILITY_MATRIX.md)

## Architecture

- [`UTILITY_ERP_MASTER_ARCHITECTURE_V2.md`](UTILITY_ERP_MASTER_ARCHITECTURE_V2.md)
- [`MASTER_SPECIFICATION.md`](MASTER_SPECIFICATION.md)
- [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md)
- [`TARGET_V2_ARCHITECTURE_ROADMAP.md`](TARGET_V2_ARCHITECTURE_ROADMAP.md)

- [OCA_ADDONS_EVALUATION_AND_ADOPTION_PLAN.md](OCA_ADDONS_EVALUATION_AND_ADOPTION_PLAN.md) — تقييم 37 إضافة OCA وخطة استخدامها ودمجها؛ مقترحات وليست إضافات مثبتة.

## Security

- [`ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md`](ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md)
- [`SECURITY_MATRIX.md`](SECURITY_MATRIX.md)
- [`SRS.md`](SRS.md)
- [`UAT_PLAN.md`](UAT_PLAN.md)

في نموذج الجغرافيا الحالي، `utility.region(type='region')` هي Region، و`utility.region(type='area')` هي الفرع التنظيمي Branch، و`utility.region(type='zone')` منطقة أدنى. لا تنشئ نموذج Branch مكررًا.

## Billing and accounting

- [`BILLING_ENGINE.md`](BILLING_ENGINE.md)
- [`ACCOUNTING_FLOWS.md`](ACCOUNTING_FLOWS.md)
- [`PAYMENT_ALLOCATION.md`](PAYMENT_ALLOCATION.md)
- [`PERIOD_LIFECYCLE.md`](PERIOD_LIFECYCLE.md)

## Inventory and meter

- [`INVENTORY_CUSTODY.md`](INVENTORY_CUSTODY.md)
- [`METER_REPLACEMENT.md`](METER_REPLACEMENT.md)

## Reading

- [`READING_BATCH_ARCHITECTURE.md`](READING_BATCH_ARCHITECTURE.md)
- [`METER_VISION_OCR_ROADMAP.md`](METER_VISION_OCR_ROADMAP.md) — خارطة طريق الذكاء الاصطناعي وOCR لقراءة العدادات وخطوات الوصول لأعلى دقة.

## API and integration

- [`API_SPECIFICATION.md`](API_SPECIFICATION.md)
- [`INTEGRATION_ARCHITECTURE.md`](INTEGRATION_ARCHITECTURE.md)

## Operations and UX

- [`OPERATIONAL_UI_UX_ARCHITECTURE.md`](OPERATIONAL_UI_UX_ARCHITECTURE.md)

## Migration

- [`DATA_MIGRATION.md`](DATA_MIGRATION.md)

## Runtime and scale

- [`DEPLOYMENT.md`](DEPLOYMENT.md)
- [`CAPACITY_AND_PERFORMANCE.md`](CAPACITY_AND_PERFORMANCE.md)
- [`MEDIA_ARCHITECTURE.md`](MEDIA_ARCHITECTURE.md)
- [`OBSERVABILITY.md`](OBSERVABILITY.md)
- [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)
- [`utility_erp_final_sizing_annual_db_ir_attachment_no_dr.md`](../utility_erp_final_sizing_annual_db_ir_attachment_no_dr.md)
- [`PRODUCTION_SIZING_IMPLEMENTATION_PLAN.md`](PRODUCTION_SIZING_IMPLEMENTATION_PLAN.md)

## Release

- [`UAT_PLAN.md`](UAT_PLAN.md)
- [`GO_LIVE_RUNBOOK.md`](GO_LIVE_RUNBOOK.md)
- [`RELEASE_TRACEABILITY_MATRIX.md`](RELEASE_TRACEABILITY_MATRIX.md)

## Agent routing

The repository router is [`../AGENTS.md`](../AGENTS.md). Repo-local execution skills are under [`../skills/`](../skills/). Read the relevant skill after this index and before scoped implementation or review.

## Current V1 module chain

```text
date_range
    ↓
utility_core
    ↓
utility_inventory
    ↓
utility_operations
    ↓
utility_billing
```

`utility_prepaid` is **OUT OF SCOPE for V1**.

## Root operational release entrypoints

`MANUAL_RELEASE_GATE.md`, `UAT_CHECKLIST.md`, and `UAT_CHECKLIST_CORE_BILLING_OPERATIONS_EN.md` remain at repository root as execution-oriented release artifacts. Their architecture and acceptance source remains in this `docs/` package, especially [`UAT_PLAN.md`](UAT_PLAN.md) and [`GO_LIVE_RUNBOOK.md`](GO_LIVE_RUNBOOK.md).

## Classification vocabulary

- **CURRENT V1:** verified in the implementation at the reviewed SHA.
- **TARGET V2:** accepted future architecture, not implied as deployed.
- **DEFERRED:** intentionally not proven or not implemented yet.
- **OUT OF SCOPE:** excluded from the current release boundary.
