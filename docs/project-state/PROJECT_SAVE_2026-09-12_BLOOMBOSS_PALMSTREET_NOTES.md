# PROJECT SAVE — BloomBoss Palmstreet Seller Hub Notes

Date: 2026-09-12
Workstream: BloomBoss Historical Data Intelligence (Phase 1)
PR: #32
Branch: `feat/bloomboss-historical-intelligence`
Status: **IMPLEMENTED IN ISOLATED DEV — VALIDATION PENDING**

## Purpose

Complete the next recorded Phase 1 Palmstreet staging refinement by representing the verified Seller Hub `Buyer Note` and `Seller Note` fields without introducing real customer PII into source control or allowing free-text notes to influence canonical matching or financial logic.

## Invariant impact / authority check

- I-01 compatibility: existing field maps remain valid because both new mappings are optional.
- I-03 data authority: Palmstreet notes remain staged source evidence only; no canonical `Sale` promotion occurs.
- I-05 bounded resources: no new collection or unbounded processing path was introduced.
- I-07 observability: existing row provenance/source fingerprinting continues to identify the source row.
- I-08 validation: targeted Palmstreet tests cover the changed behavior; the existing Phase 1 workflow supplies the appropriate branch gate.
- I-09 authority/privacy: notes are read-only staged text. They do not authorize external actions, customer inference, or marketplace writes. Tests contain synthetic values only.

## Change

- Added optional `buyer_note` and `seller_note` mappings to `PalmstreetFieldMap`.
- Added optional staged note fields to `PalmstreetSaleCandidate`.
- Extended the verified Seller Hub Orders mapping to `Buyer Note` and `Seller Note`.
- Notes are whitespace-normalized only; they remain opaque text and are not parsed for matching, financial calculation, or customer inference.
- Added targeted synthetic tests for populated and absent notes.
- Updated the Palmstreet import design with the note-handling/privacy boundary.

## Risk

Low and isolated. The main risk is accidentally treating customer-entered note text as trusted structured data. The implementation explicitly avoids that behavior and preserves backward compatibility because the new fields are optional.

## Verification

Validation is pending the GitHub Actions run for the resulting branch commit. A failing targeted run blocks the Phase 1 gate and must be fixed before the gate can remain READY.

## Rollback

Revert the isolated commit containing this change. No production, marketplace, customer, or secret state is touched.

PROJECT SAVE: PENDING VALIDATION
Persistent records updated: this save plus `docs/bloomboss/PALMSTREET_IMPORT_DESIGN.md`
Durable Git commit: recorded by the commit containing this file
Current stopping point: Palmstreet note staging implemented; branch validation pending
Next action: verify the targeted GitHub Actions result, then refresh the Phase 1 gate status if green.
