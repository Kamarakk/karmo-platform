# H0.4 Integrity & Reconciliation — isolated acceptance evidence

- Date: 2026-09-06
- Branch: `feat/h04-integrity-reconciliation`
- Scope: isolated, local, Docker-based PostgreSQL + Qdrant test environment
  only (`h04/docker-compose.yml`, container name prefix `karmo-h04-test-`,
  non-default ports 57432/58333/58334). No production host, credential,
  database, Qdrant collection, or document was accessed.
- Frozen scope: H0.4 Integrity & Reconciliation task brief (PostgreSQL
  document registry, archived-file integrity, PostgreSQL <-> Qdrant
  reconciliation, report-only auditor, recovery). No H0.4 hardening-plan
  document was present in the repository at the time of this run.

## Architecture implemented

- **PostgreSQL document registry** (`h04/app/migrations/001_h04_document_registry.sql`,
  `h04/app/registry_db.py`): `public.document_registry` is the authoritative
  structured record of logical document identity (`document_id`), SHA-256
  content identity (`document_hash`, preserved verbatim from H0.1/H0.2),
  archive location (`archive_source_location`), `expected_chunk_count`,
  `document_version`, `pipeline_version`, `embedding_model`,
  `chunker_version`, `is_active`/`superseded_by`/`created_at`/`deactivated_at`
  provenance, and `source_path`.
- **Archived-file integrity** (`h04/app/archive_integrity.py`): recomputes
  SHA-256 of the file at `archive_source_location` and compares it to
  `document_hash`; reports `MISSING_ARCHIVED_FILE` or
  `ARCHIVED_FILE_HASH_MISMATCH`. Filesystem-read-only.
- **PostgreSQL <-> Qdrant reconciliation** (`h04/app/reconciliation.py`):
  compares each registry row's expected chunk set against the actual
  `chunk_number`s present in Qdrant for that `document_hash`
  (`MISSING_VECTOR`, `INCORRECT_EXPECTED_CHUNK_COUNT`), finds Qdrant points
  whose `document_hash` has no registry row (`ORPHAN_VECTOR`), checks for
  more than one active version of a `document_id` or a Postgres/Qdrant
  active-state disagreement (`MULTIPLE_ACTIVE_VERSIONS`,
  `ACTIVE_STATE_MISMATCH`), and compares registry
  `pipeline_version`/`embedding_model`/`chunker_version` against the values
  actually stored on each Qdrant chunk (`PROVENANCE_MISMATCH`). Qdrant access
  is `.scroll()` only, never `.upsert()`/`.set_payload()`/`.delete()`.
- **Auditor** (`h04/app/auditor.py`): orchestrates the above into one flat
  finding list. Report-only by construction — it calls no PostgreSQL
  UPDATE/DELETE/INSERT and no Qdrant write API. It does not delete, rewrite,
  backfill, deactivate, or reactivate anything.
- **Recovery** (`h04/app/recovery.py`): Qdrant snapshot create/list/recover
  via the native `qdrant_client` snapshot API; PostgreSQL backup via
  `pg_dump --clean --if-exists` run inside the isolated container, with a
  minimal structural verification of the dump file; controlled restore via
  `psql` replay of the verified dump. Recovered-data integrity is verified
  by re-running the same auditor, not a bespoke check.

Intentional non-goal, called out in the migration file: `document_registry`
does **not** hard-enforce "only one active version per `document_id`" as a
DB constraint. That invariant is normally kept by the ingest application
layer (H0.2 supersession); leaving it unenforced in the schema is what
makes a violation of it representable in PostgreSQL, and therefore
detectable by the auditor (`MULTIPLE_ACTIVE_VERSIONS`), rather than simply
impossible to create.

## Reconciliation rules (finding types)

| Finding type | Detected by |
|---|---|
| `MISSING_ARCHIVED_FILE` | `archive_integrity.check_archive` |
| `ARCHIVED_FILE_HASH_MISMATCH` | `archive_integrity.check_archive` |
| `MISSING_VECTOR` | `reconciliation.check_chunk_counts` |
| `DUPLICATE_VECTOR` | `reconciliation.check_chunk_counts` |
| `INCORRECT_EXPECTED_CHUNK_COUNT` | `reconciliation.check_chunk_counts` |
| `ORPHAN_VECTOR` | `reconciliation.find_orphan_vectors` |
| `MULTIPLE_ACTIVE_VERSIONS` | `reconciliation.check_active_version_state` |
| `ACTIVE_STATE_MISMATCH` | `reconciliation.check_active_version_state` |
| `PROVENANCE_MISMATCH` | `reconciliation.check_provenance` |

## Test stack

- `postgres:17-alpine` + `qdrant/qdrant:v1.9.7`, isolated ports
  `127.0.0.1:57432` / `127.0.0.1:58333`/`58334`, container names
  `karmo-h04-test-postgres` / `karmo-h04-test-qdrant`. Synthetic credentials
  only (`karmo_h04_test` / `karmo_h04_test_synthetic_local_only`).
