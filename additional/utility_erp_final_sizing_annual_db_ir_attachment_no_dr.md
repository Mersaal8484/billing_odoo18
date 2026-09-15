# Utility ERP — Final Production Sizing

## Annual Database Rotation + `ir.attachment` + No DR

**Scope:** 300,000 electricity customers, 1,100–2,500 internal users, design target of 600–750 concurrent users, up to 7.2 million meter readings/year, image retention limited to 365 days.

**Classification:** TARGET V2 / CONDITIONAL. This is a production sizing proposal, not evidence that the topology, annual rotation, capacity, no-DR posture, or shared Filestore has been deployed or runtime-validated. The execution sequence is documented in [`docs/PRODUCTION_SIZING_IMPLEMENTATION_PLAN.md`](docs/PRODUCTION_SIZING_IMPLEMENTATION_PLAN.md).

---

## 1. Final Architectural Decisions

1. The active Odoo database covers **one operational year only**.
2. At year-end, the database is closed, made read-only, archived, and a new operational database is created.
3. Archived databases are not part of the live PostgreSQL working set.
4. Images remain subject to the **365-day maximum retention** even after the corresponding operational database is archived.
5. **No DR site** is included in this sizing.
6. Local HA is retained for critical runtime services where justified: PostgreSQL, Redis, load balancing, and Temporal persistence.
7. MinIO is **not required initially** for this workload.
8. Use standard Odoo `ir.attachment` with a shared Odoo filestore for image bytes; do **not** intentionally place the image payload inside PostgreSQL.
9. The shared filestore must be accessible consistently from all Odoo nodes.
10. Keep `utility.media.asset` or an equivalent business metadata/audit model so image bytes can be deleted after 365 days without losing reading/audit history.

---

## 2. Why MinIO Can Be Removed Initially

The upper workload assumption is 7.2 million readings/year. At an original image average of 100 KB, originals are roughly 720 GB/year. Even using the earlier working assumption of Original + Review + Thumbnail + overhead, logical annual image storage was estimated at roughly 1.584 TB.

Because image bytes do not need to survive beyond 365 days, an eight-node object-storage cluster is disproportionate to the current requirement unless object storage will later serve additional applications, public APIs, very large images, immutable data, or materially larger customer volumes.

The simpler initial design is:

```text
Odoo Application / Job Nodes
        ↓
     ir.attachment
        ↓
 Shared Odoo Filestore
        ↓
  HA NAS / Shared Storage
```

MinIO can remain an architectural extension point through `object_storage_connector`, but it does not need to be deployed in the first production phase.

---

## 3. Important Rule for Annual Database Archiving

Database archiving and image retention must be treated as separate lifecycles.

```text
Operational Year Ends
        ↓
Database becomes Read-Only
        ↓
Database archive retained according to company policy

Image uploaded_at + 365 days
        ↓
Delete image bytes from filestore
        ↓
Retain reading metadata + deletion audit
```

Do not preserve old image bytes forever simply because the annual database was archived.

If the archived database is reopened later, historical readings may therefore show that the evidence image has expired according to retention policy rather than exposing the original file.

---

## 4. Final Recommended Logical Resources

| Component | Qty | Recommended resources per node | Notes |
|---|---:|---|---|
| Load Balancer / Reverse Proxy | 2 | 4 vCPU, 8 GB RAM, 100 GB SSD | Active/Standby or Active/Active |
| Odoo Application | 3 | 24 vCPU, 64 GB RAM, 250 GB NVMe | Sized for 600–750 concurrent internal users |
| Odoo Job / Media | 2 | 8–12 vCPU, 32 GB RAM, 250 GB NVMe | Cron, media processing, retention, outbox |
| PgBouncer | 2 | 2–4 vCPU, 4–8 GB RAM | Can be colocated with LB/utility VMs if desired |
| PostgreSQL Primary | 1 | 24–32 vCPU, 128 GB RAM, 2 TB enterprise NVMe | Active-year Odoo DB only |
| PostgreSQL Standby | 1 | Same as Primary | Local HA, not DR |
| PostgreSQL Witness/Controller | 1 | 2 vCPU, 4 GB RAM | Small VM |
| Redis Session | 3 | 4 vCPU, 8 GB RAM, 50–100 GB SSD | Primary + replicas + Sentinel |
| Shared Odoo Filestore | 1 HA storage service | 4 TB usable initially | RAID/protected shared storage; expandable |
| Temporal Gateway | 2 | 2–4 vCPU, 4–8 GB RAM | Lightweight |
| Temporal Services | 3 | 4–8 vCPU, 8–16 GB RAM | Current workload is moderate |
| Temporal PostgreSQL | 2 | 8 vCPU, 16–32 GB RAM, 500 GB–1 TB NVMe | Primary + standby |
| Temporal DB Witness | 1 | 2 vCPU, 4 GB RAM | May share small infrastructure VM |
| Utility Temporal Workers | 2 | 8 vCPU, 16 GB RAM | Scale horizontally during billing/reading batches |
| Monitoring / Logs | 1 | 8 vCPU, 32 GB RAM, 2 TB storage | HA optional for monitoring |
| Backup / Annual Archive Repository | 1 | 8 vCPU, 32 GB RAM, 12 TB usable initially | Expand according to number of archived years; not DR |

