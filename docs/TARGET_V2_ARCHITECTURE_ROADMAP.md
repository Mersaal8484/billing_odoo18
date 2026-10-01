# Target V2 Architecture Roadmap

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Branch:** `development`
**Reference Implementation SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Documentation Version:** 3.2
**Reviewed Date:** `2026-08-24`
**Status:** TARGET V2 / not current deployment

This document contains accepted forward-looking architecture only. It must not be read as evidence that the components below are deployed in V1.

| Capability | Status | Trigger | Target direction |
|---|---|---|---|
| PgBouncer | TARGET / CONDITIONAL | Multiple Odoo workers/nodes create connection pressure | Pool PostgreSQL connections without becoming a source of truth |
| Horizontal Odoo topology | TARGET / CONDITIONAL | Measured concurrent workload exceeds one application node | Multiple application workers/nodes behind controlled routing |
| Scalable media backend | TARGET / CONDITIONAL | Attachment volume, delivery latency, or backup size becomes material | Media Adapter over organized filesystem/NGINX |
| Reading-table partition planning | TARGET / CONDITIONAL | Reading/staging volume and maintenance evidence justify partitions | Partition by period/time after Odoo compatibility and migration rehearsal |
| High-volume reading architecture | TARGET / CONDITIONAL | Batch throughput and queue backlog exceed V1 operating envelope | Persistent staging plus chunk workers and durable orchestration |
| Micro-batch billing | TARGET / CONDITIONAL | Billing volume makes a single transaction operationally unsafe | Independent idempotent micro-batches with partial failure reporting |
| Hybrid workflow orchestration | TARGET / CONDITIONAL | Long-running human/timed workflows need durable waiting | Odoo/local atomic work plus scoped Temporal orchestration |
| Observability scaling | TARGET / CONDITIONAL | Current logs/metrics cannot explain queue, DB, or integration latency | Centralized metrics, traces, alerting, and workflow backlog signals |
| Redis rate-limit/cache layer | TARGET / CONDITIONAL | API rate limiting or hot-read cache needs shared state | Redis as helper only; never canonical operational truth |
| Capacity targets | TARGET / DEFERRED | Actual workload profile and load evidence are available | Validate subscriber, reading, batch, API, DB, and recovery targets |
| Annual operational DB rotation | TARGET / CONDITIONAL | One-year active DB policy is approved and annual-close/restore rehearsal passes | Read-only yearly archive, new operational DB, archive catalog, rollback and restore controls |
| 365-day image-byte retention | TARGET / CONDITIONAL | Business/legal retention approval and safe deletion evidence are available | Delete eligible Filestore bytes while preserving media metadata and audit history |
| Shared Filestore initial backend | TARGET / CONDITIONAL | Multi-node Odoo deployment requires shared durable attachment access | `ir.attachment` plus shared HA Filestore; reconsider MinIO only on measured triggers |

## Non-negotiable V2 boundaries

- Odoo/PostgreSQL remains the canonical System of Record.
- Standard Odoo stock remains physical inventory truth.
- Standard Odoo accounting remains financial truth.
- No customer wallet is introduced for V1 postpaid or silently assumed for V2.
- Temporal is not a workflow per invoice, payment, image, or trivial notification; it is scoped to long-running orchestration and large-batch coordination.
- Partitioning and infrastructure expansion are not emergency changes to be made without profiling, rehearsal, and rollback evidence.
- Annual database archives and image-byte retention are separate lifecycles; archiving a database does not override the approved media deletion policy.
- Excluding DR and MinIO from the initial footprint is a scoped sizing decision and must be revisited if business continuity, object immutability, or media scale requirements change.

## Release discipline

Each roadmap item requires an ADR or accepted architecture change, a trigger backed by evidence, a capacity/security impact review, migration/rollback planning, and runtime validation. Until then it remains TARGET, DEFERRED, or CONDITIONAL.
