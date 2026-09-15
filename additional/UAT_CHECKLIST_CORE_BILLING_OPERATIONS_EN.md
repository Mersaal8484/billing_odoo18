# UAT Checklist — Utility Core, Billing, and Operations

**System:** Odoo 16 Utility ERP  
**Modules:** `utility_core`, `utility_billing`, `utility_operations`  
**Environment / Database:** __________  **Build / Commit:** __________  
**Test Date:** __________  **UAT Lead:** __________  **Business Owner:** __________

## Execution Rules

Status values: `Not Tested`, `Passed`, `Failed`, `Blocked`, `Not Applicable`.

- **P0 — Critical:** Failure blocks release.
- **P1 — High:** Core business function; resolve before acceptance.
- **P2 — Medium:** Supporting function or usability issue.
- For every failure, record the defect ID, user, company, record reference, actual result, screenshot/log, and reproducible steps.
- A test is not passed merely because a record saves. Verify linked records, accounting impact, state transitions, access rights, and duplicate prevention.

## Entry Criteria and Test Data

- [ ] Install/upgrade Core, Operations, and Billing in dependency order without server errors.
- [ ] Configure two companies, currencies, receivable accounts, journals, taxes, products, and sequences.
- [ ] Create separate users for administrator, meter reader, billing officer, accountant, operations officer, technician, collector, and read-only auditor.
- [ ] Create a complete network hierarchy and at least two reading routes.
- [ ] Create two subscriber categories/types, two contract templates, and two tariff versions.
- [ ] Prepare postpaid customers with normal, opening-balance, overdue, suspended, and disconnected conditions.
- [ ] Prepare old/new meters with different multipliers and one meter assigned to another customer.
- [ ] Prepare two billing periods, including one period with a mid-cycle meter replacement.
- [ ] Take a database backup and control scheduled jobs during repeatability tests.

## 1. Installation, Configuration, and Multi-Company

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | CFG-001 | P0 | Install and upgrade the three modules. | No traceback, missing field, invalid XML, or duplicated menu/action. | |
| [ ] | CFG-002 | P0 | Create one record for each configured sequence. | Unique, correctly prefixed number by document type and company. | |
| [ ] | CFG-003 | P1 | Save Utility settings, reload, and switch companies. | Settings persist and remain company-specific. | |
| [ ] | CFG-004 | P0 | Switch from Company A to Company B. | Master and transactional data do not leak across companies. | |
| [ ] | CFG-005 | P1 | Run Core/Billing scheduled jobs twice on the same sample. | Jobs complete without errors or duplicate records. | |
| [ ] | CFG-006 | P1 | Archive a configuration record used historically. | Historical documents remain readable; record is unavailable for new work. | |

## 2. Network and Master Data

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | MDM-001 | P0 | Create region → area → zone → office → substation → feeder → transformer → route. | Valid hierarchy is saved and incompatible relationships are rejected. | |
| [ ] | MDM-002 | P1 | Create a cell and child transformers with coupling meter. | Hierarchy, feeder, and coupling-meter relationships are correct. | |
| [ ] | MDM-003 | P1 | Assign customers to routes and transformers. | Search, group-by, and route workload return the correct customers. | |
| [ ] | MDM-004 | P0 | Create subscriber category and subscriber type. | A type cannot be used with a different category. | |
| [ ] | MDM-005 | P0 | Configure contract template restrictions by category, type, region, and area. | Only compatible templates are shown and accepted server-side. | |
| [ ] | MDM-006 | P0 | Create a block tariff with consecutive thresholds. | Invalid, overlapping, or reversed blocks are rejected. | |
| [ ] | MDM-007 | P0 | Add a new tariff version with a future effective date. | Historical documents retain old values; new period uses effective version. | |
| [ ] | MDM-008 | P1 | Run a valid and invalid dynamic formula. | Correct result or safe user-facing validation; no ORM/context exposure. | |
| [ ] | MDM-009 | P1 | Create billing date ranges and link previous/current ranges. | Period order, dates, type, and current-period flag are consistent. | |

