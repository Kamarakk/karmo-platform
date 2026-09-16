# PROJECT SAVE — BloomBoss Historical Intelligence: Inventory Aging

Date: 2026-09-11
Status: **VERIFIED — NON-PRODUCTION / PR #32 ONLY**

## Scope

Continued approved BloomBoss Phase 1 work on `feat/bloomboss-historical-intelligence` / PR #32 only. No production KARMO access or modification occurred. No deployment, merge, secrets, marketplace/customer action, or OBS action occurred.

## Purpose

Make unsold historical inventory easier to reason about by showing how long capital has been tied up, without using the current wall-clock date or inventing unknown acquisition dates/costs.

## Changes

- `bloomboss/inventory.py`
  - added deterministic age buckets for active unsold inventory: `0_30_days`, `31_60_days`, `61_90_days`, `91_plus_days`, and `unknown_age`;
  - age remains measured to the latest known business date already present in the historical dataset;
  - each bucket reports unit count, units with known/unknown cost, and known capital tied up only when cost is actually known;
  - each unit row now includes its computed `aging_bucket` or `None` when age is unknown.
- `tests/test_bloomboss_inventory_exposure.py`
  - extended coverage for per-unit bucket assignment, unknown age/cost behavior, and all four deterministic age bands.
- `docs/project-state/KARMO_DASHBOARD.md`
  - refreshed Mission Control with the new inventory-aging capability and validation result.

## Validation

Validation ladder used: changed BloomBoss code -> targeted BloomBoss Phase 1 GitHub Actions suite.

- GitHub Actions run #140 on commit `3558c148a018e42928955c19d4bf2d55ea5d20e5`: **FAIL**.
- Failure cause: the newly added test fixture used calendar dates that represented 30/60/90 elapsed days while asserting the 31/61/91 buckets. This was a test-data boundary mistake, not a discovered production or historical-data issue.
- Fix commit: `cc4e8553259100d41c2d8987803e0e8979acfc66`, adjusting only the fixture dates to exact 31/61/91-day boundaries.
- GitHub Actions run #142 on `cc4e8553259100d41c2d8987803e0e8979acfc66`: **SUCCESS**.

The failed test was not ignored or bypassed; the fixture error was corrected and the same targeted suite passed.

## Invariant / governance fit

- **I-01 / I-06:** no schema migration or historical-record rewrite; existing records continue to work and unknown dates remain unknown.
- **I-03:** no new persistent authority or transaction boundary; this is read-only derived analysis.
- **I-05:** one bounded pass over the supplied in-memory historical unit set; no new unbounded external query or service.
- **I-07:** result explicitly exposes unknown-age and unknown-cost counts instead of hiding incomplete evidence.
- **I-08:** targeted suite only; no unrelated full regression rerun.
- **I-09:** READ-only historical intelligence; no external action authority added.

## Risk

Low, isolated analysis-layer risk. The main semantic risk is misreading dataset-relative age as present-day age; the output therefore retains `dataset_cutoff_date` and the implementation never consults wall-clock time.

## Verification

A caller can verify that:

1. the dataset cutoff equals the latest known acquisition/sale date in supplied evidence;
2. active unsold units fall into the expected deterministic age bucket;
3. missing acquisition dates appear under `unknown_age` rather than being inferred;
4. missing cost never contributes to a known capital total;
5. sold/lost/giveaway units remain excluded from active exposure.

## Rollback

Revert the inventory-aging implementation/test commits on the feature branch (`70d249f30a6f2fb8aa50fa56c4dd03ae0167be60`, `3558c148a018e42928955c19d4bf2d55ea5d20e5`, `cc4e8553259100d41c2d8987803e0e8979acfc66`) and the associated documentation-only commits if the slice is rejected. No production rollback is required because nothing was deployed.

## Stopping point

PR #32 remains the active isolated BloomBoss Phase 1 pull request. The inventory-aging slice is targeted-CI green and stays within the already approved Historical Data Intelligence scope.

The high-level PR merge/promotion gate remains separate and is not authorized by the autonomous build instruction.

## Next authorized action

Continue safe Phase-1-scoped historical intelligence improvements in the feature branch, or hold at the existing PR #32 build gate. Do not merge, deploy, access production, use secrets, or create external marketplace/customer actions without the required explicit approval.

PROJECT SAVE: COMPLETE
