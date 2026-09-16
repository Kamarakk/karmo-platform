# PROJECT SAVE — BloomBoss Propagation & Lineage

Date: 2026-09-11
Branch: `feat/bloomboss-historical-intelligence`
PR: #32
Status: **IMPLEMENTED IN ISOLATED DEVELOPMENT BRANCH — VALIDATION PENDING**

## Decision
Keep the current BloomBoss purchase/listing/sale model and add a general plant-agnostic lineage + propagation layer. Do not model propagation as Alocasia/corm-specific because BloomBoss propagates multiple plant categories.

## Implemented
- Added high-level plant origin classification.
- Added propagation methods covering corm, division, cutting, node, offset, seed, tissue culture, other, and unknown.
- Added canonical `PropagationEvent` parent → child relationship.
- Allowed a `PlantUnit` to have no purchase batch when it is propagated inventory.
- Purchase-history ingestion now explicitly marks imported units as purchased.
- Added separate propagation-history CSV ingestion that creates propagated child units without fake purchase batches.
- Added propagation template and dedicated lineage design document.
- Added validation for missing lineage references, self-parenting, multiple origins, impossible known dates, origin conflicts, and lineage cycles.
- Added targeted tests including Monstera cutting, Alocasia corm, and Anthurium division examples.

## Preserved boundaries
- Existing purchase/listing/sale truth remains separate.
- Listing history remains separate from realized sales.
- Unknown historical values remain unknown, never zero.
- Parent purchase cost is not automatically copied to propagated children.
- No production access, database changes, deployment, marketplace writes, customer actions, OBS changes, or secrets.

## Known limitation
Phase 1 records one known source parent per propagation event. Formal multi-parent breeding/genetic lineage remains a future extension if BloomBoss needs it.

## Validation
GitHub Actions targeted BloomBoss suite should run automatically for this branch. Do not mark this slice verified until the new head reports a passing run.
