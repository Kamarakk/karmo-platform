# PROJECT SAVE — BloomBoss Unit Outcome Reporting

Date: 2026-09-11
Status: **VERIFIED — NON-PRODUCTION DEVELOPMENT ONLY**
Workstream: BloomBoss Phase 1 — Historical Data Intelligence
Branch: `feat/bloomboss-historical-intelligence`
PR: #32

## Purpose

Close a narrow Phase 1 reporting gap: `HistoricalImportSnapshot` already computed truthful unit-level outcomes, but the read-only operator JSON report omitted that summary. As a result, the CLI could not directly expose the Phase 1 success question "Which plants made the most money?" even though the underlying calculation existed.

## Changes

- `bloomboss/report.py`
  - added `unit_outcome_summary` to the deterministic JSON report;
  - reused the existing snapshot calculation rather than introducing a second calculation path;
  - preserved Decimal values through the existing JSON conversion path.
- `tests/test_bloomboss_report.py`
  - added targeted assertions proving the report exposes unit-level channel, realized profit on known cost, known net profit, and days-to-sale.

## Truthfulness / governance behavior

The report continues to inherit the existing `summarize_units` rules:

- realized profit is reported only when a sale is matched to known allocated landed cost;
- known net profit is reported only when the sale's fees and outbound shipping are known enough for `known_net_revenue` to exist;
- missing financial values remain unknown rather than being converted to zero;
- no marketplace, customer, production, or secret-bearing system is accessed.

This change is read-only reporting and does not alter canonical source data, schemas, persistence, external actions, or authority boundaries.

## Validation

GitHub Actions `BloomBoss Phase 1` run #107 for commit `933792b3da6a995227743d5b8f28b31e486cfe14` completed successfully. The `targeted-tests` job and `Run BloomBoss targeted suite` step both concluded `success`.

Targeted fixture verification now proves:

- U1 sale channel = `Palmstreet`;
- realized profit on known cost = `130` (`250 - 120`);
- known net profit = `90` (`250 - 25 - 15 - 120`);
- days to sale = `31`.

## Risk

Low. The change exposes an already-computed snapshot field through the existing read-only report serializer. It does not change calculations, ingestion, validation, persistence, or external behavior. Primary regression risk was accidental serialization/output breakage; targeted CI passed.

## Verification

Run the existing BloomBoss report against a historical CSV and confirm `unit_outcome_summary` is present and that unknown costs/fees remain `null` where facts are missing. The automated report test covers the known-value path while the existing outcome tests cover unknown-value preservation.

## Rollback

Revert commits:

- `f9223347d82b0e39f56b4f421ea4ca029f94f4a1` — report exposure;
- `933792b3da6a995227743d5b8f28b31e486cfe14` — targeted report assertions.

No data rollback or production action is required.

## Stopping point

The Phase 1 operator report now exposes the unit-level outcome intelligence already present in the canonical historical snapshot. PR #32 remains open and unmerged. No deployment or production access occurred.

## Next authorized action

Continue narrow Phase 1 completeness/reliability work on PR #32 while staying inside the approved non-production branch. Any merge/promotion remains a separate high-level approval boundary.

PROJECT SAVE: COMPLETE
Persistent records updated: `docs/project-state/PROJECT_SAVE_2026-09-11_BLOOMBOSS_UNIT_REPORTING.md`
Durable Git commit: created by this PROJECT SAVE commit
Current stopping point: unit-level historical outcomes are exposed through the read-only JSON report and targeted CI is green
Next action: continue approved Phase 1 non-production build work; do not merge or deploy without explicit approval
