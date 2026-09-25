# PROJECT SAVE — BloomBoss Palmstreet Historical Staging

Date: 2026-09-11

## Decision
Palmstreet is the first marketplace historical-data priority because most BloomBoss sale and purchase history lives there. Etsy remains later and is not a prerequisite for Palmstreet.

## Product direction preserved
- structured marketplace data first;
- screenshots/manual evidence only where structured source access is unavailable;
- import both historical buys and sells when a connected platform exposes both;
- Kamara and Kamara share the same canonical BloomBoss business state;
- device-neutral product direction remains unchanged.

## Implemented in isolated branch
- `bloomboss/palmstreet.py`: read-only Palmstreet CSV profile + staged sale-candidate importer.
- Explicit field mapping instead of guessed Palmstreet headers.
- Source SHA-256, row provenance, external order/line identity, duplicate detection, unknown preservation.
- No canonical sale is created until a Palmstreet line item is reconciled to a BloomBoss inventory unit.
- `tests/test_bloomboss_palmstreet.py`: targeted tests for profiling, mapping, unknown preservation, bad mappings, duplicate identities.
- `docs/bloomboss/PALMSTREET_IMPORT_DESIGN.md`: current boundary and purchase-history status.

## Current blocker / next evidence needed
A real BloomBoss Palmstreet seller order export is needed to lock the actual CSV field map and test against the real structure.

Palmstreet buyer-side bulk purchase export remains NEEDS_VERIFICATION. No scraper will be introduced just to fill that gap.

## Safety
Production access: 0
Palmstreet writes: 0
Browser scraping: 0
Secrets: 0
Deployment: 0
