# BloomBoss Palmstreet Historical Import

Status: **IN DEVELOPMENT — READ-ONLY STAGING ONLY**

## Goal
Use Palmstreet's official exported order data as the primary historical sales source for BloomBoss, while preserving exact source evidence and avoiding screen scraping.

## Current verified platform facts
- Seller Hub supports filtering and exporting seller orders.
- Ended LIVE/Purge shows support exporting order summaries.
- Buyer purchase history is visible in Palmstreet, but an official buyer-side bulk export has not yet been verified.

## Current implementation
`bloomboss/palmstreet.py` provides:
- source SHA-256 fingerprinting;
- CSV header/row profiling;
- explicit field mapping from a real Palmstreet export;
- read-only sale candidates with platform order and line-item identity;
- row-level provenance;
- duplicate external-identity rejection;
- unknown optional fields preserved as unknown.

## Important boundary
Palmstreet rows are **staged candidates**, not canonical BloomBoss `Sale` records.

The importer does not guess which BloomBoss `PlantUnit` was sold. Inventory reconciliation must happen separately before canonical promotion.

## Why mapping is explicit
Palmstreet's public documentation confirms order export, but does not publish a stable CSV column contract. Therefore BloomBoss does not hard-code guessed headers. The first real BloomBoss export will establish the verified field map.

## Purchase history
BloomBoss also intends to import historical purchases from every connected marketplace when the platform exposes them. For Palmstreet, seller-side export is verified; buyer-side bulk export remains **NEEDS_VERIFICATION**. Until a supported buyer export/source is confirmed, purchase invoices/screenshots may be used as temporary evidence.

## Safety
- no Palmstreet writes;
- no browser scraping;
- no account automation;
- no production deployment;
- no secrets;
- no canonical sale creation before reconciliation.
