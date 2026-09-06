# KARMO H0.1 isolated failure-matrix report — H01-T01 through H01-T18

- Date: 2026-09-06
- Branch: `feat/h01-handoff-import`
- Scope: isolated, local, Docker-based PostgreSQL + Qdrant test environment only. No production host, credential, database, Qdrant collection, or document was accessed.
- Frozen design under test: `scripts/h01/h01_isolated_build_v2.sh` (verified H0.1 isolated build, per `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`).

## What this covers

`docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md` names the next
gate as "the isolated H01-T01 through H01-T18 failure matrix using a separate
PostgreSQL test schema and a separate Qdrant test collection," but the specific
18 test cases are not enumerated anywhere in this repository. The 18 tests
below were derived directly from behavior the frozen artifacts already claim
for themselves — the three `failure_stage` rollback hooks documented in
`transactional_memory.remember_exchange`, every `CHECK`/`UNIQUE`/`FOREIGN KEY`
constraint in `migrations/001_h01_karmo_outbox.sql`, and the claim/lease/
fencing/retry semantics documented in `outbox.py` (`FOR UPDATE SKIP LOCKED`,
`wait=True`, `claim_token` fencing, exponential backoff). No new requirement
or behavior was invented, and no frozen file's logic was changed to make a
test pass.

## Environment

Docker was not installed on this Mac. With the user's explicit approval,
Colima + the Docker CLI + Compose plugin were installed via Homebrew
(`brew install colima docker docker-compose`) and started locally
(`colima start`). This is local developer tooling, not a production change.

- `test/h01/docker-compose.yml` — isolated stack, non-default ports:
  - `karmo-h01-test-postgres` (postgres:16-alpine) on `127.0.0.1:55432`, synthetic credentials, database `karmo_h01_test`.
  - `karmo-h01-test-qdrant` (qdrant/qdrant:v1.9.7) on `127.0.0.1:56333`/`56334`.
  - Named Docker volumes `karmo_h01_test_pg_data` / `karmo_h01_test_qdrant_data`, isolated from any other stack.
- Qdrant test collection `karmo_semantic_memory` created with `size=768, distance=Cosine` (matching `DEFAULT_VECTOR_SIZE` in `outbox.py`).

## Files created

- `test/h01/docker-compose.yml` — isolated Postgres + Qdrant stack.
- `test/h01/app/migrations/001_h01_karmo_outbox.sql` — copied **verbatim** from the verified build script's heredoc. SHA-256 `d502699c07b4eed1ea225cbc21d0c3950099818e88afba232b6b1520dac033e8`.
- `test/h01/app/transactional_memory.py` — copied **verbatim**. SHA-256 `33f464d8c71c14ae2d2635dd66dbaf50021e8a4bd283f3d8b8f89d1bcd364395`.
- `test/h01/app/outbox.py` — copied **verbatim**. SHA-256 `55af1192dbae5b1a4ea2d30e36f544dddc290cc470bfba4074c8a846fce87a04`.
  (Byte-for-byte diffed against the heredocs in `scripts/h01/h01_isolated_build_v2.sh`; only added header comments differ.)
- `test/h01/app/migrations/000_synthetic_conversation_memory.sql` — **new**, synthetic-only. The frozen migration assumes `public.conversation_memory` already exists from the frozen v0.5 schema, which this repo does not contain and this agent is not authorized to inspect. This minimal table (id/role/content/created_at) exists only to give the FK a target using the columns `transactional_memory.py` actually reads/writes.
- `test/h01/app/memory.py` — **new** test-only adapter providing `get_connection()` against the isolated Postgres container (env-var configured, synthetic credentials only). Not part of the frozen design; the frozen modules import `memory.get_connection` from the production karmo app, which is not present in this repository.
- `test/h01/conftest.py` — pytest fixtures: per-test schema/collection reset, connection helpers, a deterministic fake embedding function (no real model call).
- `test/h01/tests/test_h01_failure_matrix.py` — the 18 tests (see below).
- `test/h01/requirements.txt`, `test/h01/pytest.ini` — test tooling pins.
- `test/h01/scripts/setup_test_env.sh` — brings up the isolated stack, applies migrations, creates the Qdrant collection.
- `test/h01/scripts/teardown_test_env.sh` — tears down only the `karmo-h01-test-*` containers/volumes.
- `docs/evidence/h01/h01-failure-matrix-run.txt`, `docs/evidence/h01/h01-failure-matrix-junit.xml` — raw test-run evidence.

No file outside `test/h01/`, `docs/evidence/h01/`, and this report was modified. `CURRENT_STATE.md`, `MASTER_BUILD_LOG.md`, and `KARMO_FOUNDATION_HARDENING_PLAN.md` are not present in this repository and were not touched.

## Results: H01-T01 through H01-T18 — 18/18 PASS

