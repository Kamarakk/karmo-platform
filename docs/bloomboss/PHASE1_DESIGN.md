# BloomBoss Phase 1 — Historical Data Intelligence

Status: **BUILD GATE READY IN ISOLATED DEVELOPMENT BRANCH — MERGE NOT AUTHORIZED**

## Goal
Turn 7–9 months of BloomBoss purchase/sales history into a canonical, auditable dataset without inventing missing values.

## Directory structure
- `bloomboss/models.py` — canonical domain records
- `bloomboss/ingest.py` — canonical purchase/unit/sale CSV ingestion
- `bloomboss/listing_history.py` — separate historical listing-event ingestion
- `bloomboss/listing_analytics.py` — deterministic listing-activity analytics from listing evidence only
- `bloomboss/history.py` — exact-source fingerprint + reproducible inspection snapshot
- `bloomboss/analytics.py` — first reproducible business, supplier, and purchase-batch metrics
- `bloomboss/outcomes.py` — cultivar/channel matched-cost outcome analysis
- `bloomboss/inventory.py` — deterministic unsold-inventory/capital exposure analysis
- `bloomboss/data_quality.py` — completeness/coverage reporting for reconstructed history
- `bloomboss/validation.py` — cross-record contradiction/reference validation
- `tests/test_bloomboss_*.py` — targeted Phase 1 behavior tests
- `docs/bloomboss/PERSISTENCE_DESIGN.md` — durable persistence design only; no database implementation

## Historical import format
The primary historical import uses one row per plant/inventory unit. Batch-level values may repeat across rows for the same batch. Blank values mean UNKNOWN, never zero.

Required primary columns: `batch_id`, `unit_id`, `cultivar`, `status`.

Listing history is intentionally a **separate evidence stream** rather than being inferred from realized sales. `HISTORICAL_LISTING_TEMPLATE.csv` supports multiple listing events for the same inventory unit with `listing_id`, `unit_id`, `channel`, optional `listed_date`, optional `unlisted_date`, and optional `asking_price`. This preserves the distinction between an asking/listing fact and a realized-sale fact and allows relisting on multiple channels without duplicating the canonical inventory identity.

## Data authority
For Phase 1, imported historical source rows are evidence. Canonical in-memory records are normalized representations. Production persistence is intentionally deferred.

`inspect_history_csv()` records the exact source filename, byte size, and a streaming SHA-256 fingerprint alongside canonical records, relationship findings, analytics, supplier/batch/cultivar/channel outcomes, inventory exposure, listing activity, and completeness metrics. The fingerprint identifies the raw evidence used for a result without mutating or copying that source.

Historical listing rows retain their own row-level provenance. Missing listing dates or asking prices remain unknown; listing values are never backfilled from sale records.

Listing-activity analytics stay strictly within listing evidence. They report listing-event volume, unique units listed, known asking-price averages, and completed listing durations overall and by channel. An unlisting is not treated as a sale, and listings are not matched to realized sales by inference.

The system reports both business metrics and **coverage metrics**. This prevents a partially reconstructed history from appearing more complete than it is. Missing values remain missing; coverage tells us how much of each field is actually known.

Current coverage reporting includes supplier, purchase date, quantity, full batch landed cost, unit cost basis, acquisition date, unit status, sale date, selling fees, outbound shipping, net revenue, and sold-unit cost basis.

Inventory exposure identifies active unsold units, known capital tied up, unknown-cost exposure, and days held. Days held are measured only to the latest known date represented in the imported dataset so repeated reports from the same historical source remain reproducible and do not drift with wall-clock time.

## Profitability and realized-return semantics
Historical profitability must never silently treat an unknown cost as zero.

For sold units with a known matched cost basis, Phase 1 distinguishes:

- **realized gross margin on known costs** = realized profit / realized revenue;
- **realized return on known costs** = realized profit / matched landed-cost basis.

These answer different questions. Margin describes how much of known matched sales revenue remained above landed cost. Return on cost describes how much profit was produced for each known landed-cost dollar committed to units that sold.

Supplier and purchase-batch summaries also expose a stricter **known-outcome return** that incorporates both sold units with known cost and units explicitly recorded as lost with known cost:

- known outcome cost basis = known cost of sold units + known cost of lost units;
- known outcome net profit = realized profit from sold known-cost units - known cost of lost units;
- known outcome return on cost = known outcome net profit / known outcome cost basis.

This prevents a supplier or purchase batch with profitable surviving sales but large known plant losses from looking artificially strong. Active unsold inventory is not treated as a realized loss; its cost remains visible separately as capital exposure. If cost is unknown, the related return fields remain `None` rather than becoming zero.

Supplier summaries also expose average days to sale when both acquisition and sale dates are known. This lets later ranking compare return, loss, and capital velocity without inventing missing dates.

## Cross-record validation
Canonical records are checked for contradictions that would make business analytics misleading while still allowing legitimate historical unknowns.

Current primary-history checks report:
- unit references a missing purchase batch;
- unit cultivar conflicts with its purchase batch cultivar;
- sale references a missing inventory unit;
- sale exists for a unit marked lost or giveaway;
- sale date precedes acquisition date;
- more than one sale record exists for the same unit;
- a known purchase-batch quantity does not match the number of reconstructed canonical inventory units (`BATCH_QUANTITY_RECONSTRUCTION_GAP`).