- Isolated Qdrant collection `karmo_h04_test_documents` — never
  `karmo_documents`, `karmo_semantic_memory`, or `karmo_h00_dense_baseline`.
- One acceptance suite, one test per requirement, per the "no overlapping
  suites" working rule: `h04/tests/test_h04_integrity_reconciliation.py`.

## Result

```
10 passed, 1 warning in 1.15s
```

Full run: `docs/evidence/h04/h04-integrity-run.txt`
JUnit XML: `docs/evidence/h04/h04-integrity-junit.xml`

**Acceptance gate: PASS.**

### Inconsistencies successfully detected (one test each)

- `test_healthy_consistent_document_has_no_findings` — healthy consistent
  document produces zero findings.
- `test_missing_archived_file_detected` — `MISSING_ARCHIVED_FILE`.
- `test_archived_file_hash_mismatch_detected` — `ARCHIVED_FILE_HASH_MISMATCH`.
- `test_missing_qdrant_vector_detected` — `MISSING_VECTOR`.
- `test_orphan_qdrant_vector_detected` — `ORPHAN_VECTOR`.
- `test_incorrect_expected_chunk_count_detected` — `INCORRECT_EXPECTED_CHUNK_COUNT`
  (distinguished from `MISSING_VECTOR`: extra chunk beyond the expected
  count, not a gap in it).
- `test_multiple_active_versions_detected` — `MULTIPLE_ACTIVE_VERSIONS`.
- `test_provenance_version_mismatch_detected` — `PROVENANCE_MISMATCH`.
- `test_auditor_is_report_only` — proves the auditor still finds a real
  `MISSING_VECTOR` inconsistency with every PostgreSQL write statement and
  every Qdrant write API (`upsert`/`set_payload`/`delete`/`delete_collection`)
  replaced with a hard failure, i.e. the audit path never calls them.

### Backup/restore result

`test_backup_snapshot_corruption_restore_integrity_workflow`: created a
Qdrant snapshot and a verified `pg_dump` backup of a healthy document,
corrupted both stores independently (deleted a Qdrant point, mutated
`pipeline_version` in PostgreSQL), confirmed the auditor caught both
(`MISSING_VECTOR` and `PROVENANCE_MISMATCH`), restored Qdrant from the
snapshot and PostgreSQL from the verified dump, and confirmed the same
auditor then reports **zero findings** — the restore reproduced the
pre-corruption state. **PASS.**

## Correction made during this work: recovery-drill hang

The first full-suite run of the recovery test hung indefinitely (observed
past 11 minutes) instead of failing or passing. Diagnosis via
`pg_stat_activity` on the isolated Postgres container found the exact cause:
the test's `pg_conn` was left `idle in transaction` after a prior
`auditor.run_audit(...)` call — a read-only `SELECT`, but `psycopg` does not
implicitly end a transaction after one. That open transaction held a read
lock on `document_registry`, which blocked the restore step's
`docker exec ... psql` connection forever on the `DROP TABLE
public.document_registry` statement generated by `pg_dump --clean
--if-exists`, since nothing was ever going to commit or roll back the first
connection's transaction.

This was a test-code issue, not an `h04/app/` defect: `auditor.py` correctly
performs only reads. The fix adds `pg_conn.rollback()` in
`test_backup_snapshot_corruption_restore_integrity_workflow` immediately
after each `run_audit` call that precedes the restore's DDL, so the test
itself closes its own read transaction before triggering out-of-band
schema changes on a separate connection. No `h04/app/` file was changed to
make this fix. After the fix, the single affected test was reverified alone
(`1 passed in 0.72s`), and the full suite was then run exactly once more —
the run recorded in this report (`10 passed, 1 warning in 1.22s`) — with no
other test rerun.

## Pre-commit review and fixes

A `/code-review` pass (medium effort) over `h04/` before commit surfaced
three findings:

1. **Fixed** — `reconciliation.check_chunk_counts` compared chunk_number
   *sets*, so a duplicated/corrupted vector sharing an existing
   chunk_number (e.g. actual points `[1, 1, 2, 3]` against
   `expected_chunk_count=3`) was invisible: both `MISSING_VECTOR` and
   `INCORRECT_EXPECTED_CHUNK_COUNT` were skipped because the *distinct*
   chunk_number set still matched expectations. Added a `DUPLICATE_VECTOR`
   finding (chunk_number backed by more than one point) and switched the
   count comparison to the actual point count rather than the distinct-set
   size, so a duplicate no longer masks itself as a healthy count.
2. **Fixed** — `auditor.run_audit` fetched each document_hash's Qdrant
   points twice: once in the main per-row loop, once again to build input
   for `check_active_version_state`. Now the first loop's result is cached
   (`points_by_hash`) and reused, halving Qdrant round-trips per audit with
   no behavior change.
