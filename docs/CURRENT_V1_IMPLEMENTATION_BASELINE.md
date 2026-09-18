# Current V1 Implementation Baseline

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Branch:** `development`
**Reviewed SHA:** `b97bea78aaba6b91575dd9b8cd2c14d685c64fd5`
**Commit:** `b97bea7 dev ++ ----------- + connect security +2 uint test 3`
**Reviewed Date:** 2026-09-18
**Documentation Version:** 3.3
**Status:** CURRENT V1 implementation truth (Including Organizational Region/Branch Isolation)

This document answers: **what is actually implemented now?** It does not describe speculative V2 scale infrastructure.

## 1. Current module chain

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

`utility_prepaid` is **OUT OF SCOPE** for the V1 release boundary.

## 2. Sources of truth and ownership

- Odoo/PostgreSQL is the operational System of Record.
- `utility_core` owns the persisted operational `utility.reading` model and core validation hooks.
- `utility_billing` extends the same model with commercial fields and behavior: `is_billable`, `billing_anchor_id`, `billing_component_ids`, `included_sale_order_id`, `carried_consumption`, `billing_consumption`, and `billing_error`.
- Billing does not move commercial reading fields back into Core and Core does not dynamically detect whether Billing is installed.
- Standard Odoo `stock.lot`/stock movements remain physical inventory truth; `utility.meter` is the logical operational meter identity.
- Standard Odoo `account.move` and `account.payment` remain financial truth. There is no parallel ledger and no customer wallet.
- `utility_core` provides structured attachment storage in `ir.attachment` via deterministic folder hierarchy (`module/model/YYYY/MM/DD/checksum`) and legacy path compatibility.

## 3. Current workflows

### Reading and Reading Review Console

The compatible V1 state set is:

```text
draft → under_review → approved → queued → billed
                         └──────→ error
```

`billing_state` is not a current implementation field; any separation is TARGET / FUTURE OPTIONAL DESIGN.

- **Approval-to-Invoice Automation:** When an operational supervisor approves a commercial billable periodic reading (`is_billable = True`), it transitions through `queued` and immediately triggers automated bill generation (`action_generate_bill` guarded by savepoint). The system auto-resolves the active reading period `date.range`, confirms the `sale.order` bill (`state = 'sale'`), creates and posts the customer invoice (`account.move` with `state = 'posted'`), and marks the reading `state = 'billed'`. If billing configuration is missing, the reading safely remains in `queued` with error logged in `billing_error`.
- **Network Readings Isolation:** Network readings for public transformers (`transformer_id` with `not is_private`) and feeders (`feeder_id`) have `is_billable = False`. Upon approval, they remain in `state = 'approved'` as physical/technical records and never enter the billing queue or generate sale orders.
- **Image Review Gate:** Approving a reading strictly requires `image_state == 'clear'`. Attempting to approve an unverified or blurry image raises a `ValidationError`.
- **Review Console Workspace Scope:** The Reading Review Console (`utility.reading.review.service`) features dedicated tabs (Commercial, Transformers, Feeders, Replacements) and status filters. The "معتمدة" (Approved) filter tab and KPI cards aggregate `['approved', 'queued', 'billed']`, ensuring approved technical and billed commercial readings remain continuously visible in the workspace. In-row controls allow operators to mark image status (`clear`, `not_clear`, `not_same`, `loss_read`) and inspect images via lightbox.


### Reading Batch

`utility.reading.batch` uses bounded background processing through Cron, ownership validation, total validation, malformed JSON validation, eligible-period filtering, and concurrency control using `FOR UPDATE NOWAIT` with SQLSTATE `55P03` handling. The lifecycle is:

```text
uploaded → processing → done
                    ├── partial
                    └── error
```

The current operational UI exposes `total_readings`, `processed_count`, `error_count`, `image_count`, `progress_percent`, active-batch default filtering, and a needs-attention filter.

### Billing and accounting

