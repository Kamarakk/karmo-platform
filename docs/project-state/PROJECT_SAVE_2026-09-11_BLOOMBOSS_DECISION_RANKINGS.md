# PROJECT SAVE — BloomBoss Phase 1 Decision Rankings

Status: **VERIFIED — isolated non-production branch only**

Date: 2026-09-11
Branch: `feat/bloomboss-historical-intelligence`
PR: #32

## Purpose

Make the Phase 1 release questions directly consumable from the reproducible historical snapshot instead of requiring a human or later agent to manually sort raw summary dictionaries.

## What changed

- Added `bloomboss/rankings.py` with deterministic rankings derived only from already-known Phase 1 facts.
- Added `decision_rankings` to `HistoricalImportSnapshot`.
- Added `decision_rankings` to the JSON inspection report.
- Added targeted coverage in `tests/test_bloomboss_rankings.py`.

Current ranking views:

- plants by realized profit on known cost;
- purchase batches by known loss cost;
- suppliers by known-outcome return on cost;
- cultivars by average days to sale;
- channels by known net profit on known costs.

## Data / governance behavior

Unknown financial, date, fee, shipping, and outcome values are excluded from the corresponding ranking rather than converted to zero. Equal values use entity identity as the tie-breaker so repeated runs are deterministic.

The ranking layer is derived read-only intelligence. It does not change canonical records, source evidence, external systems, or authority boundaries.

## Invariant impact

- I-01: preserves incomplete/legacy historical facts; unknowns remain unknown.
- I-03: no authority change; rankings derive from canonical in-memory summaries.
- I-05: bounded by the already-loaded Phase 1 summary dictionaries; no new external scan or datastore.
- I-07: decision outputs are explicit and inspectable in the report.
- I-08: targeted BloomBoss suite used because only Phase 1 derived reporting changed.
- I-09: READ / derived-analysis only; no external action authority added.

No production-parity, migration, retry, or persistence boundary changed.

## Verification

Code head tested: `66ec331743864da81bddc75ebebcd54afb8a7c54`

GitHub Actions BloomBoss Phase 1 run #152 (`targeted-tests`) completed **SUCCESS** on that head. The workflow executed `python -m pytest -q tests/test_bloomboss_*.py` under Python 3.12.

The new targeted test verifies:

- ranking direction for each release question;
- deterministic tie-breaking;
- unknown values are omitted rather than imputed.

## Risk

Low. This adds derived reporting only. The main semantic risk is presenting incomplete historical data as complete; that is mitigated by excluding unknown values and retaining the existing completeness/quality summaries alongside these rankings.

## Rollback

Revert the decision-ranking commits or remove `bloomboss/rankings.py`, the snapshot/report field, and `tests/test_bloomboss_rankings.py`. No production or external state exists to roll back.

## Safety boundary

- Production KARMO: untouched.
- Deployment: none.
- Secrets: none used.
- Marketplace/customer actions: none.
- OBS: none.
- PR merge: not performed.

## Current stopping point

PR #32 remains the isolated BloomBoss Phase 1 build candidate. `main` was verified 0 commits ahead of the branch before this slice; the feature branch was 135 commits ahead at that check.

The Phase 1 implementation can now answer its principal release questions through deterministic, machine-readable rankings while still preserving historical uncertainty.

## Next action

Hold PR #32 at the existing high-level merge/promotion gate. Continue only safe Phase-1-scoped improvements unless Kamara approves merge/promotion or another high-level direction.

PROJECT SAVE: COMPLETE