## 3. Customer, Contract, and Meter Management

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | CUS-001 | P0 | Create a postpaid customer with all mandatory data. | Unique customer number and valid partner, company, classification, and contract. | |
| [ ] | CUS-002 | P0 | Select a subscriber type outside the selected category. | Save is blocked with a clear validation message. | |
| [ ] | CUS-003 | P0 | Select an incompatible contract template. | Template is filtered out and rejected through ORM/RPC. | |
| [ ] | CUS-004 | P1 | Create a customer through the customer wizard. | Same validation and relationships as the full form. | |
| [ ] | CUS-005 | P0 | Edit an existing customer and attempt to change the meter. | Meter field is read-only; replacement is the only supported change path. | |
| [ ] | CUS-006 | P0 | Attempt to assign a meter outside the selected network/cell. | Assignment is blocked with an actionable message. | |
| [ ] | CUS-007 | P1 | Update customer mobile from the Utility account. | Partner is updated without creating a duplicate contact. | |
| [ ] | CUS-008 | P0 | Execute customer lifecycle actions. | Only valid Draft/Active/Suspended/Disconnected/Closed transitions occur. | |
| [ ] | CUS-009 | P1 | Open readings, bills, payments, and replacements smart buttons. | Counts, domains, and linked records are accurate. | |
| [ ] | MET-001 | P0 | Create duplicate meter numbers/serials. | Duplicate is rejected within the applicable company scope. | |
| [ ] | MET-002 | P1 | Print and scan single/bulk meter QR labels. | QR resolves to the correct meter and print layout is usable. | |

## 4. Reading Purposes and Approval Workflow

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | RDG-001 | P0 | Create an opening reading. | Opening sequence is used; no period required; consumption is zero; no bill. | |
| [ ] | RDG-002 | P0 | Create a periodic reading. | Periodic sequence is used and billing period is required before billing. | |
| [ ] | RDG-003 | P0 | Create a replacement-closing reading. | Closing sequence is used; period is optional; it cannot bill independently. | |
| [ ] | RDG-004 | P0 | Use manual, estimated, and AMI reading sources. | Source remains independent from commercial reading purpose. | |
| [ ] | RDG-005 | P0 | Execute Draft → Under Review → Approved → Billed. | Only valid transitions succeed; users and timestamps are captured. | |
| [ ] | RDG-006 | P1 | Reject a reading under review. | Reading returns to Draft with a recorded rejection reason. | |
| [ ] | RDG-007 | P0 | Directly edit an approved or billed reading. | Protected fields are locked; correction requires settlement workflow. | |
| [ ] | RDG-008 | P0 | Enter a value lower than previous reading without rollover handling. | Reading is rejected or flagged according to configured policy. | |
| [ ] | RDG-009 | P0 | Calculate reading on a meter with multiplier greater than one. | Consumption equals raw difference multiplied by the captured multiplier. | |
| [ ] | RDG-010 | P0 | Create a second periodic reading for the same account and period. | Duplicate is blocked even if the physical meter changed. | |
| [ ] | RDG-011 | P1 | Upload a batch containing valid and invalid rows. | Clear row-level result; successful rows are not duplicated on retry. | |
| [ ] | RDG-012 | P1 | Search/group readings by purpose, source, state, period, and route. | Results and totals are correct and responsive. | |

## 5. Meter Replacement and Carried Consumption

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | RPL-001 | P0 | Start replacement for an assigned meter. | Customer and old meter are derived correctly; unrelated meter is rejected. | |
| [ ] | RPL-002 | P0 | Enter closing value below last valid old-meter reading. | Completion is blocked with a clear message. | |
| [ ] | RPL-003 | P0 | Complete replacement with old closing and new opening values. | Correct closing/opening readings and purposes are created; customer gets new meter. | |
| [ ] | RPL-004 | P0 | Inspect old meter after replacement. | Old meter is removed/inactive while historical ownership remains auditable. | |
| [ ] | RPL-005 | P0 | Create first periodic reading on the new meter. | Carried consumption includes unbilled old-meter consumption. | |
| [ ] | RPL-006 | P0 | Bill a period containing one replacement. | One bill includes both old and new meter segments. | |
| [ ] | RPL-007 | P0 | Process two replacements before the next periodic reading. | All eligible closing segments are included once in chronological order. | |
| [ ] | RPL-008 | P0 | Retry bill generation for the same anchor reading. | No duplicate order or reading component is created. | |
| [ ] | RPL-009 | P1 | Review bill reading components. | Meter, values, period segment, multiplier, and consumption snapshots are clear. | |
| [ ] | RPL-010 | P0 | Cancel/reverse a bill containing carried components. | Components are handled consistently and never silently reused or stranded. | |

