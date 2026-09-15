# Manual Production Release Gate Checklist & Command Reference

This document defines the repeatable pre-deployment validation procedures for **Utility ERP** on single-company production deployments without CI infrastructure.

---

## 3-Tier Production Release Validation Commands

Execute all 3 validation tiers sequentially prior to deployment release:

### Tier A — Fresh Database Installation Gate
Validates clean database installation order (`date_range` -> `utility_core` -> `utility_inventory` -> `utility_operations` -> `utility_billing`):

```bash
python c:\odoo\odoo\odoo-bin -d utility_test_fresh \
  -i date_range,utility_core,utility_inventory,utility_operations,utility_billing \
  --test-enable \
  --stop-after-init
```

### Tier B — Tagged Automated Test Suite Gate
Executes targeted production hardening regression tests using `--test-tags`:

```bash
python c:\odoo\odoo\odoo-bin -d utility_test_db \
  -u utility_core,utility_inventory,utility_operations,utility_billing \
  --test-enable \
  --test-tags utility_release \
  --stop-after-init
```

### Tier C — Staging Database Upgrade Gate
Validates module upgrade behavior on existing staging database copies:

```bash
python c:\odoo\odoo\odoo-bin -d utility_test_upgrade \
  -u date_range,utility_core,utility_inventory,utility_operations,utility_billing \
  --stop-after-init
```

---

## Manual Pre-Deployment UAT Checklist

| # | Validation Item | Requirement | Verification Method | Status |
|---|---|---|---|---|
| 1 | **Fresh Installation** | Zero XML, dependency, domain, or model errors | Tier A Command | [x] Pass |
| 2 | **Staging Upgrade** | Upgrade succeeds without database corruption or lost records | Tier C Command | [x] Pass |
| 3 | **Automated Tests** | All `@tagged('utility_release')` unit tests pass | Tier B Command | [x] Pass |
| 4 | **Gateway Idempotency** | Duplicate webhooks return safe idempotent status without double payment | Test Suite | [x] Pass |
| 5 | **Invoice Residual Locking** | Concurrent payments cannot drive residual balance negative | Test Suite | [x] Pass |
| 6 | **Accounting Integrity** | `accounting_balance` strictly matches posted unreconciled receivables | Test Suite | [x] Pass |
| 7 | **Meter Serial Constraints** | `lot.product_id == meter.product_id` and single active serial enforced | Test Suite | [x] Pass |
| 8 | **Route Access Default Deny** | Unassigned routes grant zero records to unprivileged field staff | Security Rules | [x] Pass |
| 9 | **API Backward Compatibility** | `/api/v1` payloads match existing integration structures | API Tests | [x] Pass |
| 10 | **Log Integrity** | No raw secrets, passwords, or authentication tokens logged | Log Inspection | [x] Pass |

---

## Technical Release Sign-off

- **Environment**: Single Company Odoo 16.0
- **Modules Included**: `date_range`, `utility_core`, `utility_inventory`, `utility_operations`, `utility_billing`
- **Modules Excluded**: `utility_prepaid` (Future Phase)
- **Validated By**: Lead Odoo Architect & Security Engineer
- **Release Verification Date**: August 12, 2026
- **Release Status**: ✅ **APPROVED FOR PRODUCTION RELEASE** (100% Green across Tier A, Tier B, Tier C Release Gates)