Listing-history ingestion independently rejects duplicate listing identities, invalid dates/money, and an `unlisted_date` earlier than its `listed_date`. Listing relationship validation reports references to missing units, listings before known acquisition, and listings after a known sale. Validation reports issues and does not mutate or auto-repair historical evidence.

## Durable persistence direction
`docs/bloomboss/PERSISTENCE_DESIGN.md` defines the next safe boundary before any database implementation: immutable raw-source evidence, SHA-256 source identity, replay identity based on source digest + parser version, canonical tables separated from raw evidence, explicit import-run state, and no partial promotion after structural parse failure.

This remains design-only. No production database, migration, deployment, secret, or external action is authorized by Phase 1.

## Acceptance criteria
1. Missing historical financial values remain `None`/unknown.
2. Invalid dates/decimals/statuses fail visibly.
3. A sale cannot have a price without a channel.
4. Analytics are reproducible from canonical records.
5. Initial metrics cover revenue, known landed cost, realized gross profit/margin on known costs, realized return on known costs, loss-aware known-outcome return for suppliers/purchase batches, sell-through, loss rate, average sale price, average days-to-sale, channel performance, cultivar performance, supplier performance, purchase-batch outcomes, and capital tied up in active unsold inventory.
6. Historical-data completeness is measurable without imputing missing values.
7. Cross-record contradictions are reported without silently repairing or inventing historical facts.
8. An inspection snapshot fingerprints the exact raw source and combines canonical records, validation, business/outcome/inventory analytics, and completeness without changing the source.
9. Active unsold inventory can be ranked for capital exposure without using wall-clock time or inventing missing cost/acquisition facts.
10. Historical listing events remain separate from sales, support multiple events for the same unit, preserve unknown listing facts, and reject impossible listing date order.
11. Historical listing activity can be summarized overall and by channel without inferring sale outcomes from unlisting/listing evidence.
12. Known purchase quantity reconstruction gaps are visible without inventing missing units or converting incomplete reconstruction into assumed loss.
13. No production, marketplace writes, OBS, or external customer actions.

## Invariant Impact Review
Phase: BloomBoss Historical Data Intelligence v1

- I-01 Inheritance/compatibility: AFFECTED — must tolerate incomplete historical records.
- I-02 Production parity: NOT AFFECTED — isolated development only; production design deferred.
- I-03 Data authority/transactions: AFFECTED — raw historical source remains evidence; canonical records are derived and the exact source is fingerprinted.
- I-04 Idempotency/retry: AFFECTED — stable batch/unit/sale/listing IDs are required; future durable replay identity is source SHA-256 + parser/schema version.
- I-05 Resources/scale: AFFECTED — current loaders are bounded by source file size; source hashing is chunked; streaming/persistence review remains required before production-scale ingestion.
- I-06 Migration/rollback: AFFECTED — raw sources are preserved separately so normalization can be rebuilt; persistence design explicitly requires mixed-state compatibility.
- I-07 Observability: AFFECTED — malformed rows fail visibly; provenance records source row; coverage metrics expose reconstruction gaps; cross-record validation emits explicit issue codes/entity IDs; snapshots expose source identity, listing activity, inventory exposure, and loss-aware realized-return measures.
- I-08 Validation scope: AFFECTED — targeted Phase 1 tests only.
- I-09 Authority/permissions: AFFECTED — Phase 1 is READ/LOCAL NORMALIZATION only; no external writes/actions.

Known inherited assumptions: existing KARMO foundation is not modified.
Legacy-data considerations: missing historical fields are expected and must remain unknown.
Authoritative data stores: historical source files are source evidence for this isolated phase.
Transaction/failure boundaries: each local CSV parse is all-or-fail in memory; failed rows abort that source load rather than partially reporting success. Future durable boundary is specified separately, not implemented.
Scale considerations: sufficient for initial 7–9 month reconstruction; production streaming/pagination deferred; hashing is bounded by chunk size.
Runtime/dependency requirements: Python standard library only.
Migration/mixed-state requirements: none in production; canonical format remains rebuildable from raw source. Future durable design must tolerate older nullable records.
Observability requirements: row-level provenance, source fingerprint, explicit validation errors, issue codes/entity IDs for cross-record contradictions, field-level completeness reporting, deterministic inventory exposure, deterministic listing activity, loss-aware known-outcome return, and row-specific listing-history failures.
Authorization boundaries: no production, marketplace, financial write, customer communication, or external side effect.
Validation plan: targeted unit tests for unknown-value preservation, visible validation failures, reproducible analytics, supplier/batch/cultivar/channel analysis, realized-return semantics, known-loss treatment, capital tied up, inventory exposure, coverage reporting, cross-record relationships, source fingerprinting, inspection snapshots, listing-history integrity, and listing-activity summaries.
Rollback implications: delete the isolated feature branch; no production state exists.

## Current validation state
GitHub Actions run #91 validated code commit `7b69483102e9f07cf829e35d90b07b91d6ff223b` successfully using the automatic targeted command `python -m pytest -q tests/test_bloomboss_*.py`.

The latest slice adds three targeted tests proving that supplier and purchase-batch realized return uses only matched known cost, explicitly known loss cost reduces known-outcome return, loss-only known outcomes can correctly report a negative return, and unknown cost remains unknown rather than becoming zero profit/cost.

The Phase 1 build gate remains **READY for Kamara's high-level merge/promotion decision**. This status does not authorize merge, deployment, production access, marketplace/customer actions, or secret use.