## 6. Postpaid Billing

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | BIL-001 | P0 | Generate a bill from an approved periodic reading. | One Sale Order links account, meter, period, tariff, and anchor reading. | |
| [ ] | BIL-002 | P0 | Validate energy, fixed, service, penalty, and tax lines. | Each charge appears once and matches contract/tariff configuration. | |
| [ ] | BIL-003 | P0 | Bill consumption crossing multiple tariff blocks. | Each quantity is priced in the correct block; total matches manual calculation. | |
| [ ] | BIL-004 | P0 | Bill a historical period after tariff changes. | Effective tariff/contract version for the period is used. | |
| [ ] | BIL-005 | P0 | Run period batch billing twice. | Only eligible periodic readings are billed and no duplicates are produced. | |
| [ ] | BIL-006 | P0 | Confirm Sale Order and create accounting invoice. | Partner, lines, accounts, taxes, due date, and amount are consistent. | |
| [ ] | BIL-007 | P0 | Exercise utility `bill_state` lifecycle. | Draft/Confirmed/Sent/Paid/Overdue/Cancelled reflects business events correctly. | |
| [ ] | BIL-008 | P0 | Verify opening balance and prior balance on bill. | Prior balance is correct and not included twice in payable lines. | |
| [ ] | BIL-009 | P0 | Print the customer bill. | Content fits one 290 mm × 70 mm page; summary charges are not repeated. | |
| [ ] | BIL-010 | P1 | Print bill with unusually many lines/long Arabic data. | No clipping, overflow, blank second page, or unreadable RTL text. | |
| [ ] | BIL-011 | P0 | Cancel a bill linked to a reading. | Reading, components, order, and accounting state remain consistent. | |
| [ ] | BIL-012 | P1 | Run recurring billing twice for the same due date. | Only one due document is created. | |
| [ ] | BIL-013 | P1 | Generate service-order charges. | Correct product/amount is billed once and linked to the service order. | |

## 7. Collections, Accounting, and Debt Management

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | PAY-001 | P0 | Register full payment. | Account Payment is linked; residual is zero; utility state becomes Paid. | |
| [ ] | PAY-002 | P0 | Register partial payment. | Residual decreases correctly and document remains partially outstanding. | |
| [ ] | PAY-003 | P0 | Submit zero, negative, or excessive payment. | Rejected or handled as approved credit policy without corrupting reconciliation. | |
| [ ] | PAY-004 | P0 | Cancel/reverse payment. | Receivable and utility state return correctly with auditable accounting entries. | |
| [ ] | PAY-005 | P1 | Print collection receipt. | Customer, reference, amount, method, user, and date are accurate. | |
| [ ] | PAY-006 | P0 | Open overlapping collector/cashier shifts for one user. | Overlap is rejected; close totals match recorded payments. | |
| [ ] | PAY-007 | P0 | Post customer opening balance and repeat the action. | Balance appears once and accounting entry is not duplicated. | |
| [ ] | PAY-008 | P0 | Run overdue update job. | Only eligible unpaid bills become overdue. | |
| [ ] | PAY-009 | P0 | Run late-penalty job twice. | One penalty/accounting invoice with correct product and account. | |
| [ ] | PAY-010 | P0 | Create installment plan and pay installments. | Schedule, residual, due dates, and states remain consistent. | |
| [ ] | PAY-011 | P0 | Process reading/financial settlement. | Controlled adjustment document is created; billed source is not directly edited. | |
| [ ] | PAY-012 | P1 | Approve write-off or deposit transaction. | Authorization, linkage, balance, and accounting effect are auditable. | |
| [ ] | PAY-013 | P0 | Reconcile customer statement with bills and payments. | Opening balance + debits − credits equals closing balance. | |

## 8. Field Operations

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | OPS-001 | P0 | Create service order with customer, location, team, technician, and date. | Unique reference and complete operational assignment. | |
| [ ] | OPS-002 | P0 | Attempt valid and invalid service-order transitions. | Sequential workflow is enforced server-side. | |
| [ ] | OPS-003 | P1 | Create and complete a work order from service order. | State, dates, result, technician, and materials synchronize correctly. | |
| [ ] | OPS-004 | P0 | Install a new meter. | Meter assignment/status updates and opening reading is created correctly. | |
| [ ] | OPS-005 | P0 | Disconnect and reconnect a customer. | Reasons, readings, dates, user, and customer/meter states are accurate. | |
| [ ] | OPS-006 | P1 | Complete field inspection with finding and attachment. | Inspection links to customer, meter, and originating order. | |
| [ ] | OPS-007 | P0 | Create and approve a tamper case with charge. | Approval is enforced and charge reaches billing once. | |
| [ ] | OPS-008 | P1 | Create, assign, acknowledge, and close an alarm. | Source, priority, owner, timestamps, and resolution are captured. | |
| [ ] | OPS-009 | P1 | Bill a completed service order twice. | One charge only; duplicate billing is blocked. | |
| [ ] | OPS-010 | P1 | Cancel an operation after linked records exist. | Invalid cancellation is blocked or dependencies are reversed safely. | |

