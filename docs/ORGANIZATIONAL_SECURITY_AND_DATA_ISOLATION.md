# Organizational Security & Data Isolation Architecture

**Repository:** `AbdulrhmanBashammmakh/utility_erp`  
**Branch:** `development`  
**Reviewed SHA:** `bf951a05a6031e94192e692dacbeb9dd01ca035e`
**Documentation Version:** 3.2
**Reviewed Date:** `2026-08-24`
**Status:** CURRENT V1 IMPLEMENTED (Functional Roles + Company Scope + Unified Region/Branch Scope)

## 1. Purpose

Utility ERP must separate two independent security dimensions:

```text
Functional Authorization → What can the user do?
Organizational Scope     → On which company/region/branch data?

Effective Access = Role Permissions ∩ Company Scope ∩ Organizational Scope
```

The current source code proves the first dimension and parts of the second. It does **not** prove a complete Region/Branch isolation architecture for every model.

## 2. Current implementation findings

### CURRENT V1: functional roles

The authoritative Odoo groups are defined in `utility_core/security/utility_security.xml`:

```text
Readonly
├── Cashier
├── Collector
├── Technician
│   └── Field Inspector
├── Auditor
└── Supervisor
    └── Billing Manager
        └── Revenue Manager
            └── Utility Admin
```

`base.group_system` and `base.group_erp_manager` imply Utility Admin. These groups answer what a user may do; geography is not encoded in group names.

### CURRENT V1: existing scope controls

- `res.users.assigned_region_ids` exists and is a Many2many to `utility.region` restricted to records of type `region`.
- `res.users.assigned_route_ids` exists and is used by route-scoped customer, reading, sale-order, and payment-allocation rules for applicable operational roles.
- `company_id` and standard `company_ids` rules provide the existing company boundary on many models.
- Region-based rules exist for selected Auditor/customer/reading and financial allocation/settlement paths, with explicit Utility Admin bypass in those rules.
- Route-based rules exist for selected Collector/Technician paths.
- API ownership checks exist for portal/customer access and selected service/reading/billing endpoints.

### CURRENT V1: verified unified organizational isolation

The implementation has been unified and verified across Core and Operations:

- **`scope_mode = 'global' / 'restricted'` on `res.users`**: Defaults to restricted unless marked global or member of `group_utility_admin`.
- **`assigned_region_ids` & `assigned_branch_ids` on `res.users`**: Managed strictly by admins.
- **Scope resolution methods**:
  * `user._is_global_utility_scope()`: Returns True for Admin / System or explicit global mode.
  * `user._get_effective_region_ids()`: Returns assigned regions (or all regions if global).
  * `user._get_effective_branch_ids()`: Returns explicit branches plus all child areas of assigned regions (`parent_id in region_ids`).
- **Canonical Model Mapping**: `utility.region` with `type='region'` represents Region; `type='area'` represents the organizational Branch.
- **True Global Record Rules**: Rules for Customers, Readings, Meters, Service Orders, Work Orders, Installations, Inspections, and Alarms are defined as `global=True` with `groups=[(6, 0, [])]`. This guarantees strict logical conjunction (`AND`) with multi-company rules, preventing accidental bypass via group disjunction (`OR`).
- **Non-Destructive Staff Scope Sync**: When creating or updating `utility.staff`, if the staff record does not define a geographic region or area, it does not wipe out the user's existing assigned regions/branches. When a user is created with assigned regions/branches, they are seamlessly propagated to the staff profile.

## 3. Role-Based Authorization

Roles remain independent from geography:

```text
User
├── Role(s)
└── Organizational Scope
    ├── Company scope
    ├── Allowed Region(s)
    └── Explicit Branch(es), when policy allows
```

Do not create groups such as `Billing Manager Sana'a` or `Supervisor Aden`. They multiply ACL complexity and make role maintenance non-scalable.

## 4. Target organizational hierarchy

The target conceptual hierarchy is:

```text
Company
    ↓
Region
    ↓
Branch
```

The current implementation has:

```text
utility.region(type=region)
    ↓
utility.region(type=area)  # Branch
    ↓
utility.region(type=zone)
```

`area` is the business Branch level for this architecture. Do not create a duplicate Region/Branch model. User scope fields and Record Rules must reference the existing `utility.region` records with `type='area'`.

## 5. Target scope rules

### Region expansion

```text
Effective Branches
= Branches belonging to Allowed Regions
  + Explicitly Allowed Branches
```

An explicit additional branch must not grant access to the rest of its parent Region.

### Global versus restricted

`GLOBAL` must be explicitly granted by policy/group. Empty Region/Branch assignments must never imply global access.

Target examples include Utility Administrator, Central Auditor, Central Accounting Manager, and Executive Management, subject to verified business policy. Operational users should normally be `RESTRICTED`.

### V1 unified scope

For V1 hardening, prefer one unified organizational scope per user shared by all roles:

```text
User → Multiple Roles + One Organizational Scope
```

Do not implement `Role A → Region X` and `Role B → Region Y` unless a verified requirement makes that complexity unavoidable.

## 6. Canonical scope ownership

Current derivation paths that are supported by source code are:

