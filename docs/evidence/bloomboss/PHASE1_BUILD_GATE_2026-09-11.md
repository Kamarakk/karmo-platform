# BloomBoss Phase 1 — Build Gate Evidence

Status: **VERIFIED IN ISOLATED GITHUB/DEV SCOPE — MERGE NOT AUTHORIZED**

Date: 2026-09-11
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Validated code commit: `c508c90365e5c4aed6185ca44e609fd59da0769b`

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
- baseline business, supplier, cultivar, channel, capital-tied-up, and completeness analytics;
- gross margin computed only across sold units with known matched cost basis, so unknown costs are never treated as zero;
- purchase-batch outcome analytics exposing sell-through, loss rate, known cost lost, matched realized profit/margin, and average days to sale;
- deterministic inventory-exposure analytics that identify active unsold units, known capital tied up, unknown-cost exposure, and days held measured to the latest date present in the source dataset rather than wall-clock time;
- streaming SHA-256 raw-source fingerprinting;
- reproducible `HistoricalImportSnapshot` combining source identity, normalized primary records, relationship findings, business/supplier/batch/cultivar/channel/inventory analytics, and quality coverage;
- read-only JSON report/CLI exposing the same source-fingerprinted primary snapshot without modifying raw evidence;
- design-only durable persistence boundary preserving raw evidence and defining replay/idempotency, transaction, mixed-state, observability, and rollback expectations;
- isolated read-only GitHub Actions validation workflow that automatically includes every `tests/test_bloomboss_*.py` test.

## Validation

GitHub Actions workflow: `BloomBoss Phase 1`
Run: #52
Runner: Ubuntu 24.04
Python: 3.12.14
Pytest: 9.1.1
Repository permission: contents read-only
Secrets used by BloomBoss code/tests: none

Targeted command:

`python -m pytest -q tests/test_bloomboss_*.py`

Result:

`27 passed in 0.13s`

Validated commit `c508c903` completed successfully in GitHub Actions. The four added listing-history tests prove multiple events per inventory unit, preservation of unknown listing facts, duplicate-listing rejection with source-row context, impossible date-order rejection, and negative asking-price rejection.

## Invariant/authority check

- I-01: incomplete legacy/historical records remain supported; unknown values are not backfilled by guess.
- I-03: raw source remains evidence; normalized records are derived; listing evidence is kept semantically separate from realized sales.
- I-04: stable listing IDs join stable batch/unit/sale IDs; persistence design defines replay identity as source digest + parser/schema version; no durable replay implementation yet.
- I-05: source hashing is chunked; current loaders are bounded to the historical files already supplied in dev scope; production-scale streaming remains deferred.
- I-06: raw evidence remains separable/rebuildable; future mixed-state behavior is explicit in the persistence design.
- I-07: row failures, validation issue codes, quality coverage, source identity, matched-margin coverage, batch outcomes, inventory exposure, and listing-history parse failures are visible.
- I-08: only targeted Phase 1 validation was run.
- I-09: no production, external marketplace/customer action, financial write, OBS, deployment, or secret use occurred.

## Risk

This remains an in-memory historical-intelligence slice. It has not yet been exercised against the real BloomBoss reconstructed history and has no durable database implementation. Passing synthetic/targeted tests does not establish the completeness of real business history.

Matched gross margin is intentionally narrower than total-revenue margin: only sales whose inventory units have known allocated landed cost are included in that denominator. This prevents incomplete historical cost data from overstating profitability.

Inventory age is intentionally measured only to the latest known date represented in the imported dataset, never to today's date, so repeated inspection of the same historical source remains reproducible.

Listing history is intentionally not inferred from sales. Historical asking prices, listing dates, and channels remain unknown when not supplied. This prevents realized sales from being misrepresented as evidence of prior asking/listing behavior.

## Rollback

Because this workload remains isolated to the feature branch, rollback is removal/closure of PR #32/branch changes. No production state exists from this workload.

## Gate result

**BUILD GATE READY.** The implemented Phase 1 slice has targeted validation evidence and is ready for Kamara's high-level merge/promotion decision when desired.

This report does **not** authorize merge or deployment.

## Next authorized work after merge/promotion decision

Use the real BloomBoss historical source data in approved non-production scope, produce source fingerprint + completeness/validation/inventory-exposure reports and listing-history evidence where available, then determine whether the next slice should implement durable local/dev persistence. No marketplace write automation is implied.