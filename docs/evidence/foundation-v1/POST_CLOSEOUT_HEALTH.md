# Foundation v1 — Post-Closeout Health Snapshot

Read-only, captured 2026-09-09 ~06:14–06:20 UTC, after all authorized
production reads and before any repository merges that followed. All
values below are a point-in-time snapshot, not a monitoring feed.

## PostgreSQL (`karmo-postgres` container, 127.0.0.1:5433)

- Container status: `Up 10 days (healthy)` — `pg_isready` confirms accepting connections.
- `conversation_memory`: 16 rows.
- `karmo_memory`: 1 row.
- `public.karmo_outbox`: exists (table, owner `karmo`), 1 row.
- `public.document_registry`: 3 rows.
- No error, no connection failure, no unexpected schema state observed.

## Qdrant (`karmo-qdrant` container, 127.0.0.1:6333)

| Collection | points_count | status |
|---|---|---|
| `karmo_semantic_memory` | 5 | green |
| `karmo_documents` | 8 | green |
| `karmo_h00_dense_baseline` | 8 | green |

All three collections reachable, all `status: green` (Qdrant's own
health indicator — no yellow/red state).

## KARMO service state

- `karmo-h01-relay` (systemd user service, `lofason`): **active (running)**, continuously since 2026-09-06 22:40:28 UTC.
- `loginctl show-user lofason -p Linger`: **Linger=yes**.
- `docker ps --filter name=karmo`: `karmo-postgres` up 10 days (healthy), `karmo-qdrant` up 10 days, `karmo-ollama` up 11 days.

## Application compile/import sanity (read-only)

`python -m py_compile` on every deployed H0.1/H0.2/H0.4 production
application file (`karmo.py`, `memory.py`, `outbox.py`,
`transactional_memory.py`, `router.py`, `semantic_memory.py`,
`document_ingest_h04.py`, `document_memory.py`, `registry_db.py`,
`auditor.py`, `reconciliation.py`, `archive_integrity.py`,
`run_auditor.py`, `bootstrap_legacy_registry.py`): **exit 0**, no syntax
errors on any file.

## H0.4 report-only audit result (context, not a health-check failure)

`run_auditor.py --collection karmo_documents`: `STATUS:
INTEGRITY_FINDINGS_PRESENT` (5 non-legacy findings: 2 `ORPHAN_VECTOR`
matching the already-known, intentionally-unresolved ambiguous legacy
hashes; 3 `ACTIVE_STATE_MISMATCH` traced to an auditor-design gap for
legacy-bootstrapped documents, not a data problem — full detail in
`PRODUCTION_READONLY_VERIFICATION.md` and `FOUNDATION_V1_CLOSEOUT_REPORT.md`).
This does not indicate a service-health problem — the auditor completing
its report-only pass successfully is itself confirmation the app code
path, DB connection, and Qdrant connection are all functioning correctly.

## No unexpected service/container changes

Container uptimes (10–11 days) and the relay's continuous active state
since the recorded 2026-09-06 cutover date are consistent with **no
restart, no redeploy, and no configuration change** having occurred to any
KARMO production service before, during, or as a result of this session's
verification work.