---

## 5. PostgreSQL Sizing After Annual Rotation

The earlier 4 TB per PostgreSQL node was intentionally conservative for a multi-year live database. With yearly closure, the active production database only accumulates one year of readings, invoices, accounting data, workflow records, audit events, indexes, and normal bloat.

A better starting point is therefore:

```text
Primary:  24–32 vCPU / 128 GB RAM / 2 TB NVMe
Standby:  24–32 vCPU / 128 GB RAM / 2 TB NVMe
```

Use 4 TB only if actual yearly database growth tests show that 2 TB does not preserve sufficient free space, WAL working room, maintenance headroom, and index/bloat reserve.

The yearly close procedure should include VACUUM/ANALYZE as appropriate, integrity checks, final backup, archive catalog registration, read-only controls, and a tested restore procedure.

---

## 6. `ir.attachment` Storage Recommendation

Use `ir.attachment` as the Odoo ownership/API layer, with the binary payload in the Odoo filestore rather than intentionally storing image bytes inside PostgreSQL.

For multiple Odoo application nodes, the filestore must behave as shared durable storage so a file written by one node can be retrieved by another node behind the load balancer.

Recommended initial usable capacity:

```text
4 TB usable shared filestore
```

This is comfortably above the previous 1.584 TB/year logical image estimate and leaves room for reports, non-meter attachments, temporary processing, and operational headroom.

If field measurements later show original images are materially larger than expected, expand shared storage to 6–8 TB before reconsidering object storage.

---

## 7. When to Reintroduce MinIO

MinIO should be reconsidered when one or more of the following becomes true:

- The platform starts storing many classes of large objects beyond meter-reading images.
- Average image size grows substantially.
- Public/mobile traffic requires direct presigned upload at significantly higher scale.
- Image retention becomes multi-year.
- Object immutability/versioning becomes a formal requirement.
- Shared filestore IOPS/metadata performance becomes a measured bottleneck.
- Capacity grows beyond the practical limits of the selected shared-storage platform.

Until one of those triggers occurs, `ir.attachment` + shared filestore is the simpler production design.

---

## 8. Physical Server Consolidation — Recommended

The logical services above do not require one physical server per service.

### Compute Cluster

**3 physical virtualization hosts** are a reasonable production starting point:

```text
Each host:
32–48 physical CPU cores
256–384 GB RAM
2 × 1.92 TB NVMe mirrored for VM/system workloads
Dual 10/25 GbE
Redundant power supplies
```

They host Odoo, Redis, Temporal services/workers, load balancers, PgBouncer, and monitoring. Three hosts allow maintenance/failure of one host without requiring the former four-host compute design.

### Database Hosts

**2 dedicated PostgreSQL hosts**:

```text
Each host:
32 physical cores
192–256 GB RAM
2–4 TB usable enterprise NVMe
Dual 25 GbE preferred
```

The Odoo PostgreSQL Primary and Standby should reside on different physical hosts.

Temporal persistence can run as dedicated VMs on the compute cluster if isolation and I/O tests are satisfactory; otherwise place its primary/standby on separate DB hosts without colocating both primaries on the same failure domain.

### Shared Attachment / Archive Storage

Use a protected shared-storage platform with:

```text
4 TB usable fast shared filestore for active attachments
12 TB usable archive/backup capacity initially
10/25 GbE connectivity
RAID / redundancy
Snapshot capability where appropriate
```

The archive repository stores annual database archives and backups, but expired meter-reading image bytes must still be deleted according to the 365-day policy.

---

## 9. Final Production Footprint

A balanced deployment therefore becomes approximately:

```text
3 × Virtualization / Compute Hosts
2 × Dedicated PostgreSQL Hosts
1 × Shared HA Storage platform for active filestore + archive capacity

Logical services:
- 2 Load Balancers
- 3 Odoo Application instances
- 2 Odoo Job/Media instances
- 2 PgBouncer instances
- PostgreSQL Primary + Standby + Witness
- 3 Redis session nodes / Sentinels
- 2 Temporal Gateways
- 3 Temporal service instances
- Temporal PostgreSQL Primary + Standby + Witness
- 2 Utility Temporal Workers
- 1 Monitoring/Log instance
- Backup/Annual Archive repository
```

There is **no DR site** and **no MinIO cluster** in the recommended initial production footprint.

---

## 10. Final Decision

For the stated workload, annual database rotation materially changes the storage architecture.

The recommended baseline is:

```text
Odoo:
3 App nodes × 24 vCPU / 64 GB
2 Job nodes × 8–12 vCPU / 32 GB

PostgreSQL:
Primary + Standby
24–32 vCPU / 128 GB / 2 TB NVMe each
Annual operational DB rotation

Redis:
3 nodes × 4 vCPU / 8 GB

Attachments:
ir.attachment + shared filestore
4 TB usable initial capacity
365-day image retention
No image bytes in long-term annual archive

Temporal:
3 service nodes × 4–8 vCPU / 8–16 GB
2 workers × 8 vCPU / 16 GB
Temporal DB Primary + Standby

Infrastructure:
2 load balancers
1 monitoring node
1 local backup/archive repository
No DR
No MinIO initially
```

This design preserves application concurrency and local HA where it matters while removing the largest unnecessary object-storage footprint from the earlier proposal.
