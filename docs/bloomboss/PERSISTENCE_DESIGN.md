# BloomBoss Phase 1 — Durable Persistence Design

Status: **DESIGN ONLY — NO PRODUCTION DATABASE OR MIGRATION**

## Purpose

Define how Historical Data Intelligence can become durable without losing the raw evidence, inventing missing historical facts, or making import replay unsafe.

## Data authority

The raw historical source file remains immutable evidence. A normalized canonical record is a derived representation of that evidence, not a replacement for it.

Each imported source should be identified by a SHA-256 digest of its exact bytes. The digest is the stable source identity for replay and provenance checks.

## Proposed local/dev persistence model

A future isolated development persistence layer should separate:

1. `historical_source` — source digest, original filename, byte size, import timestamp, parser/schema version.
2. `import_run` — deterministic source identity plus parser version, status, failure reason, record counts, validation counts.
3. `purchase_batch` — canonical batch facts with explicit nullable historical fields.
4. `plant_unit` — one authoritative inventory identity per reconstructed plant unit.
5. `sale` — realized sale facts linked to one inventory unit.
6. `status_event` — historical lifecycle events when independently known.
7. `provenance` — source digest + row/reference linking each canonical fact back to evidence.

Raw source bytes should be stored separately from canonical tables/files so normalization can be rebuilt without rewriting the evidence.

## Idempotency and replay

Import identity should be based on:

`source_sha256 + parser_schema_version`

Replaying the same source under the same parser version must not create duplicate canonical records. A newer parser version may produce a new import run while retaining the earlier run for auditability.

Stable business IDs (`batch_id`, `unit_id`, `sale_id`) remain the canonical identity inside one reconstructed history. Conflicting reuse of those IDs fails visibly rather than overwriting prior facts.

## Transaction boundary

One source import should be treated as one logical operation.

For a future database implementation:

- record the source/import-run identity first;
- stage canonical records and validation results inside one database transaction where practical;
- commit canonical data only after structural parsing succeeds;
- relationship/data-quality issues may be persisted as visible findings when they do not make the source structurally unreadable;
- a parser failure must leave no partially promoted canonical dataset.

No claim of atomicity is made across a database and external raw-file storage. The source digest is the reconciliation key between them.

## Mixed-state compatibility

Historical records are expected to be incomplete. Nullable fields are a supported state, not a migration defect.

Future schema additions must tolerate older imports that lack the new field. New fields default to unknown unless evidence exists; backfill must never invent a financial or historical fact.

## Scale and resource bounds

The current 7–9 month history is small enough for the in-memory canonical loader. Source hashing is streamed in bounded chunks.

A production-scale importer must not load unlimited source files, rows, or history into memory. Before promotion, define file-size limits or streaming ingestion and paginate database reads that mean ALL records.

## Observability

Each durable import should expose:

- source digest and source filename;
- parser/schema version;
- started/completed/failed state;
- batch/unit/sale counts;
- structural parse failure reason;
- relationship issue counts and codes;
- completeness/coverage metrics;
- exact import-run identity.

Unknown historical values must remain distinguishable from errors.

## Rollback

Before production exists, rollback is branch/file removal only.

For a future durable development database, rollback of one import should remove only canonical records owned by that import run while retaining the raw source evidence and import audit record. Cross-import shared business identities require an explicit reconciliation design before destructive rollback is allowed.

## Promotion blockers

Do not implement or deploy production persistence until all of the following are separately reviewed:

- actual production data store and execution model;
- schema/migration and mixed-state behavior;
- import replay/idempotency acceptance tests;
- raw-source storage location and access controls;
- rollback/reconciliation procedure;
- production access authorization.

This document does not authorize a production database, migration, deployment, or secret use.
