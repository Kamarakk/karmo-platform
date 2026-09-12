# BloomBoss Propagation & Lineage Design

Status: **IMPLEMENTED IN ISOLATED PHASE 1 BRANCH — NOT DEPLOYED**

## Goal
Extend the existing BloomBoss purchase → inventory → listing → sale model with a general parent → propagation event → child inventory relationship that works across plant types.

## Reuse decision
The current purchase, listing, and sale model remains intact. Propagation is an additional evidence stream; it does not create fake purchase batches or infer supplier/cost history for plants grown in-house.

## Canonical additions
- `PlantOrigin` — high-level origin classification: purchased, propagated, tissue_culture, seed_grown, gifted, other, unknown.
- `PropagationMethod` — plant-agnostic method: corm, division, cutting, node, offset, seed, tissue_culture, other, unknown.
- `PropagationEvent` — stable relationship from one known parent unit to one child unit.
- `PlantUnit.batch_id` may be null for inventory that did not come from a purchase batch.

## Historical propagation import
`HISTORICAL_PROPAGATION_TEMPLATE.csv` is a separate evidence stream with:

Required columns:
- `propagation_id`
- `parent_unit_id`
- `child_unit_id`
- `cultivar`
- `method`

Optional columns:
- `status`
- `propagation_date`
- `acquired_date`
- `allocated_landed_cost`
- `notes`

Blank optional values remain unknown. A propagation row creates a propagated child `PlantUnit` with `batch_id=None`; it does not create a purchase batch.

## Why this is not Alocasia-specific
The same model represents:
- Alocasia corms or offsets;
- Monstera/Philodendron node or stem cuttings;
- Anthurium divisions or seed-grown offspring;
- Begonia or other cuttings;
- tissue-culture-derived propagation;
- future methods through `other` or a later enum extension.

## Lineage integrity
Validation reports, without auto-repair:
- missing parent unit;
- missing child unit;
- self-parenting;
- multiple propagation origins for one child identity;
- propagation before a known parent acquisition date;
- child acquisition before a known propagation date;
- child origin inconsistent with a propagation event;
- lineage cycles.

## Cost semantics
No cost is invented for propagated offspring. `allocated_landed_cost` stays nullable until BloomBoss adopts an explicit propagation-cost policy. Parent purchase cost is not automatically copied to children.

## Known limitation / future extension
Phase 1 models one known source parent per propagation event. If BloomBoss later needs formal two-parent breeding/genetic lineage, add a separate multi-parent lineage relationship rather than overloading this field.

## System-Fit review
Goal served: truthful historical and future inventory lineage across BloomBoss plant types.
Existing capability reused: canonical `PlantUnit`, provenance, independent evidence streams, validation patterns.
New software/services added: none.
Important current-system facts: isolated PR #32 only; no database or production persistence.
Main risks/lifecycle burden: lineage identity errors and accidental cost invention.
Simpler alternative considered: Alocasia-specific corm fields; rejected because BloomBoss propagates multiple plant categories.
Decision: **PROCEED WITH CONSTRAINTS**.
Constraints: no fake purchase batches, no inferred cost, no production writes, preserve separate listing/sale truth.
