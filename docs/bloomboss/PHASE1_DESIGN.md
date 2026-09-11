# BloomBoss Phase 1 — Historical Data Intelligence

Status: **IMPLEMENTATION STARTED IN ISOLATED DEVELOPMENT BRANCH**

## Goal
Turn 7–9 months of BloomBoss purchase/sales history into a canonical, auditable dataset without inventing missing values.

## Directory structure
- `bloomboss/models.py` — canonical domain records
- `bloomboss/ingest.py` — canonical CSV ingestion
- `bloomboss/history.py` — exact-source fingerprint + reproducible inspection snapshot
- `bloomboss/analytics.py` — first reproducible business metrics
- `bloomboss/data_quality.py` — completeness/coverage reporting for reconstructed history
- `bloomboss/validation.py` — cross-record contradiction/reference validation
- `tests/test_bloomboss_phase1.py` — targeted Phase 1 behavior tests
- `tests/test_bloomboss_history_snapshot.py` — source-fingerprint/snapshot tests
- `docs/bloomboss/PERSISTENCE_DESIGN.md` — durable persistence design only; no database implementation

## Historical import format
One row per plant/inventory unit. Batch-level values may repeat across rows for the same batch. Blank values mean UNKNOWN, never zero.

Required columns: `batch_id`, `unit_id`, `cultivar`, `status`.

## Data authority
For Phase 1, imported historical source rows are evidence. Canonical in-memory records are normalized representations. Production persistence is intentionally deferred.

`inspect_history_csv()` now records the exact source filename, byte size, and a streaming SHA-256 fingerprint alongside the canonical records, relationship findings, analytics, supplier outcomes, and completeness metrics. The fingerprint identifies the raw evidence used for a result without mutating or copying that source.

The system reports both business metrics and **coverage metrics**. This prevents a partially reconstructed history from appearing more complete than it is. Missing values remain missing; coverage tells us how much of each field is actually known.

Current coverage reporting includes supplier, purchase date, quantity, full batch landed cost, unit cost basis, acquisition date, unit status, sale date, selling fees, outbound shipping, net revenue, and sold-unit cost basis.

## Cross-record validation
Canonical records are checked for contradictions that would make business analytics misleading while still allowing legitimate historical unknowns.

Current checks report:
- unit references a missing purchase batch;
- unit cultivar conflicts with its purchase batch cultivar;
- sale references a missing inventory unit;
- sale exists for a unit marked lost or giveaway;
- sale date precedes acquisition date;
- more than one sale record exists for the same unit.

Validation reports issues and does not mutate or auto-repair historical evidence.

## Durable persistence direction
`docs/bloomboss/PERSISTENCE_DESIGN.md` defines the next safe boundary before any database implementation: immutable raw-source evidence, SHA-256 source identity, replay identity based on source digest + parser version, canonical tables separated from raw evidence, explicit import-run state, and no partial promotion after structural parse failure.

This remains design-only. No production database, migration, deployment, secret, or external action is authorized by Phase 1.

## Acceptance criteria
1. Missing historical financial values remain `None`/unknown.
2. Invalid dates/decimals/statuses fail visibly.
3. A sale cannot have a price without a channel.
4. Analytics are reproducible from canonical records.
5. Initial metrics cover revenue, known landed cost, realized gross profit on known costs, sell-through, loss rate, average sale price, average days-to-sale, channel performance, cultivar performance, supplier performance, and capital tied up in active unsold inventory.
6. Historical-data completeness is measurable without imputing missing values.
7. Cross-record contradictions are reported without silently repairing or inventing historical facts.
8. An inspection snapshot fingerprints the exact raw source and combines canonical records, validation, analytics, supplier outcomes, and completeness without changing the source.
9. No production, marketplace writes, OBS, or external customer actions.

## Invariant Impact Review
Phase: BloomBoss Historical Data Intelligence v1

- I-01 Inheritance/compatibility: AFFECTED — must tolerate incomplete historical records.
- I-02 Production parity: NOT AFFECTED — isolated development only; production design deferred.
- I-03 Data authority/transactions: AFFECTED — raw historical source remains evidence; canonical records are derived and the exact source is fingerprinted.
- I-04 Idempotency/retry: AFFECTED — stable batch/unit/sale IDs are required; future durable replay identity is source SHA-256 + parser/schema version.
- I-05 Resources/scale: AFFECTED — current loader is bounded by file size; source hashing is chunked; streaming/persistence review remains required before production-scale ingestion.
- I-06 Migration/rollback: AFFECTED — raw source is preserved separately so normalization can be rebuilt; persistence design explicitly requires mixed-state compatibility.
- I-07 Observability: AFFECTED — malformed rows fail visibly; provenance records source row; coverage metrics expose reconstruction gaps; cross-record validation emits explicit issue codes/entity IDs; snapshots expose source identity.
- I-08 Validation scope: AFFECTED — targeted Phase 1 tests only.
- I-09 Authority/permissions: AFFECTED — Phase 1 is READ/LOCAL NORMALIZATION only; no external writes/actions.

Known inherited assumptions: existing KARMO foundation is not modified.
Legacy-data considerations: missing historical fields are expected and must remain unknown.
Authoritative data stores: historical source files are source evidence for this isolated phase.
Transaction/failure boundaries: single local CSV parse; failed rows abort the load rather than partially reporting success. Future durable boundary is specified separately, not implemented.
Scale considerations: sufficient for initial 7–9 month reconstruction; production streaming/pagination deferred; hashing is bounded by chunk size.
Runtime/dependency requirements: Python standard library only.
Migration/mixed-state requirements: none in production; canonical format remains rebuildable from raw source. Future durable design must tolerate older nullable records.
Observability requirements: row-level provenance, source fingerprint, explicit validation errors, issue codes/entity IDs for cross-record contradictions, and field-level completeness reporting.
Authorization boundaries: no production, marketplace, financial write, customer communication, or external side effect.
Validation plan: targeted unit tests for unknown-value preservation, visible validation failures, reproducible analytics, supplier analysis, capital tied up, coverage reporting, cross-record relationships, source fingerprinting, and inspection snapshots.
Rollback implications: delete the isolated feature branch; no production state exists.

## Current validation state
Earlier isolated validation of the initial slice passed `2 passed in 0.05s`. The expanded targeted suite now also includes capital-tied-up, supplier, coverage, cross-record validation, source fingerprinting, and inspection-snapshot cases. The repository currently has no attached CI status for these expanded tests, so they remain **NOT YET INDEPENDENTLY EXECUTED** and no merge/phase gate is claimed ready.
