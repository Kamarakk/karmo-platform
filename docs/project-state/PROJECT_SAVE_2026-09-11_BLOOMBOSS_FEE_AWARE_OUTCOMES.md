# PROJECT SAVE — BloomBoss fee-aware realized outcomes

Status: **VERIFIED**

Date: 2026-09-11
Workstream: BloomBoss Historical Data Intelligence (Phase 1)
Branch: `feat/bloomboss-historical-intelligence`
PR: #32
Scope: approved non-production GitHub/dev only

## Purpose

Strengthen Phase 1 channel and cultivar economics so BloomBoss can distinguish gross realized outcomes from fully known post-fee/post-shipping outcomes without inventing missing financial facts.

## Changes made

### `bloomboss/outcomes.py`

Added fee-aware matched-cost outcome fields for cultivar and channel summaries:

- `sold_units_with_known_net_profit`
- `known_net_revenue_on_known_costs`
- `known_net_profit_on_known_costs`
- `known_net_margin_on_known_costs`

These fields are populated only when all required facts are known for the sold unit:

1. allocated landed cost;
2. selling fees; and
3. shipping cost.

If fee or shipping evidence is missing, these net metrics remain `None` rather than treating unknown amounts as zero.

Gross matched-cost metrics remain unchanged and separate.

### `tests/test_bloomboss_outcomes.py`

Added targeted coverage proving:

- known net revenue/profit/margin are calculated from fully known facts;
- partially known selling-cost facts do not produce invented net economics;
- gross matched-cost outcomes still include eligible sales even when fee/shipping facts are incomplete.

The first test-only commit contained an incorrect expected days-to-sale arithmetic value. GitHub Actions run #104 failed as expected. The test assertion was corrected; no production or external action was involved.

## Validation

BloomBoss Phase 1 GitHub Actions run #105 completed **SUCCESS** for code/test head:

`187350b310cb4f1d325058e665d879f161782879`

The prior failed run #104 is retained as truthful evidence of the test correction sequence rather than being hidden or rewritten.

## Invariant impact

- I-01 Inheritance/compatibility: **AFFECTED** — existing gross fields preserved; new output fields are additive.
- I-03 Data authority/transactions: **AFFECTED** — calculations use only canonical `PlantUnit` landed cost and `Sale` fee/shipping facts already present in Phase 1.
- I-05 Resources/scale: **NOT MATERIALLY CHANGED** — same bounded in-memory Phase 1 summarization path; no new external scan or persistence path.
- I-07 Observability: **AFFECTED** — explicit known-net eligibility count makes incompleteness visible.
- I-08 Validation scope: **AFFECTED** — targeted BloomBoss suite used; no unrelated regression suite added.
- I-09 Authority/permissions: **NOT AFFECTED** — read-only analytics only; no external action capability added.

## Risk

Primary risk is misrepresenting incomplete fee/shipping history as true net profit. The implementation avoids this by requiring both selling fees and shipping cost before calculating known net revenue or known net profit.

## Rollback

Revert the fee-aware outcome commits on the feature branch. No database, production, marketplace, customer, or secret state exists to roll back.

## Current branch/base condition

Fresh GitHub comparison during this workload showed PR #32 has diverged from current `main` and is **23 commits behind**. Therefore the earlier BUILD GATE READY state is suspended until the feature branch is resynchronized with current `main` and the targeted BloomBoss suite passes again after that synchronization.

This is a repository synchronization blocker only. It is not a Phase 1 code failure and it does not authorize a merge.

## Safety record

- Production KARMO accessed: **NO**
- Production KARMO modified: **NO**
- Secrets used/requested: **NO**
- Marketplace writes: **NO**
- Customer actions: **NO**
- OBS actions: **NO**
- Deployment: **NO**
- PR merge: **NO**

## Stopping point

Fee-aware cultivar/channel realized-outcome analytics are implemented and code-green. Mission Control now truthfully records that PR #32 is 23 commits behind current `main`, so the merge gate is suspended pending non-production branch resynchronization.

## Next authorized action

Resynchronize `feat/bloomboss-historical-intelligence` with current `main` in approved non-production GitHub/dev scope, resolve only actual conflicts, rerun the BloomBoss targeted suite, then refresh Phase 1 build-gate evidence. Do not merge without separate high-level approval.

PROJECT SAVE: COMPLETE
Persistent records updated: `docs/project-state/KARMO_DASHBOARD.md`, this PROJECT SAVE record
Durable Git commits: `2f75bc352d94571e17caef55afbafb05d4c0b0eb`, `62901e3f9d1872514ae77920d6a0bdb9cd0e6933`, `187350b310cb4f1d325058e665d879f161782879`, `18c739724ed5a9761439383e5ceb63f97110b333`, plus this documentation commit
Current stopping point: fee-aware outcome analytics code-green; PR #32 merge gate suspended because branch is 23 commits behind `main`
Next action: non-production resynchronization with current `main`, targeted validation, build-gate refresh
