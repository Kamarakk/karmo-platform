# KARMO H0.1 isolated failure-matrix report — H01-T01 through H01-T18

- Date: 2026-09-06 (corrected; closeout decision recorded 2026-09-06); test-hardening correction and evidence regeneration 2026-09-12
- Branch: `feat/h01-handoff-import` (test-hardening correction applied on `staging/karmo-full-predeploy-20260912`)
- Scope: isolated, local, Docker-based PostgreSQL + Qdrant test environment only. No production host, credential, database, Qdrant collection, or document was accessed.
- Frozen design under test: `scripts/h01/h01_isolated_build_v2.sh` (verified H0.1 isolated build, per `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`).

## Closeout decision (Kamara, 2026-09-06)

Kamara has reviewed this corrected report and accepts the validation level
achieved:

- **H01-T02 through H01-T17: PASS.**
- **H01-T01 and H01-T18 remain recorded as BLOCKED / NOT EXECUTED.** They are
  *not* changed to PASS — production-read-only verification for these two was
  intentionally not performed in this or any prior session.
- Kamara accepts the residual verification risk this leaves (the live
  production/host manifest and baseline reverification described below
  remains outstanding) and has decided that H01-T01/H01-T18 will **not**
  block moving to the next development phase.
- **This decision is not authorization for production deployment or
  cutover.** Production migration, live-code wiring, worker service
  installation, and cutover remain separately gated per `AGENTS.md` and the
  handoff doc, unaffected by this decision.

## Test-hardening correction (2026-09-12)

A code review of `test/h01/tests/test_h01_failure_matrix.py` (the suite
described in the "Correction notice" below) found three plausible
robustness/coverage gaps in the *test code itself* — not in the frozen
`test/h01/app/` implementation, which this pass did not touch:

1. **H01-T17** compared an application-side wall-clock timestamp
   (`datetime.now(timezone.utc)`, taken in the Python test process) against
   a Postgres-side `processed_at` timestamp (taken inside the Docker
   container). A host/container clock skew — e.g. the known Docker Desktop
   VM-clock-drift behavior after host sleep/resume — could produce a
   negative or inflated latency reading unrelated to actual delivery
   performance.
2. **H01-T10** proved "same point is replaced" by calling the relay's
   private `_upsert` helper three times directly, never exercising
   `claim_batch` / `_finish`. A regression in how a full delivery cycle
   derives or reuses the Qdrant point ID would not have been caught.
3. **H01-T06 / H01-T07** simulated an unavailable embedding endpoint /
   Qdrant target by opening a real socket to `127.0.0.1:1`, which depends on
   how the local sandbox or CI network policy handles connections to unused
   loopback ports (refuse vs. drop vs. block) rather than on deterministic
   test behavior.

All three were fixed in `test/h01/conftest.py` and
`test/h01/tests/test_h01_failure_matrix.py`:

- H01-T17 now times each event's claim → deliver cycle with a single
  in-process `time.monotonic()` measurement, eliminating the cross-clock
  comparison. The per-event `healthy_delivery_deadline_seconds` requirement
  is preserved.
- H01-T10 now drives two full `claim_batch → _authoritative_user_content →
  _embedding → _upsert` cycles through real `OutboxRelay` instances
  (crashing before `_finish`, forcing lease-recovery redelivery — the same
  mechanism as H01-T08/H01-T09), followed by a third worker completing the
  real `process_once` finish path. Three genuine deliveries through the
  actual relay code path, collapsing to one Qdrant point.
- `unavailable_embedding_endpoint` and `unavailable_qdrant_client` in
  `conftest.py` now raise deterministically (`ConnectionRefusedError`, and a
  minimal `_UnavailableQdrantClient.upsert` raising `ConnectionError`)
  instead of depending on real socket/network refusal behavior. The
  assertions in H01-T06/H01-T07 and the frozen `outbox.py`/
  `transactional_memory.py` implementation were not changed.

No file under `test/h01/app/` was edited by this pass. SHA-256 of all three
frozen artifacts is unchanged from every prior report:

- `migrations/001_h01_karmo_outbox.sql`: `d502699c07b4eed1ea225cbc21d0c3950099818e88afba232b6b1520dac033e8`
- `transactional_memory.py`: `33f464d8c71c14ae2d2635dd66dbaf50021e8a4bd283f3d8b8f89d1bcd364395`
- `outbox.py`: `55af1192dbae5b1a4ea2d30e36f544dddc290cc470bfba4074c8a846fce87a04`

New SHA-256 of the two changed test-harness files:

- `test/h01/tests/test_h01_failure_matrix.py`: `2353c7cfd5f960a9a369b8166cc7afb0608675caa0c87f6e56a9ecc6f8fcb668`
- `test/h01/conftest.py`: `42f1c846ae710ff37e0223b36085ef37c87fa5a8c20e416bacc6cf71d4947fe1`

The full matrix was re-run against a fresh isolated Docker Postgres +
Qdrant stack after these fixes:
**19 passed, 2 skipped, 0 failed** — identical pass/skip set to the
2026-09-06 result below. H01-T01 and H01-T18 still skip in this isolated
suite for the same reason as before (it does not reach out to production);
this pass did not change that skip logic. Their production-read-only
components were separately authorized, performed, and passed on
2026-09-09 — see the "Later resolution" note below the BLOCKED
explanation. Raw
evidence (`docs/evidence/h01/h01-failure-matrix-run.txt`,
`docs/evidence/h01/h01-failure-matrix-junit.xml`) was regenerated in place
from this run.

This is a test-code hardening correction only. It does not change the
2026-09-06 closeout decision above, does not touch frozen H0.1 design or
acceptance criteria, and is not authorization for production migration,
live-code wiring, worker service installation, or cutover.

## Correction notice

An independent review found the original version of this report and its
18-test suite (`test/h01/tests/test_h01_failure_matrix.py`, commit
`b38c851`) **did not match** the frozen matrix now present at
`docs/handoff/h01/frozen-design/FAILURE-TEST-MATRIX-H01.md` and
`docs/handoff/h01/frozen-design/acceptance-criteria-h01.json`. That earlier
suite was derived from implementation behavior (migration constraints, the
relay's internal claim/lease mechanics) rather than from the frozen matrix's
18 named scenarios, so its test IDs, scenarios, and pass claims did not
correspond to H01-T01–T18 as frozen. **The prior report's "18/18 PASS against
the frozen matrix" claim was incorrect: it verified a different, self-authored
matrix, not the frozen one.**

This report supersedes it. The test suite has been replaced so each
`test_h01_t<NN>_*` function corresponds exactly, by ID, scenario, injection,
and required result, to the corresponding row of the frozen matrix. A few
migration-constraint tests from the old suite that are still useful defect
coverage, but are not rows in the frozen matrix, were kept and clearly
relabeled `test_supplementary_*` so they cannot be mistaken for frozen-matrix
results.

## Isolated stack changes made in this correction

- PostgreSQL bumped from `postgres:16-alpine` to `postgres:17-alpine` in
  `test/h01/docker-compose.yml`, to match the verified production major
  version. Confirmed running: `server_version = 17.11`.
- The isolated Qdrant collection was renamed from `karmo_semantic_memory`
  (which collides with the real production collection name) to
  **`karmo_h01_outbox_test`**, in `test/h01/conftest.py` and
  `test/h01/scripts/setup_test_env.sh`. Every `OutboxRelay` construction in
  the test suite now passes `collection_name="karmo_h01_outbox_test"`
  explicitly (the frozen `outbox.py` itself is unmodified and still defaults
  to `karmo_semantic_memory`, which is correct for production — only the test
  call sites were changed to override it).
- No file under `test/h01/app/` (the verbatim frozen artifacts) was edited.
  SHA-256 of all three is unchanged from the original import:
  - `migrations/001_h01_karmo_outbox.sql`: `d502699c07b4eed1ea225cbc21d0c3950099818e88afba232b6b1520dac033e8`
  - `transactional_memory.py`: `33f464d8c71c14ae2d2635dd66dbaf50021e8a4bd283f3d8b8f89d1bcd364395`
  - `outbox.py`: `55af1192dbae5b1a4ea2d30e36f544dddc290cc470bfba4074c8a846fce87a04`
  No frozen test exposed a defect in the implementation, so per the
  corrective instructions the implementation was preserved unchanged.

## Frozen-test-ID mapping

| Frozen ID | Frozen scenario | Test function | Local result |
|---|---|---|---|
| H01-T01 | Evidence continuity | `test_h01_t01_evidence_continuity` | **BLOCKED** (partial pass, see below) |
| H01-T02 | Fail after user insert | `test_h01_t02_fail_after_user_insert` | PASS |
| H01-T03 | Fail after assistant insert | `test_h01_t03_fail_after_assistant_insert` | PASS |
| H01-T04 | Fail after outbox insert | `test_h01_t04_fail_after_outbox_insert` | PASS |
| H01-T05 | Successful atomic exchange | `test_h01_t05_successful_atomic_exchange` | PASS |
| H01-T06 | Ollama unavailable | `test_h01_t06_ollama_unavailable` | PASS |
| H01-T07 | Qdrant unavailable | `test_h01_t07_qdrant_unavailable` | PASS |
| H01-T08 | Crash before Qdrant write | `test_h01_t08_crash_before_qdrant_write_reclaimed` | PASS |
| H01-T09 | Crash after Qdrant write | `test_h01_t09_crash_after_qdrant_write_before_delivered_update` | PASS |
| H01-T10 | Duplicate delivery | `test_h01_t10_triple_duplicate_delivery` | PASS |
| H01-T11 | Claim-token fencing | `test_h01_t11_claim_token_fencing` | PASS |
| H01-T12 | Concurrent workers | `test_h01_t12_concurrent_workers_twenty_events` | PASS |
| H01-T13 | Malformed permanent event | `test_h01_t13_malformed_permanent_payload` | PASS |
| H01-T14 | Restart recovery | `test_h01_t14_restart_recovery_mixed_states` | PASS |
| H01-T15 | Behavior preservation | `test_h01_t15_user_only_semantic_promotion` | PASS |
| H01-T16 | Digest integrity | `test_h01_t16_digest_mismatch_marks_dead` | PASS |
| H01-T17 | Healthy delivery latency | `test_h01_t17_healthy_delivery_latency` | PASS |
| H01-T18 | Baseline and rollback drill | `test_h01_t18_baseline_and_rollback_drill` | **BLOCKED** (partial pass, see below) |

Raw evidence: `docs/evidence/h01/h01-failure-matrix-run.txt`,
`docs/evidence/h01/h01-failure-matrix-junit.xml` (regenerated 2026-09-12
against the hardened suite described above)
(**19 passed, 2 skipped, 0 failed** — the 2 skips are H01-T01 and H01-T18's
production-baseline components, described next).

## H01-T01 and H01-T18 — why they are BLOCKED, not PASS

Both frozen rows require reverifying **live production/host state**:

- **H01-T01** ("Reverify H0.0 and every H0.1 manifest") needs
  `MANIFEST-H0-FINAL.sha256` and `MANIFEST-H01-ISOLATED-BUILD.sha256`, which
  live only on the production host (`karmo-ai01`) per
  `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`. They are
  not present in this repository.
- **H01-T18** ("Reverify live counts/hashes ... rollback drill") needs the
  production PostgreSQL baseline (`conversation_memory=14`, `karmo_memory=1`,
  no `karmo_outbox`) and Qdrant baseline (`karmo_semantic_memory=4`,
  `karmo_documents=8`, `karmo_h00_dense_baseline=8`) from the same handoff
  doc, reverified live.

Per this session's corrective instructions and `AGENTS.md` ("Never access or
modify production KARMO from an AI session"), this session does not silently
reach out to production to get that data. Each test asserts everything that
**is** locally verifiable, then calls `pytest.skip(...)` with an explicit
message, so the test suite records these as blocked rather than misreporting
them as passed or silently omitting them:

- `test_h01_t01_evidence_continuity` verifies locally: both frozen-design
  documents are present, `acceptance-criteria-h01.json.required_test_ids`
  exactly equals `H01-T01`..`H01-T18`, `status == "frozen_for_review"`,
  `implementation_authorized == False`, and that the body of each of the 3
  frozen artifacts under `test/h01/app/` is byte-identical to the
  corresponding heredoc in `scripts/h01/h01_isolated_build_v2.sh` (i.e. no
  local drift from the verified isolated build). It then skips with a message
  stating the live-manifest component is blocked pending Kamara's approval.
- `test_h01_t18_baseline_and_rollback_drill` verifies locally: the frozen
  acceptance criteria still forbid automatic event deletion and legacy
  backfill and still require rollback to preserve outbox evidence; the
  teardown script only ever names `karmo-h01-test-*` resources and contains
  no production hostname/address; and, as a non-destructive drill on the
  isolated stack, that delivering one event and then separately dead-lettering
  an unrelated malformed event leaves the first event's row and Qdrant point
  completely untouched. It then skips with a message stating the live
  production-baseline component is blocked pending Kamara's approval.

**Recommended next action for T01/T18:** a separate, explicitly-approved,
read-only session (Kamara) reverifies the production PostgreSQL/Qdrant
baseline counts and the two manifest files against the values recorded in the
handoff doc. Nothing in this session performed or attempted that access.

**Later resolution (2026-09-09, recorded here for continuity, not altered
above):** the production-read-only component described above was
subsequently performed under a separate, explicit, task-specific,
read-only Production Access Authorization from Kamara (KARMO Foundation
v1 closeout, Workload 2) and **passed** — both the H0.0/H0.1 manifest
reverification and the production PostgreSQL/Qdrant baseline count
reverification. Full detail, commands, and timestamps:
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`; see also
`docs/project-state/CURRENT_STATE.md`'s H0.1 section and
`docs/project-state/CHANGE_LOG.md`'s 2026-09-09 Foundation v1 closeout
entry. This 2026-09-06 section is left as-written above as the historical
record of what this isolated test suite alone could verify at the time;
the isolated suite's H01-T01/H01-T18 `pytest.skip` calls are unchanged and
still correctly do not reach out to production themselves.

## Files changed in this correction

- `test/h01/docker-compose.yml` — Postgres 16 → 17.
- `test/h01/conftest.py` — isolated collection renamed to
  `karmo_h01_outbox_test`; added `unavailable_embedding_endpoint`,
  `unavailable_qdrant_client`, and `drain` helpers for the new failure
  scenarios.
- `test/h01/scripts/setup_test_env.sh` — isolated collection renamed to
  `karmo_h01_outbox_test`.
- `test/h01/tests/test_h01_failure_matrix.py` — replaced; 18 tests re-mapped
  one-to-one to the frozen matrix by ID, plus 3 clearly-labeled supplementary
  regression tests for migration constraints not enumerated as their own
  frozen rows.
- `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md` (this file),
  `docs/evidence/h01/h01-failure-matrix-run.txt`,
  `docs/evidence/h01/h01-failure-matrix-junit.xml` — regenerated.

No file under `test/h01/app/` (the frozen artifacts) was modified. No file
outside `test/h01/`, `docs/evidence/h01/`, and this report was modified.
`CURRENT_STATE.md`, `MASTER_BUILD_LOG.md`, and
`KARMO_FOUNDATION_HARDENING_PLAN.md` are not present in this repository and
were not touched. `docs/handoff/h01/frozen-design/` was read only, never
written.

## Security checks

- `grep` for production hostnames/paths (`karmo-ai01`, `lofason`,
  `192.168.1.235`, `kve01`/`02`/`03`, `/home/lofason`) across `test/`: no
  matches.
- No SSH session was opened to any host during this work.
- Only two Docker containers were running at any point:
  `karmo-h01-test-postgres` (now `postgres:17-alpine`),
  `karmo-h01-test-qdrant`. No production container was referenced, started,
  stopped, or restarted.
- All credentials used are synthetic, hardcoded test-only values scoped to
  the isolated stack (`karmo_h01_test` / `karmo_h01_test_synthetic_local_only`).
- The isolated Qdrant collection used for all writable test activity is
  `karmo_h01_outbox_test`; `karmo_semantic_memory`, `karmo_documents`, and
  `karmo_h00_dense_baseline` were never targeted for writes.
- Production database writes / schema changes / Qdrant writes / live
  application changes / container restarts / service installations: all `0`.
- No commit, push, merge, deploy, or edit to any authoritative KARMO project
  document was made in this session, per the corrective instructions.

## How to reproduce

```
cd test/h01
./scripts/teardown_test_env.sh   # if an older (postgres:16) stack is running
./scripts/setup_test_env.sh      # brings up isolated stack (postgres:17), applies migrations, creates karmo_h01_outbox_test
venv/bin/python -m pytest -v     # runs H01-T01..T18 (T01/T18 show as SKIPPED — blocked, not failed)
./scripts/teardown_test_env.sh   # removes only the karmo-h01-test-* containers/volumes
```

## Recommended next action

16 of 18 frozen tests (H01-T02–T17) pass locally against the isolated,
Postgres-17-backed stack with no defects found in the preserved
implementation. H01-T01 and H01-T18 were BLOCKED / NOT EXECUTED in this
isolated suite on their production-read-only components as of 2026-09-06.
Per the closeout decision above, Kamara accepted that residual risk and
cleared H0.1 to proceed to the next development phase on that basis. That
outstanding production-read-only reverification was subsequently performed
and passed on 2026-09-09 under a separate, explicit, read-only Production
Access Authorization (see the "Later resolution" note above) —
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md` is now
the authoritative record for that component; this file's own isolated
H01-T01/H01-T18 tests still skip by design, since they must never reach
out to production themselves.

This closeout is **not** authorization for production migration, live-code
wiring, worker service installation, or cutover — those remain unauthorized
and separately gated per `AGENTS.md` and the handoff doc. This report and its
evidence should be attached to the pull request for the next independent
review.
