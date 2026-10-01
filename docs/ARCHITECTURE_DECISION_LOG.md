# Architecture Decision Log

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Reviewed SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Documentation Version:** 3.2
**Reviewed Date:** `2026-08-24`

This is a concise ADR index. Detailed implementation belongs in the linked domain documents.

| ADR | Status | Classification | Decision | Consequence / relevant modules |
|---|---|---|---|---|
| ADR-001 Odoo/PostgreSQL System of Record | Accepted | CURRENT V1 | Odoo/PostgreSQL is canonical operational and financial persistence. | No shadow operational DB; all modules. |
| ADR-002 No Customer Wallet | Accepted | CURRENT V1 / OUT OF SCOPE | Postpaid Utility has no customer wallet architecture. | Use bills, payments, allocations, and accounting balances. |
| ADR-003 Standard Odoo Stock Is Physical Inventory Truth | Accepted | CURRENT V1 | Standard stock/lot/moves are the physical serialized inventory ledger. | `utility_inventory`, `utility_operations`. |
| ADR-004 Utility Meter Is Logical Meter Identity | Accepted | CURRENT V1 | `utility.meter` carries operational identity while stock carries physical custody. | `utility_core`, `utility_inventory`. |
| ADR-005 Explicit Invoice Payment Reconciliation | Accepted | CURRENT V1 | Payments reconcile only explicitly selected utility invoice receivable lines. | `utility_billing`, `account.move`, `account.payment`. |
| ADR-006 Immutable Financial/Billing Evidence | Accepted | CURRENT V1 | Corrections use controlled adjustment/reversal documents, not destructive mutation. | Billing/accounting flows and audit trail. |
| ADR-007 Core/Billing Reading Ownership | Accepted | CURRENT V1 | Core owns reading truth; Billing inherits and owns commercial fields/behavior. | `utility_core/models/utility_reading.py`, billing extension. |
| ADR-008 Payment Allocation Entry Point Consolidation | Accepted | CURRENT V1 | Payment entry starts from an explicit utility invoice allocation path. | Payment allocation and gateway flows. |
| ADR-009 Financial Reversal Orchestraction | Accepted | CURRENT V1 | Adjustments, refunds, and write-offs create controlled financial artifacts. | `utility.billing.adjustment`, `utility.writeoff`. |
| ADR-010 Reader Batch Concurrency Controls | Accepted | CURRENT V1 | Batches use bounded work, NOWAIT locking, and SQLSTATE `55P03` handling. | `utility_billing` batch service. |
| ADR-011 Migration Bounded Processing | Accepted | CURRENT V1 | Migration staging is persistent, bounded, retryable, and traceable. | `utility_core` migration staging models. |
| ADR-012 Payment Gateway Callback Authentication Before Lock | Accepted | CURRENT V1 | Authenticate/token-verify before `FOR UPDATE`; then transition only pending transactions. | Billing API/gateway transaction. |
| ADR-013 Write-off Single Credit Note Invariant | Accepted | CURRENT V1 | One write-off creates at most one generated Credit Note. | `utility.writeoff`, linked `account.move`. |
| ADR-014 Sensitive Wizard Least Privilege | Accepted | CURRENT V1 | Wizard access cannot exceed the most sensitive mutation it performs. | Core wizard ACLs and server guards. |
| ADR-015 Action-Based Operational State Transition | Accepted | CURRENT V1 | Workflow actions, not raw state writes, execute operational transitions. | Service/work/install/inspection views. |
| ADR-016 Unified Organizational Data Isolation | Accepted | CURRENT V1 | Role permissions & Region/Branch geography are independent; fail-closed unified scope. | res.users, utility_core, utility_operations, utility_billing. |
| ADR-017 Runtime/CI Proof Deferred From Current Static Gate | Accepted | DEFERRED | Static implementation and test existence are documented separately from runtime proof. | Release gate and UAT/runbook. |
| ADR-018 Prepaid Excluded From V1 | Accepted | OUT OF SCOPE | `utility_prepaid` is not part of the current V1 release chain. | Prepaid remains separately documented. |
| ADR-019 Scale Architecture Remains Target V2 | Accepted | TARGET V2 | PgBouncer, horizontal nodes, scalable media, partitioning, micro-batches, and scoped Temporal require triggers and runtime evidence. | `TARGET_V2_ARCHITECTURE_ROADMAP.md`. |
| ADR-020 Role-Based Authorization Is Independent From Organizational Scope | Accepted principle | CURRENT roles / TARGET hardening | Roles answer what a user can do; company/region/branch scope answers where. V1 prefers one unified user scope across multiple roles. | `SECURITY_MATRIX.md`, `ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md`. |
| ADR-021 Contract Template Versioning & Immutable Pricing Snapshot | Accepted | CURRENT V1 | Commercial configuration uses `utility.contract.template.version` (in-place unbilled, auto-V+1 on billed changes). Financial calculation evidence uses immutable `utility.bill.pricing.snapshot` and `utility.bill.pricing.block` on each bill. | `utility_core`, `utility_billing`, `sale.order`. |
| ADR-022 Collector Deposit Is a Direct Bank Settlement Event | Accepted | CURRENT V1 | Collector custody settlements and bank deposits execute through explicit Odoo accounting moves. Bank deposits allocate open collector settlements automatically by reference/FIFO when lines are omitted, reconcile only the deposit clearing account, and do not use bank statement matching. Company-scoped `settlement_key` prevents duplicate events. | `utility_billing`, `utility.collection.settlement`, `utility.bank.settlement`, `ACCOUNTING_FLOWS.md`. |
| ADR-023 Annual Operational Database Rotation and 365-Day Media Retention | Accepted | TARGET V2 / CONDITIONAL | Operate one active operational year per Odoo database; close and archive the year read-only, create a new operational database, retain image metadata/audit history while deleting image bytes after 365 days, use `ir.attachment` with shared Odoo Filestore initially, and do not deploy DR or MinIO in the initial sizing baseline. | `DEPLOYMENT.md`, `MEDIA_ARCHITECTURE.md`, `BACKUP_RESTORE.md`, `PRODUCTION_SIZING_IMPLEMENTATION_PLAN.md`. |
| ADR-024 Transformer-Based Route Assignment Wizard | Accepted | CURRENT V1 | Use `utility.route.assignment.wizard` to dynamically aggregate subscribers via transformer links and assign field crews (`res.users`), maintaining route cleanliness. | `utility_core`, `utility.route`, `utility.transformer`. |
| ADR-025 Dedicated Meter Reader Entity & Mobile Sync | Accepted | CURRENT V1 | Model meter reading staff in `utility.meter.reader` with dedicated route synchronization, mobile API endpoints, and dynamic role discovery. | `utility_core`, `utility_billing/controllers`, Flutter mobile app. |
| ADR-026 Structured Storage for IR Attachment | Accepted | CURRENT V1 | Extend `ir.attachment` with deterministic structured directory paths (`module/model/YYYY/MM/DD/checksum`), content deduplication, and backward-compatible legacy reading. | `utility_core/models/utility_ir_attachment.py`. |
| ADR-027 Standard Attachment Storage Without Thumbnails & No S3/MinIO | Accepted | CURRENT V1 | Meter and operational images are stored strictly as single standard Odoo `ir.attachment` records (`attachment=True`) in the native Filestore. All thumbnail generation and separate image variants are removed, and external object storage (S3/MinIO) is excluded from V1. | `utility_core`, `utility_reading`, `utility_media_asset`, `MEDIA_ARCHITECTURE.md`. |
| ADR-028 True Global Record Rules & Non-Destructive Staff Scope Sync | Accepted | CURRENT V1 | Organizational data isolation rules (`utility.alarm`, `utility.service.order`, `utility.work.order`, etc.) are defined with `global=True` and `groups=[(6, 0, [])]` ensuring strict conjunction (`AND`) against multi-company rules. Staff scope sync preserves existing user scope when staff defines no region/area. | `utility_operations`, `utility_core`, `ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md`. |
| ADR-029 Removal of Prepaid and Additional Addons From Codebase | Accepted | CURRENT V1 | `utility_prepaid` and `additional` directories are completely removed from the repository. V1 focus is strictly hardened Postpaid electricity distribution. | Repo tree, manifests, documentation index. |
| ADR-030 Externalization of Date Range Addon to OCA Dependency | Accepted | CURRENT V1 | `date_range` is treated as an external OCA dependency installed in the Odoo environment, rather than a vendored module within the repository. | Repo tree, installation runbooks, manifests. |

## ADR review rule

An accepted newer ADR supersedes stale prose, but implementation evidence remains authoritative for CURRENT V1 behavior. A code change does not silently promote a TARGET V2 decision to deployed architecture.
