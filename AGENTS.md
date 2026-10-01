# AGENTS.md — Utility ERP execution router

This file contains repository-wide invariants and routing only. Treat `docs/DOCUMENT_INDEX.md` as the canonical documentation entry point and load the smallest relevant repo-local skill before scoped work.

## Source-of-truth order

1. Live code and tests at the reviewed HEAD for CURRENT V1 facts.
2. Accepted decisions in `docs/ARCHITECTURE_DECISION_LOG.md`.
3. `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md` for the verified implementation snapshot.
4. The relevant domain document in `docs/`.
5. `skills/<skill-name>/SKILL.md` for execution discipline, not business truth.

`/skills` is authoritative. `.opencode/skills/` is a generated/tool-compatibility mirror and must never contain independent business rules.

Do not present TARGET V2 proposals, a UI affordance, a test file, or an empty CI status as implemented evidence without verification.

## Skill routing

| Work area | Required skill | Start with |
|---|---|---|
| Boundaries, dependencies, ownership, CURRENT/TARGET | `utility-architecture` | `docs/DOCUMENT_INDEX.md`, baseline, ADR |
| Groups, ACLs, record rules, role/data scope, APIs | `utility-security-scope` | baseline, ADR, organizational security, matrix, SRS, UAT |
| Invoices, payments, allocations, write-offs, penalties | `utility-accounting` | baseline, ADR, accounting flows, payment allocation |
| Meters, lots, stock custody, replacements | `utility-inventory` | baseline, inventory custody, meter replacement |
| Service/work/inspection/installation workflows and UX | `utility-operations` | baseline, operational UX, SRS, UAT |
| Readings, batches, bills, billing and payment flow | `utility-billing` | baseline, ADR, billing engine, reading batches, accounting flows |
| REST, callbacks, webhooks, media, error contracts | `utility-api` | API specification, integration, security, reading batches, UAT |
| Staging, templates, mappings, import/retry controls | `utility-migration` | data migration, baseline, technical architecture |
| Static/runtime/UAT evidence and release verdicts | `utility-release-gate` | index, baseline, ADR, UAT, go-live, traceability |
| Deployment, backup/restore, cutover, rollback, Filestore, production operations | `utility-deployment-operations` | deployment, backup/restore, go-live runbook, baseline |
| Logging, metrics, alerts, profiling, load tests, capacity, queue/DB health | `utility-observability-performance` | observability, capacity/performance, deployment, UAT |
| Flutter meter-reading app, offline sync, mobile API/media/printer integration | `utility-mobile-integration` | API, integration, reading batches, media, mobile README |
| Diff/PR security review, blast radius, auth, workflow and integrity regressions | `utility-differential-review` | diff, baseline, ADR, security scope, routed domain skill |
| Python/Dart dependencies, lockfiles, package provenance, secrets, supply chain | `utility-dependency-security` | requirements, pubspec, lockfiles, manifests, CI/deployment |
| Flutter/Dart unit, widget, integration, offline-sync, mocks, analysis, coverage | `utility-mobile-quality` | mobile package, sync engine, API client, mobile integration, API specification |
| Odoo 18 backend JavaScript, OWL components, client actions, field widgets, templates, assets, RTL UX | `utility-frontend-owl` | operational UX, SRS, UAT, module asset blocks, existing static/src |
| Odoo 18 ORM performance, OCA code quality, N+1, XML, sudo | `odoo-framework-best-practices` | skills/odoo-framework-best-practices/SKILL.md |

## Project and dependency invariants

- This branch (`18`) targets Odoo 18 for electricity distribution; `main` and `development` remain on Odoo 16. External dependency: `date_range` (from OCA's 18.0 branch). Core repository addons installed in this order: `utility_core`, `utility_inventory`, `utility_operations`, `utility_billing`. **`utility_meter_vision` is a future V2 OCR/AI module** — its manifest is `installable: False` and it must NOT be installed in V1 production environments.
- `utility_core` is always first among repo addons. Migration staging models live inside `utility_core`; there is no standalone `utility_migration` addon. `utility_portal` was merged into `utility_billing`.
- V1 is strictly postpaid. `utility_prepaid` and `additional` directories have been deleted from the repository. Do not introduce prepaid vending, STS/POS architecture, or OCR/AI auto-billing into V1 scope.

- Media architecture uses standard Odoo `ir.attachment` (`attachment=True`) stored in the native Filestore. Thumbnail generation and external object storage (S3/MinIO) are excluded from V1.
- All record rules for organizational data isolation must be true global rules (`global=True`, `groups=[(6, 0, [])]`) so they evaluate with strict conjunction (`AND`) against multi-company rules.
- Staff geographic scope synchronization is non-destructive: a staff record without defined regions/areas does not wipe user assigned regions.
- `utility_core` owns master data and the base unified `utility.reading`; `utility_billing` owns financial extensions and billing APIs.
- The utility Bill is inherited `sale.order`; the posted Invoice is `account.move`; payments are `account.payment`. Do not recreate deleted `utility.bill`, `utility.collection`, or allocation ledgers.
- Standard Odoo stock, lots, pickings, quants, and valuation are physical custody truth. `utility.meter` is the logical record and `utility_inventory` is the bridge.
- The reading lifecycle is `draft → under_review → approved → billed`; rejection returns to `draft`. Utility bill lifecycle is separate: `draft → confirmed → sent → paid → overdue → cancelled`.
- The eight-level geography is `region → area → zone → office → substation → feeder → transformer → route`, using model hierarchy fields already present. In organizational security language, `utility.region` with `type='area'` is the Branch.

## Engineering guardrails

- Inspect existing code, tests, views, security, and current git changes before editing. Preserve unrelated user work.
- Use `apply_patch` for intentional file edits. Do not reset, checkout, or recursively delete broad paths.
- Keep changes narrow and module-owned. Prefer inheritance and existing Odoo models over duplicate business ledgers.
- Use translated user-facing strings, `UserError`/`ValidationError`/`AccessError` for expected business failures, and logging instead of `print()`.
- Do not catch generic `Exception` around business or database operations. Preserve rollback and surface unexpected DB/programming failures.
- Avoid N+1 ORM queries, searches inside loops, unbounded imports, and unscoped `sudo()`. New business models need company context and appropriate record rules.
- Important workflow state fields are readonly in forms and changed through guarded server-side actions. Financial and stock effects require idempotency, audit links, and focused regression tests.
- Arabic labels and Odoo-native UX are required: clear statusbars, valid workflow buttons, useful search/filter/group-by views, smart buttons, and understandable confirmations.

## Validation

Use focused checks proportional to the change. Standard module tests use:

```text
odoo-bin -d <db> -i <module> --test-enable --stop-after-init
```

For documentation or skill-only changes, validate local links, YAML/frontmatter, `git diff --check`, and the changed-file scope. A release verdict must distinguish static evidence, runtime tests, CI status, and UAT.

## Completion rule

Do not implement a new security architecture, accounting model, inventory ledger, or unrelated refactor merely because a routed document mentions it. If the requested work is documentation, skills, or release review, keep source-code behavior unchanged and report deferred implementation separately.
