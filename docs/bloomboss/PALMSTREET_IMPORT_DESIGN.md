# BloomBoss Palmstreet Historical Import

Status: **IN DEVELOPMENT — READ-ONLY STAGING ONLY**

## Goal
Use Palmstreet's official exported order data as the primary historical sales source for BloomBoss, while preserving exact source evidence and avoiding screen scraping.

## Current verified platform facts
- Seller Hub supports filtering and exporting seller orders.
- Ended LIVE/Purge shows support exporting order summaries.
- Buyer purchase history is visible in Palmstreet, but an official buyer-side bulk export has not yet been verified.
- The observed Seller Hub Orders table includes Buyer Note and Seller Note fields in addition to order, customer, item, value, shipping, date, status, and source fields.

## Current implementation
`bloomboss/palmstreet.py` provides:
- source SHA-256 fingerprinting;
- CSV header/row profiling;
- explicit field mapping from verified Palmstreet source columns;
- read-only sale candidates with platform order and line-item identity;
- row-level provenance;
- duplicate external-identity rejection;
- unknown optional fields preserved as unknown;
- optional Buyer Note and Seller Note staging as opaque source text.

## Note handling and privacy boundary
Buyer Note and Seller Note can contain operationally useful evidence, but they can also contain customer-entered text. BloomBoss therefore stages these fields without interpreting them for identity matching, financial calculations, customer inference, or automatic actions.

Repository tests use synthetic note values only. Real customer notes must not be copied into source control or project evidence merely to prove the importer works.

## Important boundary
Palmstreet rows are **staged candidates**, not canonical BloomBoss `Sale` records.

The importer does not guess which BloomBoss `PlantUnit` was sold. Inventory reconciliation must happen separately before canonical promotion.

## Why mapping is explicit
Palmstreet's public documentation confirms order export, but does not publish a stable CSV column contract. Therefore BloomBoss does not hard-code an assumed downloadable-export schema. Verified source profiles are mapped explicitly, and future downloadable CSV headers must be confirmed before being treated as stable.

## Purchase history
BloomBoss also intends to import historical purchases from every connected marketplace when the platform exposes them. For Palmstreet, seller-side export is verified; buyer-side bulk export remains **NEEDS_VERIFICATION**. Until a supported buyer export/source is confirmed, purchase invoices/screenshots may be used as temporary evidence.

## Safety
- no Palmstreet writes;
- no browser scraping;
- no account automation;
- no production deployment;
- no secrets;
- no canonical sale creation before reconciliation;
- no real customer note content committed to source control for testing.