3. **Deferred at the time, then fixed post-approval** — `reconciliation.actual_chunk_points`/
   `all_points` used `qdrant_client.scroll(..., limit=10000)` and discarded
   the pagination cursor, so a document with more than 10000 chunks, or a
   collection with more than 10000 total points, would silently truncate.
   At review time this matched the existing pattern already accepted
   elsewhere in this repository (e.g. `docs/handoff/h04/document_ingest.py`'s
   `active_points_for_document` and H0.2's `get_document_history`, both
   `limit=10000` with the offset discarded), so it was left as-is and
   flagged as a known production-scale gap rather than fixed under frozen
   scope. After H0.4 acceptance was approved (10/10 PASS), this gap was
   resolved as a separate, explicitly requested follow-up — see "Pagination
   fix (post-approval)" below.

Findings 1 and 2 above are contained to `h04/app/reconciliation.py` and
`h04/app/auditor.py`. The full suite was rerun once after applying them
(10 passed, 1 warning in 1.15s) — this is the run recorded in this report;
no test needed changes for either fix.

## Pagination fix (post-approval)

After H0.4 acceptance was approved (10/10 PASS, recorded above), the one
known production-scale gap called out in the pre-commit review (item 3) was
resolved before commit, per explicit instruction. This did not change any
reconciliation rule, finding type, or the report-only guarantee, and did not
touch `docs/handoff/h04/`.

**Fix:** `h04/app/reconciliation.py` replaced the single bounded
`qdrant_client.scroll(..., limit=10000)` call in `actual_chunk_points` and
`all_points` with a new `_scroll_all` helper that loops on Qdrant's
`next_page_offset` until it is `None`, so every point in the applicable
scope (one document's chunks, or the whole collection for orphan detection)
is read regardless of how many pages that takes. The per-call page size is
now a parameter (`page_size`, default `1000`, plumbed through
`find_orphan_vectors` and `auditor.run_audit`) rather than a hardcoded
`10000` — it bounds one round-trip's response size only, not the total
number of points examined. Still `.scroll()` only: no `.upsert()`,
`.set_payload()`, `.delete()`, or any other Qdrant/PostgreSQL write was
added.

**Targeted result:** one new test,
`h04/tests/test_h04_pagination.py::test_reconciliation_paginates_across_multiple_scroll_pages`,
kept separate from the frozen acceptance suite (it verifies this one fix,
not a reconciliation-rule scenario). It registers 3 healthy documents at
Qdrant point ids 1-3 and adds one unregistered orphan point at id 4, then
runs `auditor.run_audit(..., page_size=2)` against the isolated stack —
too small a page to read all 4 points in one scroll call. A counting wrapper
around `qdrant_client.scroll` confirms more than one unfiltered
(collection-wide) scroll call was made, and the audit still correctly
reports exactly one `ORPHAN_VECTOR` finding for point id 4 — the point that
only appears once the second page is read — with no spurious findings for
the three healthy documents on page 1.

```
tests/test_h04_pagination.py::test_reconciliation_paginates_across_multiple_scroll_pages PASSED
1 passed, 1 warning in 0.15s
```

Full run: `docs/evidence/h04/h04-pagination-run.txt`. Per instruction, the
full H0.4 acceptance suite was **not** rerun for this change — only this one
targeted test was executed, against the isolated stack brought up and torn
down for that purpose.

## Files created

- `h04/app/migrations/001_h04_document_registry.sql`
- `h04/app/registry_db.py`
- `h04/app/archive_integrity.py`
- `h04/app/reconciliation.py`
- `h04/app/auditor.py`
- `h04/app/recovery.py`
- `h04/docker-compose.yml`
- `h04/requirements.txt`
- `h04/pytest.ini`
- `h04/conftest.py`
- `h04/scripts/setup_test_env.sh`
- `h04/scripts/teardown_test_env.sh`
- `h04/tests/test_h04_integrity_reconciliation.py`
- `h04/tests/test_h04_pagination.py`
- `docs/evidence/h04/H04_INTEGRITY_RECONCILIATION_REPORT.md` (this file)
- `docs/evidence/h04/h04-integrity-run.txt`
- `docs/evidence/h04/h04-integrity-junit.xml`
- `docs/evidence/h04/h04-pagination-run.txt`

No file under `docs/handoff/h04/` (the captured production references) was
modified.

## Verification commands

```
cd h04
./scripts/setup_test_env.sh
venv/bin/python -m pytest -v
./scripts/teardown_test_env.sh
```

## Not in scope / not performed

- No production access, SSH, Docker socket, production database, or
  production Qdrant instance was used.
- No automatic deletion, rewrite, backfill, deactivation, or reactivation of
  authoritative data by the auditor — verified directly by
  `test_auditor_is_report_only`, not just asserted.
- No commit, push, merge, or deploy was performed.
