# PROJECT SAVE — BloomBoss Listing Evidence Integration

Saved: 2026-09-11
Branch: `feat/bloomboss-historical-intelligence`
PR: #32 — `feat: start BloomBoss Historical Data Intelligence`

## Verified this session

- Work remained entirely in approved non-production GitHub/dev scope.
- Production KARMO was not accessed or modified.
- No deployment, merge, secret use, marketplace write, customer action, or OBS action occurred.
- Historical listing evidence remains a separate source stream from realized sales and canonical inventory/sales history.

## Change completed

Historical listing evidence is now integrated into the reproducible read-only import snapshot without collapsing it into sale facts:
- optional listing CSV is independently SHA-256 fingerprinted and size-recorded;
- canonical listing events are included in the snapshot while primary history remains backward-compatible;
- listing-to-inventory/sale relationship issues are included in the snapshot;
- listing completeness reports known/missing listed date, unlisted date, and asking price coverage;
- the read-only report CLI accepts `--listings <path>` and reports both source identities;
- both history and listing source files are proven unchanged by CLI tests.

The existing contradiction checks remain in force: `LISTING_UNIT_MISSING`, `LISTING_BEFORE_ACQUISITION`, and `LISTING_AFTER_SALE`. Unknown values remain unknown; no asking price, date, or sale relationship is inferred.

## Validation

Validated code commit: `b5478aa90075ce0fc6a4aef958fdec046c4c39e9`
GitHub Actions workflow: `BloomBoss Phase 1`
Run: #69
Runner: Ubuntu 24.04
Python: 3.12.14
Pytest: 9.1.1
Result: **32 passed in 0.15s**
Repository permission: contents read-only

## Risk and rollback

Risk is limited to isolated historical import/reporting code and tests. The primary one-file history interface remains supported; optional listing evidence only activates when explicitly supplied.

Rollback: revert the listing-evidence snapshot/report commits or close/remove PR #32 branch changes. No production rollback exists because production was untouched.

## Current stopping point

BloomBoss Phase 1 remains **BUILD GATE READY**. PR #32 is open and mergeable but intentionally unmerged.

## Next action

High-level decision remains whether to merge/promote PR #32. Until that decision, continue only safe isolated Phase 1 improvements that do not expand into production, external marketplace/customer actions, secrets, deployment, or a new high-level capability phase.