| Entity | Current canonical path | Isolation status |
|---|---|---|
| Customer | `utility.customer → partner_id → partner.region_id / area_id / zone_id`, plus `route_id` | Partial current rules; `area_id` is Branch |
| Meter | computed from customer or transformer/feeder location | Company boundary current; full Region/Branch scope not proven |
| Reading | `account_id.region_id` or `meter_id.region_id`; route through account | Partial current Auditor/route rules |
| Reading Batch | explicit `region_id` plus creator/reader ownership in API | Ownership current; full user Region/Branch scope not proven |
| Bill | `sale.order.customer_id` and `route_id` | Route/company rules applicable; full Region/Branch layer not proven |
| Accounting Invoice | `account.move.utility_sale_order_id` | Do not add broad accounting rules without impact analysis |
| Payment | `account.payment.utility_sale_order_id` | Reach through controlled Utility relation |
| Service Order | customer/meter with related `region_id`/`area_id` (`area_id` = Branch) | Company boundary current; complete scope not proven |
| Work Order | customer/service-order context; no dedicated branch field | Requires derived scope review |
| Installation/Inspection | customer/service-order context; no dedicated branch field | Requires derived scope review |
| Alarm | `area_id` with related `region_id` (`area_id` = Branch) | Company boundary current; complete scope not proven |
| Write-off/Adjustment | sale order/customer financial relation | Requires controlled financial scope review |

Avoid independently editable `region_id` values that can contradict the canonical parent context. If denormalized scope fields are later needed for security/performance, they must be derived, readonly, indexed where justified, and never become a second business truth.

## 7. Enforcement architecture

The target enforcement chain is:

```text
Odoo Groups
    ↓
ACL
    ↓
Company Record Rules
    ↓
Organizational Record Rules
    ↓
Server-side Action Validation
```

The same restrictions must hold through UI, RPC, API, import, wizards, and server actions. UI domains and hidden menus are usability controls, not security boundaries.

Multi-record wizards and high-impact actions must validate all target records' effective scope server-side; Record Rules alone may not be sufficient.

## 8. Accounting considerations

Organizational scope must not create an Account, Journal, Receivable, or parallel ledger per Region unless a genuine accounting requirement is approved. `account.move` and `account.payment` remain standard Odoo financial truth.

Restricted Billing users should reach invoices/payments through controlled Utility relations. Broad `account.move` rules must be reviewed against posting, reconciliation, allocation, reports, and central accounting users before implementation. Global accounting visibility must be explicit and policy-driven.

## 9. API, dashboards, and reporting

Any `sudo()` used by API, dashboard, report, or media code must restore the authenticated user's company and organizational scope before resolving user-supplied identifiers. Never process `sudo().browse(user_supplied_id)` without explicit scope validation.

Aggregates, `search_count`, `read_group`, exports, dashboards, and reports must use the same effective scope:

```text
Restricted KPI = records inside the user's effective scope
Global KPI     = all authorized company records
```

The current dashboard and API code contains region-aware queries and ownership checks, but a complete user-assigned Region/Branch scope contract is not yet proven for all paths.

## 10. Security matrix: two axes

| Role | Functional capability | Target organizational scope |
|---|---|---|
| Meter Reader | Submit readings | Assigned Regions/Branches |
| Technician | Execute field work | Assigned Regions/Branches |
| Supervisor | Assign/approve operations | Assigned Regions/Branches |
| Billing User | Billing operations | Assigned Regions/Branches |
| Billing Manager | Billing approval/management | Assigned scope or explicit Global |
| Auditor | Read-only audit | Assigned scope or explicit Global |
| Utility Admin | System administration | Explicit Global by policy |

The role names above map to current Odoo groups where verified; the unified branch/global scope is target hardening.

## 11. Required implementation review before rollout

Before converting this target into code, review every scoped model for:

| Model | Company boundary | Canonical Region source | Canonical Branch source | Applicable roles | Global bypass | Create/write validation |
|---|---|---|---|---|---|---|
| `utility.customer` | Current company rule | partner/customer relation | `area_id` (`type='area'`) | role + scope | explicit policy | validate move/create |
| `utility.meter` | Current company rule | customer/technical hierarchy | derived `area_id` (`type='area'`) | technician/supervisor | explicit policy | validate assignment |
| `utility.reading` | Current company + partial route/region rules | account or meter | derived branch decision | reader/reviewer/billing | explicit policy | validate submitted target |
| `sale.order` | current company/route behavior | customer | customer/branch decision | billing roles | central accounting policy | validate bill action |
| `utility.service.order` | current company rule | customer | customer/branch decision | operations roles | explicit policy | validate action targets |
| `utility.work.order` | current company rule | parent/customer | parent/branch decision | technician/supervisor | explicit policy | validate assignment |
| `utility.writeoff` | current company boundary | customer/sale order | customer/branch decision | billing/admin | controlled financial policy | validate approval/apply |

## 12. Cross-scope UAT scenarios

- Same role in Region A cannot read/write/assign/approve Region B records.
- A user assigned Regions A+B can access both but not Region C.
- Regions A plus explicit Branch B-02 grants all A branches and only B-02, not B-01/B-03.
- Explicit `GLOBAL` can access all permitted company records.
- `RESTRICTED` with no assigned regions/branches sees no scoped operational records and is never treated as global.
- Sensitive wizards cannot mutate out-of-scope Customer, Meter, Route, Transformer, Feeder, Replacement, or operational records.
- Valid but out-of-scope API identifiers are rejected.
- Lists, dashboards, exports, reports, and aggregate counters do not leak out-of-scope data.
- Accounting central roles retain required posting/reconciliation capability after any Utility scope rules are introduced.

## 13. Audit requirements

Record role changes, scope assignments, global grants, branch/region hierarchy changes, denied cross-scope attempts, and high-impact cross-record actions. Scope changes should be traceable to an approver and effective date.

## 14. Future extensions

Per-role scopes, delegated temporary scope, branch-level approval routing, and more granular organization units are **TARGET / FUTURE OPTIONAL DESIGN**. They must not be added to V1 without evidence that unified user scope is insufficient.
