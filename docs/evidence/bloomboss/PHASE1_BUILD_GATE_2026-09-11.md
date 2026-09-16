# BloomBoss Phase 1 — Build Gate Evidence

Status: **VERIFIED IN ISOLATED GITHUB/DEV SCOPE — MERGE NOT AUTHORIZED**

Date: 2026-09-11
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Validated code/test commit: `7b69483102e9f07cf829e35d90b07b91d6ff223b`

## Purpose

Record the meaningful build gate for BloomBoss Historical Data Intelligence without crossing into merge, production, marketplace/customer action, deployment, or secret scope.

## Implemented boundary

- canonical purchase batch, plant unit, sale, status, provenance, and historical listing-event records;
- canonical historical CSV loader with unknown values preserved as unknown;
- separate listing-history loader so asking/listing facts are never inferred from realized sales and multiple listing events may exist for one canonical unit;
- row-specific human-readable parse failures;
- duplicate/conflicting identity checks, including listing identity;
- listing-history date-order validation (`unlisted_date` cannot precede `listed_date`);
- relationship contradiction validation for primary purchase/unit/sale history;
- reconstruction-integrity reporting when known purchase-batch quantity does not match reconstructed canonical inventory count, without inventing missing units or assumed losses;
- baseline business, supplier, purchase-batch, cultivar, channel, capital-tied-up, and completeness analytics;
- gross margin computed only across sold units with known matched cost basis, so unknown costs are never treated as zero;
- realized return on known cost basis for supplier and purchase-batch outcomes;
- loss-aware known-outcome return that includes explicitly known plant-loss cost while leaving active unsold inventory as capital exposure rather than pretending it is a realized loss;
- supplier average days-to-sale where dates are known, allowing return and capital-velocity comparison without date imputation;
- deterministic inventory-exposure analytics that identify active unsold units, known capital tied up, unknown-cost exposure, and days held measured to the latest date present in the source dataset rather than wall-clock time;
- streaming SHA-256 raw-source fingerprinting;
- reproducible `HistoricalImportSnapshot` combining source identity, normalized primary records, relationship findings, business/supplier/batch/cultivar/channel/inventory/listing analytics, and quality coverage;
- read-only JSON report/CLI exposing the same source-fingerprinted snapshot without modifying raw evidence;
- separate historical listing-evidence fingerprint, relationship findings, coverage, and deterministic activity summary;
- design-only durable persistence boundary preserving raw evidence and defining replay/idempotency, transaction, mixed-state, observability, and rollback expectations;
- isolated read-only GitHub Actions validation workflow that automatically includes every `tests/test_bloomboss_*.py` test.

## Latest validation

GitHub Actions workflow: `BloomBoss Phase 1`
Run: #91
Event: pull request
Result: **SUCCESS**
Runner family: GitHub-hosted Ubuntu
Python target: 3.12
Repository permission: contents read-only
Secrets used by BloomBoss code/tests: none

Targeted command:

`python -m pytest -q tests/test_bloomboss_*.py`

Validated commit `7b694831` completed successfully in GitHub Actions on 2026-09-11.

The latest three targeted tests prove:

1. supplier realized return uses only matched known sold cost and does not impute unknown cost;
2. known plant-loss cost reduces the stricter supplier/purchase-batch known-outcome return;
3. a loss-only supplier with known cost correctly produces a negative known-outcome return while unknown-cost outcomes remain `None` rather than zero.

## Realized-return interpretation

Phase 1 now explicitly distinguishes two profitability lenses:

- **realized gross margin on known costs** = matched realized profit / matched realized revenue;
- **realized return on known costs** = matched realized profit / matched landed-cost basis.

Supplier and batch summaries additionally expose:

- **known outcome cost basis** = known cost of sold units + known cost of explicitly lost units;
- **known outcome net profit** = realized profit from sold known-cost units - known cost of explicitly lost units;
- **known outcome return on cost** = known outcome net profit / known outcome cost basis.

This avoids ranking suppliers or purchases only by the successful survivors when known historical loss cost exists. It also avoids charging active unsold inventory as a realized loss; active inventory remains visible through the inventory-exposure metrics.

## Invariant/authority check

- I-01: incomplete legacy/historical records remain supported; unknown values are not backfilled by guess.
- I-03: raw source remains evidence; normalized records are derived; listing evidence is kept semantically separate from realized sales.
- I-04: stable listing IDs join stable batch/unit/sale IDs; persistence design defines replay identity as source digest + parser/schema version; no durable replay implementation yet.
- I-05: source hashing is chunked; current loaders are bounded to the historical files already supplied in dev scope; production-scale streaming remains deferred.
- I-06: raw evidence remains separable/rebuildable; future mixed-state behavior is explicit in the persistence design.
- I-07: row failures, validation issue codes, quality coverage, source identity, matched-margin coverage, realized-return coverage, loss-aware supplier/batch outcomes, inventory exposure, and listing-history failures are visible.
- I-08: only targeted Phase 1 validation was run; no unnecessary full KARMO suite was added.
- I-09: no production, external marketplace/customer action, financial write, OBS, deployment, or secret use occurred.

## Risk

This remains an in-memory historical-intelligence slice. It has not yet been exercised against the real BloomBoss reconstructed history and has no durable database implementation. Passing synthetic/targeted tests does not establish the completeness of real business history.

Matched gross margin and realized return are intentionally narrower than total-revenue profitability: only sales whose inventory units have known allocated landed cost are included. This prevents incomplete historical cost data from overstating certainty.

Known-outcome return includes only outcomes whose costs are actually known. It must not be described as total supplier or purchase profitability when historical cost coverage is incomplete.

Inventory age is intentionally measured only to the latest known date represented in the imported dataset, never to today's date, so repeated inspection of the same historical source remains reproducible.

Listing history is intentionally not inferred from sales. Historical asking prices, listing dates, and channels remain unknown when not supplied. This prevents realized sales from being misrepresented as evidence of prior asking/listing behavior.

## Rollback

Because this workload remains isolated to the feature branch, rollback is removal/closure of PR #32/branch changes. No production state exists from this workload.

## Gate result

**BUILD GATE READY.** The implemented Phase 1 slice has targeted validation evidence and is ready for Kamara's high-level merge/promotion decision when desired.

This report does **not** authorize merge or deployment.

## Next authorized work after merge/promotion decision

Use the real BloomBoss historical source data in approved non-production scope, produce source fingerprint + completeness/validation/inventory-exposure/realized-return reports and listing-history evidence where available, then determine whether the next slice should implement durable local/dev persistence. No marketplace write automation is implied.
