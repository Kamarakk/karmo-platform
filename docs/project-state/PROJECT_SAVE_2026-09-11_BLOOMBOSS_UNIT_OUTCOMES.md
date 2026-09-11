# PROJECT SAVE — BloomBoss Phase 1 unit-level outcome intelligence

Date: 2026-09-11
Workstream: BloomBoss Historical Data Intelligence
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Scope: approved non-production GitHub/dev only

## Purpose

Close a remaining Phase 1 success-criterion gap: BloomBoss must be able to answer which individual plants made the most money without inferring missing costs, fees, shipping, or sale facts.

## Changes made

- Added `summarize_units()` in `bloomboss/outcomes.py`.
- Added `unit_outcome_summary` to the reproducible `HistoricalImportSnapshot`.
- Added targeted tests in `tests/test_bloomboss_unit_outcomes.py`.

The unit-level summary reports, per canonical inventory unit:

- cultivar and batch identity;
- recorded status;
- matched sale identity/channel/price where present;
- allocated landed cost where known;
- realized profit and return only when a realized sale is matched to known allocated landed cost;
- known net profit only when sale fees and shipping are both explicitly known;
- days to sale only when acquisition and sale dates are both known.

Unsold inventory is not mislabeled as realized profit or loss. Unknown cost remains unknown.

## Validation

Branch head after targeted test addition: `5d714c297af9dc8c04dd8f8c021622f0b69d9c38`.

GitHub Actions BloomBoss Phase 1 run #102 (`34659482083`) completed successfully on that head.

## Current integration state

At the start of this workload, current `main` was `0a59506a1898b33ade395093fd52e3041c7e59cb` while PR #32 was still based at merge base `21019c1e2833b0f797e09d225639305530c48f3e` and GitHub reported the branch 23 commits behind / diverged. This workload did not merge or deploy anything.

A non-production Desktop Commander endpoint for KARMO-DEV01 was not available; the only connected endpoint was production `karmo-ai01`, so it was intentionally not used. All work remained in the approved GitHub feature branch.

## Safety / invariant boundary

- Production KARMO: untouched.
- Production host access: none.
- Deployment: none.
- PR merge: none.
- Secrets: none.
- Marketplace/customer actions: none.
- OBS/live production: none.
- Historical unknowns remain explicit; no financial facts were invented.

## Risk

Low implementation risk. The new output is read-only analytics over already canonicalized Phase 1 records. It adds no external side effects and no persistence writes.

The current promotion risk is branch divergence from newer `main`, not this unit-outcome change. PR #32 must be synchronized and revalidated before any future merge decision can be trusted.

## Verification / rollback

Verification: GitHub Actions run #102 succeeded for head `5d714c297af9dc8c04dd8f8c021622f0b69d9c38`.

Rollback: revert the three feature-branch commits introducing unit outcome code, snapshot wiring, and its targeted tests. No production rollback exists because production was not touched.

## Next authorized work

Continue improving Phase 1 only in the approved feature branch and restore synchronization with current `main` when a non-production dev merge path is available. After synchronization, rerun the targeted BloomBoss suite and re-establish the high-level merge gate. No merge is authorized by this save.
