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

Historical listing evidence is integrated into the reproducible read-only import snapshot without collapsing it into sale facts:
- optional listing CSV is independently SHA-256 fingerprinted and size-recorded;
- canonical listing events are included in the snapshot while primary history remains backward-compatible;
- listing-to-inventory/sale relationship issues are included in the snapshot;
- listing completeness reports known/missing listed date, unlisted date, and asking price coverage;
- the read-only report CLI accepts `--listings <path>` and reports both source identities;
- both history and listing source files are proven unchanged by CLI tests.

This session also added deterministic historical listing-activity analytics from listing evidence only:
- total listing-event count and unique units listed;
- count and average of known asking prices;
- count and average duration of listings where both listed/unlisted dates are known;
- the same measures grouped by sales channel;
- no unlisting is treated as a sale, and no listing is matched to a realized sale by inference.

The listing activity summary is now part of `HistoricalImportSnapshot` and the read-only JSON report whenever a listing source is explicitly supplied. Unknown asking prices and incomplete dates remain unknown and are excluded from averages rather than imputed.

The existing contradiction checks remain in force: `LISTING_UNIT_MISSING`, `LISTING_BEFORE_ACQUISITION`, and `LISTING_AFTER_SALE`. Unknown values remain unknown; no asking price, date, or sale relationship is inferred.

## Validation

Validated code commit: `fc559b266a9baac6ebf706b4cb276f429e7b183b`
GitHub Actions workflow: `BloomBoss Phase 1`
Run: #78
Runner: GitHub-hosted Ubuntu
Result: **SUCCESS**; targeted BloomBoss suite passed, including the two new listing-activity tests.
Repository permission: contents read-only

The workflow automatically includes every `tests/test_bloomboss_*.py` file, so the two newly added tests extend the previously validated 32-test set to **34 targeted tests**.

## Risk and rollback

Risk is limited to isolated historical import/reporting code and tests. The primary one-file history interface remains supported; optional listing evidence and listing-activity analytics only activate when explicitly supplied.

Rollback: revert commits `d1b9553`, `07a3524`, `e91d643`, and `fc559b2`, or close/remove PR #32 branch changes. No production rollback exists because production was untouched.

## Current stopping point

BloomBoss Phase 1 remains **BUILD GATE READY**. PR #32 is open and intentionally unmerged pending the high-level merge/promotion decision.

## Next action

High-level decision remains whether to merge/promote PR #32. Until that decision, continue only safe isolated Phase 1 improvements that do not expand into production, external marketplace/customer actions, secrets, deployment, or a new high-level capability phase.
