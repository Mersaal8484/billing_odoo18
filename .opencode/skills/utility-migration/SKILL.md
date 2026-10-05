---
name: utility-migration
description: Use for Utility ERP staging models, import templates, mapping, retries, savepoints, validation, dry runs, and migration traceability.
---

# Utility migration

Apply this skill to legacy import, staging, mapping, and operational migration work.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/DATA_MIGRATION.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- `AGENTS.md`

## Rules

- Migration staging models live inside `utility_core`; do not create a standalone `utility_migration` addon.
- Preserve source references, row-level errors, deterministic mappings, and resumability.
- Use bounded batches, explicit validation, savepoints where appropriate, and safe retry semantics.
- Keep import templates synchronized with the actual staging fields and parsers.
- A migration test must prove behavior on representative data; a visible Run Now button alone is not evidence of completion.
- For Odoo module schema changes, inspect the current manifest version, migration scripts, and Odoo 18 upgrade behavior. Preserve existing stored data with an explicit migration when a rename, type change, or recomputation requires it; do not assume a field rename is inferred safely.
- Trace source and destination fields, relation models, XML IDs, and module dependencies in the local code before changing mappings. Keep a concise `file:line` evidence note for consequential assumptions.

## Workflow

1. Inspect staging models, import methods, templates, constraints, and target ownership.
2. Define dry-run, error reporting, duplicate handling, partial failure, and rollback behavior.
3. Add focused tests for valid rows, malformed booleans, missing references, duplicates, and retry safety.
4. Document operational prerequisites and recovery steps before calling the migration ready.
