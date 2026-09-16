# PROJECT SAVE — BloomBoss Historical Reconstruction Integrity

Date: 2026-09-11
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Scope: approved non-production GitHub/dev only

## What changed

Historical relationship validation now compares each purchase batch's known `quantity` with the number of reconstructed canonical inventory-unit records attached to that batch.

When the numbers differ, the snapshot reports `BATCH_QUANTITY_RECONSTRUCTION_GAP` with the batch identity, known purchased quantity, and reconstructed unit count. The validator does not create missing units, change the known quantity, or infer what happened to the missing inventory.

When batch quantity is unknown, no expected count is invented.

## Why this matters

BloomBoss Phase 1 is intended to reconstruct roughly 7–9 months of real business history without allowing incomplete history to masquerade as complete history. A known purchase quantity that does not match reconstructed inventory is a material historical-data gap because sell-through, loss rate, supplier outcomes, cultivar outcomes, and capital analysis can otherwise look more complete than the source evidence supports.

This check makes that gap visible while preserving the project's rule that unknown historical facts remain unknown.

## Files changed

- `bloomboss/validation.py`
- `tests/test_bloomboss_reconstruction_validation.py`
- this PROJECT SAVE record

## Validation

GitHub Actions workflow: `BloomBoss Phase 1`
Run: #86
Validated commit: `4b33da2b1f59b60033ed32b62067815a766c0715`
Result: **SUCCESS**

Three targeted tests cover:

1. known quantity mismatch is reported;
2. matching quantity/reconstruction produces no gap;
3. unknown quantity does not invent an expected inventory count.

The workflow remained in isolated GitHub scope with repository contents read-only and no BloomBoss secrets.

## Invariant impact

- **I-01 Inheritance/compatibility:** affected positively; incomplete historical reconstruction is surfaced instead of silently accepted as complete.
- **I-03 Data authority/transactions:** no write or transaction boundary changed; source quantity and reconstructed records remain separate observed facts.
- **I-06 Migration/rollback:** no schema or persistent-state migration introduced.
- **I-07 Observability:** improved through a stable human-readable validation issue code and message.
- **I-08 Validation scope:** targeted validation only; no unrelated suite expansion.
- **I-09 Authority/permissions:** no production access, marketplace/customer action, deployment, merge, secret use, or external side effect.

## Risk

A quantity mismatch is deliberately classified as a reconstruction gap rather than automatically as a plant loss. Historical records may simply be incomplete, aggregated, or still awaiting reconstruction. Future analysis must not convert this validation issue into a business loss without supporting evidence.

## Rollback

All changes remain isolated to PR #32. Rollback is removal/reversion of these branch commits or closure of the PR. Production KARMO and external systems were not touched.

## Gate

PR #32 remains at the existing **BUILD GATE READY / MERGE NOT AUTHORIZED** boundary. This checkpoint strengthens the trustworthiness of real-history reconstruction but does not change the high-level approval requirement for merge/promotion.
