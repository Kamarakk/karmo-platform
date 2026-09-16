# PROJECT SAVE — BloomBoss loss-aware realized return

Date: 2026-09-11
Workstream: BloomBoss Historical Data Intelligence (Phase 1)
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Status: **VERIFIED IN ISOLATED GITHUB/DEV SCOPE — BUILD GATE READY — MERGE NOT AUTHORIZED**

## Purpose

Preserve the latest Phase 1 progress after extending historical supplier and purchase-batch intelligence from gross-margin-only reporting to return-on-cost and loss-aware known-outcome reporting.

## What changed

- `bloomboss/analytics.py`
  - supplier summaries now expose matched known cost basis, realized return on known costs, explicitly known loss cost, known-outcome cost basis/net profit/return, and average days to sale;
  - purchase-batch summaries now expose the same realized-return and known-outcome return distinctions;
  - unknown cost no longer produces a misleading zero realized profit/return in supplier summaries;
  - active unsold inventory is not charged as a realized loss.
- `tests/test_bloomboss_realized_return.py`
  - verifies supplier realized return from matched known sold cost;
  - verifies explicit known loss cost reduces known-outcome return;
  - verifies purchase-batch return semantics;
  - verifies a loss-only known-cost supplier produces a negative known-outcome return;
  - verifies unknown cost remains unknown rather than being imputed as zero.
- `docs/bloomboss/PHASE1_DESIGN.md`
  - documents the distinction between gross margin, realized return on known cost, and stricter loss-aware known-outcome return.
- `docs/evidence/bloomboss/PHASE1_BUILD_GATE_2026-09-11.md`
  - refreshes build-gate evidence with the latest validated code/test commit and run.
- `docs/project-state/KARMO_DASHBOARD.md`
  - refreshes Mission Control with the new decision-ready supplier/batch outcome capability.

## Why

The BloomBoss build plan requires Phase 1 to answer which suppliers produced the best realized return and which purchases produced the highest losses. Gross margin alone is insufficient for that decision because:

1. margin uses revenue as the denominator rather than invested landed cost;
2. ranking only sold survivors can hide known plant losses from the same supplier or purchase batch;
3. unknown historical cost must not be interpreted as zero cost or zero profit.

The new metrics keep these concepts separate and explicit.

## Metric semantics

For sold units with matched known landed cost:

- realized gross margin on known costs = realized profit / realized revenue;
- realized return on known costs = realized profit / matched landed-cost basis.

For supplier and batch outcomes with explicitly known sold/lost cost:

- known outcome cost basis = known sold cost + known lost cost;
- known outcome net profit = realized sold profit - known lost cost;
- known outcome return on cost = known outcome net profit / known outcome cost basis.

Unknown costs remain `None`. Active unsold inventory remains capital exposure, not realized loss.

## Validation

Validated code/test commit: `7b69483102e9f07cf829e35d90b07b91d6ff223b`

GitHub Actions:
- workflow: `BloomBoss Phase 1`
- pull-request run: #91
- result: **SUCCESS**
- target: Python 3.12
- command: `python -m pytest -q tests/test_bloomboss_*.py`
- repository permission: contents read-only
- BloomBoss secrets: none

The three newly added targeted tests passed as part of the automatic BloomBoss suite.

## Invariant review

- I-01: historical unknowns remain supported; no new required field is introduced.
- I-03: source evidence remains authoritative input; analytics remain derived/read-only.
- I-05: no new unbounded resource behavior was introduced.
- I-07: profitability meaning is more observable because margin, matched return, loss cost, and loss-aware return are separately named.
- I-08: targeted BloomBoss validation only; no unjustified full-suite repetition.
- I-09: READ/analysis scope only; no external action or production authority added.

## Risk

These metrics remain only as reliable as the historical reconstruction coverage. A supplier/batch known-outcome return is not a claim of complete lifetime profitability when cost or status fields are missing. Completeness reporting must accompany interpretation of real data.

No real BloomBoss source dataset was accessed in this workload turn.

## Verification

- latest code/test commit passed the isolated GitHub Actions gate;
- build-gate evidence and Phase 1 design were reconciled with the new metric semantics;
- Mission Control still identifies PR #32 as build-gate ready and unmerged.

## Rollback

All work is isolated to PR #32 / the feature branch. Rollback is branch/PR reversion or closure. There is no production state to repair.

## Current stopping point

Phase 1 can now answer the plan's supplier/purchase return question more truthfully by separating gross margin, return on invested known cost, and known plant-loss effects. The PR remains build-gate ready.

## Next action

High-level decision: merge or decline PR #32. Merge remains outside this workload's authority.

If promoted later, the next approved non-production step is to run the real reconstructed BloomBoss history through the source-fingerprinted report and inspect completeness, contradictions, listing evidence, inventory exposure, supplier/batch return, and known-outcome return before implementing durable persistence.
