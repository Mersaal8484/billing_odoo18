---
name: odoo-framework-best-practices
description: >-
  Technical Odoo 18 ORM standards, OCA code quality rules, N+1 query prevention,
  safe sudo() scoping, multi-company/branch record rules, XML load ordering, and
  OWL JS component best practices for Utility ERP.
---

# Odoo 18 Framework & OCA Best Practices

This skill defines technical engineering guardrails, ORM performance patterns, security boundaries, and OCA quality standards for developing and maintaining Odoo 18 addons in `utility_erp`. Check the live Odoo 18 source and current repository code before applying a framework pattern; the V1 baseline documents an earlier implementation snapshot, not proof of this port's runtime behavior.

## Source-first workflow

- Confirm the target Odoo version from the local core checkout (`odoo/release.py`) and the repository's `AGENTS.md`; resolve disagreements before using version-specific guidance.
- Before changing a model method, field, XML view, OWL component, or migration, trace its definition and extension points in the local Odoo core and installed addons. Check inheritance order, callers, manifest load order, view XPath anchors, XML IDs, ACLs, and record rules as relevant to the change.
- Keep a compact evidence note with `file:line` references for the framework behaviors that drive the change. Mark missing or ambiguous symbols as unverified instead of guessing.
- Use external Odoo 18 skill packs as lookup material only. Confirm each relevant claim against the local source and keep Utility ERP ownership, scope, security, and V1/V2 rules from `AGENTS.md` and the canonical docs authoritative.
- Scale tracing to risk: a label-only change needs little investigation; schema changes, overridden workflows, access changes, accounting/stock effects, and public APIs need their full call and dependency path.

---

## 1. ORM Performance & Query Optimization

- **Avoid N+1 Queries**:
  - Avoid ORM searches or SQL inside per-record loops when they produce N+1 behavior.
  - Batch/prefetch whenever practical.
  - Do not refactor a loop solely on static appearance; profile or verify query behavior when performance impact is uncertain.
  - Use `.mapped()`, `.filtered()`, or `.filtered_domain()` for recordset filtering in memory.
  - Use `search_count(domain)` instead of `len(search(domain))`.
- **Field Indexing**:
  - Add `index=True` to Foreign Key fields (`Many2one`) that are heavily queried in domains, search views, or record rules (e.g., `meter_id`, `contract_id`, `area_id`).
- **Batching Operations**:
  - Perform record creation and updates in batch where possible (`create([{...}, {...}])` or `.write({...})` on a recordset).

---

## 2. Security, Sudo Scoping & Multi-Branch Safety

- **Scoped `sudo()`**:
  - Avoid unscoped `sudo()` calls across business logic.
  - When bypassing security for automated tasks (e.g., cron jobs or webhooks), explicitly scope down using `.with_user()` or limit the accessed field set to prevent privilege escalation.
- **Multi-Company & Branch Isolation**:
  - Every scoped business model must have a deterministic company/organizational scope path.
  - Do NOT add `branch_id` mechanically to every model. Prefer canonical related/derived scope from the owning business entity. Add a stored readonly/indexed scope field only when security or performance evidence justifies it.
  - Add explicit record rules in `security/ir_rule.xml` enforcing company and branch data isolation.

---

## 3. XML Loading Sequence & Manifesto Management

- **Manifest Load Order (`__manifest__.py`)**:
  1. Security files: `security/ir.model.access.csv`, `security/ir_rule.xml`
  2. Data files: `data/ir_sequence_data.xml`, default records
  3. Views & Actions: `views/*.xml`
  4. Menus: `views/menu_views.xml` (placed at the bottom to ensure referenced actions exist)
  5. Wizards & Reports: `wizards/*.xml`, `reports/*.xml`
- **XML ID Namespacing**:
  - Prefix XML IDs with module-specific prefixes (e.g., `utility_core_`, `utility_billing_`) to avoid cross-module ID collisions.

---

### Dependent Form Domains

- In this project, use the applicable existing chain: `recurring_rule_type → region → area → zone → route`, `region → area → zone → substation`, `substation → feeder → transformer → route`, or `utility.subscriber.category → utility.subscriber`. Do not fabricate missing model relationships.
- For meter assignments, the compatible phase chain is `utility.meter.model.phase → utility.meter`, then the selected endpoint: `utility.connection.type.phase` for a subscriber, `utility.transformer.phase` for a transformer, or explicit `utility.feeder.phase` for a feeder. Do not assume an implicit feeder phase.
- Where a selector depends on several parents, use a combined eligibility domain rather than choosing one parent as authoritative; for example, a contract template must be compatible with subscriber category, subscriber type, geographic scope, and applicable billing cadence.
- Model one-to-one relations as two reciprocal `Many2one` fields with database uniqueness on both links and server-side reciprocal validation; do not rely on a readonly UI field to maintain the invariant.
- For parent/child business selectors, define a dynamic XML `domain` using the parent field(s), so the opening dropdown is already filtered.
- Use `@api.onchange` to remove stale child values after a parent changes, and pair it with `@api.constrains` validation for create/write, imports, and RPC.
- Keep domains indexed and narrow. A dependent domain is configuration validation and must not be used as the only security control.

---

## 4. Exception Contracts & Logging

- **Business Errors vs Systems Failures**:
  - Use Odoo native `UserError` for expected user mistakes, `ValidationError` for field constraint failures, and `AccessError` for security violations.
  - Do NOT catch generic `Exception` around ORM transactions; let database rollbacks execute naturally.
- **Logging**:
  - Use `logging.getLogger(__name__)` instead of `print()`. Log critical operational events at `info` or `warning` level.

---

## 5. UI/UX & Translation Standards

- **Odoo-Native Views**:
  - Statusbar for state fields (`widget="statusbar"`).
  - Clear workflow action buttons with Odoo 18 expression attributes such as `invisible="state != 'draft'"` and `readonly="state != 'draft'"`. Keep the referenced fields in the view and enforce transitions in server actions; do not use legacy `attrs` or `states` modifiers.
  - Use `<list>` for list view roots and `list` in action view modes; check existing inherited view targets before changing XML.
  - Search views must include relevant `filters`, `group_by`, and search fields.
- **Arabic Translation**:
  - Wrap user-facing string literals in `_('String')` for translation support.