The commercial Bill is represented by `sale.order`; an Accounting Invoice is `account.move`. The current Bill form provides direct navigation to related accounting invoices, payments, and billing adjustments.
- **Progressive Billing & Multi-Meter Replacement:** Multiple meter replacements within the same billing cycle produce a single `sale.order` bill. Each meter contributes an immutable `utility.bill.reading.component` tracking its segment consumption and dates, while total consumption is calculated across progressive tariff blocks (`block`) seamlessly.
- **Targeted Payment Allocation:** Payments are strictly allocated to the selected invoice. Partner-wide arbitrary reconciliation is rejected. Overpayments exceeding the invoice residual raise `ValidationError`. Cancelling an allocation cleanly un-reconciles entries and restores the original invoice residual without cross-invoice contamination.
- **Block Discounts & Sponsor Fund Integration:** Multi-tier block discounts calculate energy relief per tier. Supported subscriber categories (`sub_category_public`, `sub_public_tenant`) are linked to `partner_sponsor_fund` ("الصندوق"), enabling precise tracing of subsidized energy units and amounts on the bill and accounting entries.

### Contract template versioning, clone wizard, and immutable pricing snapshot

- **`utility.contract.template.version`**: Authoritative immutable version record owned by `utility_core`. Any modification to a contract template already referenced by a bill automatically generates a new version (V1 → V2), while unbilled templates update in place. Direct edits and deletions on used versions are strictly blocked with `UserError`.
- **`utility.contract.template.clone.wizard`**: Professional transient wizard allowing authorized users (Billing Managers/Admins) to create a new, completely independent Contract Template by copying pricing, lines, blocks, discount configurations, local fees, and workflow settings from an existing template. The new template receives a unique name/code, its own fresh Version 1 (V1), clean history isolation, and optional geographic overrides without mutating the source or historical billing records.
- **Dynamic Blocks & Context Guard**: `skip_tier_validation` context guard is supported during programmatic block replacement/creation, preventing false constraint errors when rearranging pricing tiers.
- **`utility.bill.pricing.snapshot` & `utility.bill.pricing.block`**: Immutable pricing and formula calculation evidence recorded on each `sale.order` bill by `utility_billing`. Captures energy, service, local fee, discount, and private transformer amounts, along with exact applied pricing block breakdown. Once the bill is confirmed, pricing snapshots and their block lines are locked against direct mutation.
- **Audit Chain**: `Customer -> Contract Template -> Contract Version -> Reading -> Reading Snapshot (Component) -> Pricing Snapshot -> Sale Order -> Invoice -> Accounting`.
- **Pricing Modes**: `flat`, `tier` (single tier), and `block` (progressive tier) are fully supported. `seasonal` and `tou` modes are explicitly unsupported in V1 and blocked with `ValidationError`.

### Settings and UI Streamlining
- Redundant and inactive settings cards have been pruned from the operational settings forms:
  * Removed "الإنذارات والتنبيهات" (Alerts and Notifications) from `utility_core`.
  * Removed "الغرامات والتأخير" (Penalties and Late Fees) and "الفصل التلقائي" (Automatic Disconnection) cards from `utility_billing`.
  * All underlying model fields and backend `ir.config_parameter` hooks are preserved with deterministic defaults (e.g. 1.5% penalty rate, 30% max penalty, 90 days disconnection threshold) ensuring zero runtime disruption.

### Payment gateway

The callback path verifies the transaction and token before taking the row lock, uses constant-time comparison where applicable, allows only pending transitions, sanitizes callback payloads, requires a provider reference for successful settlement where applicable, and is idempotent for repeated successful callbacks. The intended artifact invariant is one successful callback → one `account.payment`.

### Write-off

```text
draft → approved → applied → linked Credit Note
           └──────→ draft   (only before financial application)
```

Approval requires `draft`; application requires `approved`; `FOR UPDATE`, existing `move_id`, `copy=False`, readonly evidence, and restricted deletion prevent duplicate financial artifacts. After application, reopening, re-approval, and re-application are forbidden. One write-off creates at most one generated Credit Note.

### Collector settlement and bank deposit

The implemented V1 custody/deposit lifecycle is:

```text
collection posted
  → collector settlement confirmed and posted
  → bank settlement confirmed, automatically allocated, posted, and settled
```

`utility.collection.settlement` supports explicit allocation and deterministic
oldest-first allocation when no lines are supplied. `utility.bank.settlement`
accepts the collector and deposit amount, allocates open collector settlements
using bank reference priority followed by FIFO, creates the bank-journal entry,
and performs exact partial reconciliation through the deposit clearing account.

The legacy bank-statement matching path is not part of the current model or UI:
there is no `waiting_bank_match` state, `statement_line_id`, or
`action_reconcile`. `action_post` remains an internal idempotent recovery entry
point, while the user-facing confirmation action executes the business event.
Automatic entries carry a company-scoped unique `settlement_key`; duplicate
creation is rejected by the database constraint.

### Operations, field management, and inventory

- **`utility.route.assignment.wizard`**: Transformer-based route assignment wizard allowing supervisors to select transformers, automatically aggregate connected active customers, select field staff (`res.users`), and assign/add/replace customers on existing or newly generated routes.
- **`utility.meter.reader`**: Dedicated Meter Reader entity linking `res.users` with assigned routes, tracking mobile/staff credentials, and keeping route assignments synchronized with user scopes and mobile APIs.
- Critical operational forms use named action transitions with readonly state fields and non-clickable statusbars. Installation, work order, inspection, and alarm lifecycles expose terminal/error paths in the UI. Meter replacement is an operational orchestration over standard stock movements and requires explicit confirmation before immediate execution.

## 4. Security and migration

- Sensitive operational wizards no longer grant broad `base.group_user` access. Supervisor-access operations are separated from admin-only network/master creation.
- Important operations include server-side `AccessError` guards where implemented; UI groups are not the sole security boundary.
- API ownership checks restrict records to the authorized customer/user scope.
- Migration staging is persistent, bounded, retryable, lock-aware, and traceable to source data. Manual Run Now remains an admin-only/test-oriented path where present; normal processing is background-driven.

## 5. Current API contract and Mobile Integration

Verified billing and Reader API hardening uses this normalized error envelope on updated endpoints:

```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "error": "..."
}
```

- Mobile API endpoints (`/api/v1/reader/...` and `/api/v1/auth/...`) support dynamic user roles, subscriber listing by assigned routes, offline sync payload generation, and batch confirmation.
- Reader confirmation translates expected `AccessError`, `UserError`, and `ValidationError` into deterministic business errors. Unexpected database/integrity/programming failures are not the desired generic business response.

## 6. Evidence and limits

- **Test Suite Inventory:** 6 modules, **76 test files**, and **542 test methods**, with **100% test discovery** verified across `date_range`, `utility_core`, `utility_inventory`, `utility_operations`, `utility_billing`, and `utility_prepaid`.
- **Verified Business Logic Test Suites:**
  * Progressive billing & multi-meter replacement: `test_billing_progressive_and_replacement_business_logic.py`
  * Targeted payment allocation, unreconciliation & write-off: `test_accounting_payment_and_settlement_business_logic.py`
  * Meter replacement lifecycle & validation constraints: `test_operations_meter_lifecycle_business_logic.py`
  * Multi-tier block discounts & sponsor fund tracing: `test_block_discount_business_logic.py`
  * Core infrastructure settings: `test_utility_infrastructure_settings.py`
- This document records verified implementation and test suite coverage at commit `b97bea7`. It distinguishes static code evidence and unit test inventory from end-to-end production load validation.

**DEFERRED:** runtime/CI proof, production-scale load validation, and `stock.quant` N+1 optimization until profiling confirms meaningful impact.

## Security baseline qualification

Functional roles are CURRENT V1. The current code also has user-assigned Regions and Routes plus selected company/region/route rules. A complete unified `GLOBAL/RESTRICTED` Region/Branch isolation layer is not currently implemented/proven; it is **TARGET V1 SECURITY HARDENING**. The canonical `utility.region` hierarchy is `region/area/zone`, where `area` is the organizational Branch; there is no separate Branch model or user-level explicit Branch assignment yet.