## 9. Reports and Printouts

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | REP-001 | P0 | Generate customer statement for a date range. | Opening, movements, and closing balance match accounting. | |
| [ ] | REP-002 | P1 | Generate transformer/cell balance report. | Input, subscriber consumption, technical loss, and percentage are correct. | |
| [ ] | REP-003 | P1 | Run outstanding, overdue, billing, and collection reports. | Filters and totals reconcile with source records. | |
| [ ] | REP-004 | P1 | Filter reports by company, period, area, route, and state. | Scope is exact and cross-company leakage does not occur. | |
| [ ] | REP-005 | P1 | Export/print reports containing Arabic and English text. | RTL/LTR text, numbers, totals, and page breaks are readable. | |

## 10. Security, Audit, and Performance

| Done | ID | Priority | Test | Expected Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | SEC-001 | P0 | Log in with every business role. | Menus, records, fields, and actions match assigned authority. | |
| [ ] | SEC-002 | P0 | Meter reader attempts approval or billing through UI and RPC. | Server rejects unauthorized action. | |
| [ ] | SEC-003 | P0 | Company A user requests Company B record/report/export. | Multi-company record rules deny access everywhere. | |
| [ ] | SEC-004 | P0 | Unauthorized user attempts write-off, settlement, penalty, or cancellation. | Operation is denied and no partial data is created. | |
| [ ] | SEC-005 | P1 | Review creator, approver, cancellation user/date/reason. | Required audit information is available and consistent. | |
| [ ] | PRF-001 | P1 | Search, sort, and group 10,000 customers/readings/bills. | Response is within agreed target and no timeout occurs. | |
| [ ] | PRF-002 | P1 | Generate a large billing batch. | Batching completes without memory exhaustion and reports row-level failures. | |
| [ ] | PRF-003 | P1 | Run penalties/overdue jobs on realistic volume. | Jobs finish within window without duplicates or harmful locking. | |
| [ ] | PRF-004 | P0 | Concurrently bill the same reading or pay the same invoice. | Database/business controls produce one financial outcome only. | |

## 11. End-to-End Acceptance Scenarios

| Done | ID | Priority | Scenario | Acceptance Result | Status / Evidence |
|---|---|---|---|---|---|
| [ ] | E2E-001 | P0 | Customer → contract → meter installation → opening → periodic → bill → full payment. | All links, states, accounting, statement, and printout are correct. | |
| [ ] | E2E-002 | P0 | Previous periodic → mid-cycle replacement → new periodic → bill. | One bill includes old/new meter consumption exactly once. | |
| [ ] | E2E-003 | P0 | Unpaid bill → overdue → penalty → partial payment → full payment. | Residual, penalty, utility state, and statement reconcile. | |
| [ ] | E2E-004 | P0 | Service order → inspection → meter replacement → reading → billing. | Operations, readings, meter ownership, and billing remain consistent. | |
| [ ] | E2E-005 | P0 | Tamper case → approval → charge → invoice → collection. | Charge is authorized, billed once, paid, and traceable end to end. | |
| [ ] | E2E-006 | P0 | Company A and B process equivalent cycles concurrently. | Independent sequences, accounting, records, and reports. | |

## Defect Register

| Defect ID | UAT ID | Description | Severity | Owner | Status | Evidence Link |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |
| | | | | | |

## Execution Summary and Sign-Off

| Metric | Count |
|---|---:|
| Total test cases | |
| Passed | |
| Failed | |
| Blocked | |
| Not Applicable | |
| Pass rate | |
| Open P0 defects | |
| Open P1 defects | |

Recommended acceptance criteria:

- 100% of P0 cases passed and no open P0 defect.
- At least 95% of applicable P1 cases passed, with approved closure dates for exceptions.
- No unexplained financial variance in bills, payments, penalties, or customer statements.
- Multi-company isolation, access control, auditability, and duplicate-prevention tests passed.

| Role | Name | Decision | Date | Signature / Comment |
|---|---|---|---|---|
| Business Owner | | Accept / Conditional / Reject | | |
| Billing Lead | | Accept / Conditional / Reject | | |
| Finance Lead | | Accept / Conditional / Reject | | |
| Operations Lead | | Accept / Conditional / Reject | | |
| IT / Security Lead | | Accept / Conditional / Reject | | |
| Project Manager | | Release / Hold | | |