| Test | What it verifies | Result |
|---|---|---|
| T01 | Frozen migration applies cleanly to the isolated schema: `karmo_outbox` columns and both partial indexes exist. | PASS |
| T02 | `remember_exchange` happy path: exactly 2 conversation rows + 1 `pending` outbox row, deterministic `event_id`. | PASS |
| T03 | Atomic rollback at `failure_stage="after_user_insert"`: zero rows committed anywhere. | PASS |
| T04 | Atomic rollback at `failure_stage="after_assistant_insert"`: zero rows committed anywhere. | PASS |
| T05 | Atomic rollback at `failure_stage="after_outbox_insert"`: zero rows committed anywhere. | PASS |
| T06 | `event_id_for_user_id` is deterministic (UUID5); `karmo_outbox_delivery_key` UNIQUE constraint rejects a duplicate `(event_type, aggregate_type, aggregate_id, destination)`. | PASS |
| T07 | `karmo_outbox_status_check` rejects an invalid `status` value. | PASS |
| T08 | `karmo_outbox_claim_state_check` rejects `processing` without claim fields, and non-`processing` with claim fields set. | PASS |
| T09 | `karmo_outbox_processed_state_check` rejects `delivered` without `processed_at`, and non-`delivered` with `processed_at` set. | PASS |
| T10 | `karmo_outbox_payload_object_check` rejects a non-object JSON payload. | PASS |
| T11 | `karmo_outbox_nonempty_identity_check` rejects an empty `event_type`. | PASS |
| T12 | `karmo_outbox_conversation_fk` rejects a dangling `aggregate_id`; `ON DELETE RESTRICT` blocks deleting a referenced conversation row. | PASS |
| T13 | `claim_batch` concurrency: two workers claiming concurrently against the same 6 pending rows never claim the same `event_id` (`FOR UPDATE SKIP LOCKED`); stable across 3 repeated runs. | PASS |
| T14 | A `processing` row past its `lease_seconds` is reclaimed by a second worker with a new `claim_token` and incremented `attempt_count`. | PASS |
| T15 | `process_once` happy path: valid digest + embedding + `wait=True` Qdrant upsert → outbox row `delivered`, `processed_at` set, claim fields cleared, matching point present in the isolated Qdrant collection. | PASS |
| T16 | Permanent failure path: authoritative content no longer matches the recorded `content_sha256` → `dead`, `last_error_code=content_digest_mismatch`, no Qdrant point written. | PASS |
| T17 | Transient failure path: embedding call raises → `retry` with `attempt_count` incremented and `available_at` delayed per `retry_delay_seconds`; not reclaimable before `available_at`. | PASS |
| T18 | Fencing: after a stale claim is reclaimed by a second worker (new `claim_token`), the first worker's late `_finish("delivered")` call is rejected (0 rows updated) and the row remains under the second worker's claim. | PASS |

Full raw output: `docs/evidence/h01/h01-failure-matrix-run.txt` and `docs/evidence/h01/h01-failure-matrix-junit.xml` (18 passed, 0 failed, 0 errors, 1 unrelated `urllib3`/`LibreSSL` deprecation warning).

## Security checks

- `grep` for production hostnames/paths (`karmo-ai01`, `lofason`, `192.168.1.235`, `kve01`/`02`/`03`, `/home/lofason`) across `test/`: no matches.
- No SSH session was opened to any host during this work.
- Only two Docker containers were running at any point: `karmo-h01-test-postgres`, `karmo-h01-test-qdrant`. No production container was referenced, started, stopped, or restarted.
- All credentials used are synthetic, hardcoded test-only values scoped to the isolated stack (`karmo_h01_test` / `karmo_h01_test_synthetic_local_only`), not secrets, and not committed anywhere sensitive-looking (`.gitignore` already excludes `.env`, `*.key`, `secrets/`, etc.; none of those patterns matched any new file).
- `py_compile` passed cleanly on every new/copied Python file.
- The 3 frozen artifacts under test were confirmed byte-identical (body diff, excluding added header comments) to the heredocs in the already-verified `scripts/h01/h01_isolated_build_v2.sh` — this test run validates the actual frozen design, not a rewritten copy of it.
- `test/h01/venv/` and `test/h01/.pytest_cache/` are excluded from git (root `.gitignore`'s `venv/` pattern, and pytest's own nested `.pytest_cache/.gitignore`).
- Production database writes / schema changes / Qdrant writes / live application changes / container restarts / service installations: all `0`, as required by `AGENTS.md` and the H0.1 scope note.

## Blockers

None. All H01-T01 through H01-T18 acceptance tests pass.

## How to reproduce

```
cd test/h01
./scripts/setup_test_env.sh     # brings up isolated stack, applies migrations, creates Qdrant collection
venv/bin/python -m pytest -v    # runs H01-T01..T18
./scripts/teardown_test_env.sh  # removes only the karmo-h01-test-* containers/volumes
```

## Recommended next action

H0.1's isolated failure-matrix gate (H01-T01–T18) is satisfied in this local,
non-production environment. Per `AGENTS.md` and this session's scope, the next
step — production migration, live-code wiring, worker service installation,
or any cutover — remains unauthorized here and requires a separate,
explicitly approved cutover decision (Natalie) plus Codex's independent
design/security/evidence review. This report and its raw evidence should be
attached to the pull request for that review; nothing in this session should
be merged or deployed automatically.
