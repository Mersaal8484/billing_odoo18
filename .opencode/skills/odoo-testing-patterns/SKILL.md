---
name: odoo-testing-patterns
description: Use for writing, reviewing, or repairing Odoo 18 backend, ORM, HTTP, cron, and failure-path tests. Do not use for browser-only visual QA or load testing.
---

# Odoo testing patterns

Use this skill to turn an Odoo behavior or regression into focused, deterministic test evidence. Keep the test at the lowest layer that proves the required invariant.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- The routed domain skill and its existing tests
- `skills/odoo-framework-best-practices/SKILL.md`

## Select the right base case

- Use `TransactionCase` for ordinary ORM workflows, constraints, access rules, and record lifecycle tests. Odoo 18 runs its test methods in savepoints; use `setUpClass` for expensive shared fixtures and avoid mutations that leak between tests. `SavepointCase` is not available in the local Odoo 18 test framework.
- Use `HttpCase` only for actual controller, session, route, or browser integration behavior. Prefer ORM tests when the behavior is purely model-side.

## ORM and database evidence

- Build the smallest valid fixture set. Use stable, unique test identifiers and explicit company/scope fields where the model requires them.
- Assert both the user-visible behavior and the persisted invariant. For a database-only property such as a uniqueness constraint, lock behavior, or generated artifact count, use parameterized `self.env.cr.execute(...)` queries and assert the result; never interpolate data into SQL strings.
- Test the negative path with `self.assertRaises(ValidationError)`, `UserError`, or `AccessError` as appropriate. Assert the meaningful postcondition after the failed operation when it matters.
- Exercise create and write when the same invariant must survive imports, RPC, and form edits. Do not treat an XML domain or onchange as proof of backend enforcement.
- Use `flush_model()` / `invalidate_model()` only when the assertion genuinely needs database state outside the ORM cache.

## Boundaries, mocks, and automation

- Mock only external boundaries such as HTTP providers, clocks, filesystem/media adapters, queues, or mail gateways. Do not mock the ORM method under test or replace the business invariant with a mock assertion.
- For cron methods, call the cron/service method directly with bounded fixtures. Verify idempotency, retry/error state, ownership, and resulting records; patch time or external transport deterministically when needed.
- For callbacks and jobs, include duplicate delivery/execution tests where one event must create at most one artifact.

## Error and test quality rules

- Expected business failures must remain specific: catch the intended Odoo exception class, not `Exception`.
- Avoid relying on test order, live dates, a real network, a preexisting database record, or another test's side effects.
- For financial, stock, workflow, or security behavior, test both successful transition and rejected transition. Confirm no duplicate accounting, stock, or lifecycle artifact was persisted.
- Keep assertions focused on observable contracts, not implementation formatting or incidental method calls.

## Validation

Run the narrowest affected module test suite first using the repository command convention. Report static validation separately from runtime Odoo test evidence, and state any unavailable database or service dependency plainly.
