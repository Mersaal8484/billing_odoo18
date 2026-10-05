---
name: odoo-performance-tuning
description: Use for measured Odoo 18 ORM, PostgreSQL query, computed-field, cron, or server-action performance diagnosis and optimization. Do not use for speculative refactoring or capacity planning without measurements.
---

# Odoo performance tuning

Use this skill to diagnose and improve a demonstrated code-path bottleneck while preserving Odoo business and security behavior. For production observability, capacity, queues, and release evidence, also use `utility-observability-performance`.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CAPACITY_AND_PERFORMANCE.md`
- The affected model, view, cron, or server action and its tests
- `skills/odoo-framework-best-practices/SKILL.md`
- `skills/utility-observability-performance/SKILL.md` when runtime or production evidence is involved

## Measurement before change

- State the operation, representative dataset, concurrency, baseline latency/query count, and acceptable outcome before optimizing.
- Treat N+1 as a hypothesis until query count, SQL logs, profiler output, or a representative trace proves it. Review loops that call `search`, `search_count`, `read_group`, `write`, or access uncached relations.
- Use `EXPLAIN (ANALYZE, BUFFERS)` only for a controlled, read-only representative query and only where it is safe to execute. Never run costly analysis against a production mutation, and redact identifiers from shared evidence.
- Use `pg_stat_statements` only when it is installed and authorized; record its collection window and distinguish aggregate production statistics from a single request trace.

## Odoo ORM improvements

- Batch `create`, `write`, and relation access. Build domains once and use `read_group` for aggregate counts/totals instead of loading records solely to count or sum them.
- Use `with_prefetch()` deliberately when a known record set and field access pattern benefit from controlled prefetching; do not add it mechanically or use it to conceal an N+1 query.
- Keep domains selective and add indexes only for verified query predicates, joins, record rules, or ordering patterns. Assess write and migration cost before adding an index.
- For stored computed fields, declare precise dependencies, batch the compute method, and avoid ORM searches per record. Do not store a value merely to simplify a view.
- Keep cron jobs bounded, idempotent, lock-aware, and observable. Process pages/offsets explicitly, avoid unbounded recordsets, and commit only under an established safe transaction design.
- Treat `ir.actions.server` as business code: scope its domain, avoid per-record queries, preserve access controls, and make retries safe.

## Verify the optimization

- Compare the same workload before and after. Report query count, duration, rows examined/returned where available, and any changed resource cost.
- Run focused regression tests for correctness, access scope, workflow/financial/stock idempotency, and the optimized code path.
- Do not claim a production capacity result from static inspection or a tiny local benchmark. Record residual risk and the next measurement needed.
