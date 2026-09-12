# PROJECT SAVE — H0.1 Isolated Failure-Matrix Test Hardening

Saved: 2026-09-12
Branch: `staging/karmo-full-predeploy-20260912`
PR: none opened this session (pushed to branch only, per explicit instruction not to merge or deploy)

## Scope

This session performed a code review of the H0.1 isolated failure-matrix
test suite (`test/h01/tests/test_h01_failure_matrix.py`,
`test/h01/conftest.py`) — the pre-cutover acceptance suite whose PASS/BLOCKED
results are recorded in `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md` and
whose closeout Natalie already accepted on 2026-09-06. H0.1's production
cutover completed separately on 2026-09-07/08, and Foundation v1 closeout
(2026-09-09) separately resolved the two BLOCKED production-read-only
components. **This session touched none of that.** It is a retroactive
quality-hardening pass on the isolated test code only, done at Kamara's
request after a code review surfaced three plausible robustness/coverage
gaps.

## Work completed this session

1. **Code review** of `test_h01_failure_matrix.py` against the frozen
   matrix (`docs/handoff/h01/frozen-design/FAILURE-TEST-MATRIX-H01.md`,
   `acceptance-criteria-h01.json`) and the frozen `test/h01/app/`
   implementation. Confirmed the H01-T01–T18 ID/scenario/result mapping is
   still accurate; found three test-code findings (none in the frozen
   implementation):
   - **H01-T17**: latency assertion compared an application-side
     (`datetime.now(timezone.utc)`) timestamp against a Postgres-container
     timestamp — host/container clock skew could produce a false pass or
     fail unrelated to actual delivery latency.
   - **H01-T10**: "duplicate delivery" was proved by three direct calls
     into the relay's private `_upsert` helper, never exercising
     `claim_batch`/`_finish` — a regression in the real delivery cycle's
     point-ID handling would not have been caught.
   - **H01-T06/H01-T07**: fault injection depended on connecting to
     `127.0.0.1:1` and observing real OS-level connection-refusal behavior,
     which varies across sandboxed/CI network policies.
2. **Fixed all three** in `test/h01/conftest.py` and
   `test/h01/tests/test_h01_failure_matrix.py`:
   - T17 now measures each event's claim→deliver cycle with a single
     in-process `time.monotonic()` call, removing the cross-clock
     comparison.
   - T10 now drives two full `claim_batch → _authoritative_user_content →
     _embedding → _upsert` cycles through real `OutboxRelay` instances
     (crash-before-finish, forcing lease-recovery redelivery — same
     mechanism as T08/T09), then a third worker completes the real
     `process_once` finish path.
   - T06/T07 now use deterministic test doubles
     (`ConnectionRefusedError` / a minimal `_UnavailableQdrantClient`)
     instead of real-socket fault injection.
   - No file under `test/h01/app/` (the frozen H0.1 implementation) was
     edited. SHA-256 of all three frozen artifacts confirmed unchanged.
3. **Re-ran the full isolated matrix** against a fresh Docker Postgres 17 +
   Qdrant stack (brought up and torn down cleanly, twice, via the existing
   `scripts/setup_test_env.sh` / `teardown_test_env.sh`): **19 passed, 2
   skipped, 0 failed**, identical pass/skip set to the 2026-09-06 baseline.
   No new BLOCKER/HIGH findings.
4. **Regenerated evidence**: `docs/evidence/h01/h01-failure-matrix-run.txt`
   and `docs/evidence/h01/h01-failure-matrix-junit.xml` from the fresh run;
   updated `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md` in place with a
   new "Test-hardening correction (2026-09-12)" section documenting the
   three findings/fixes and new file hashes.
5. **Flagged and cross-referenced a pre-existing staleness** found while in
   the report: its 2026-09-06 section still read as if H01-T01/H01-T18's
   production-read-only components were unresolved, but they were in fact
   separately authorized, performed, and passed on 2026-09-09
   (`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`,
   Foundation v1 closeout Workload 2). Added "Later resolution" pointer
   notes rather than rewriting the historical 2026-09-06 record, and
   propagated the same cross-reference into `CURRENT_STATE.md` and
   `CHANGE_LOG.md`.
6. Updated `docs/project-state/CURRENT_STATE.md` (H0.1 section),
   `docs/project-state/CHANGE_LOG.md` (H0.1 section), and
   `docs/project-state/MASTER_INDEX.md` (record-set table + reconciliation
   log) to reference this checkpoint.

## Files changed this session

- `test/h01/conftest.py`
- `test/h01/tests/test_h01_failure_matrix.py`
- `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md`
- `docs/evidence/h01/h01-failure-matrix-run.txt` (regenerated)
- `docs/evidence/h01/h01-failure-matrix-junit.xml` (regenerated)
- `docs/project-state/CURRENT_STATE.md`
- `docs/project-state/CHANGE_LOG.md`
- `docs/project-state/MASTER_INDEX.md`
- `docs/project-state/PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md` (this file)

No file under `test/h01/app/` (frozen H0.1 design) was touched. No
production system was accessed. No merge occurred.

## Verification

- SHA-256 of `test/h01/app/migrations/001_h01_karmo_outbox.sql`,
  `transactional_memory.py`, `outbox.py`: unchanged from every prior
  report (`d502699c...`, `33f464d8...`, `55af1192...` — see
  `H01_FAILURE_MATRIX_REPORT.md` for full digests).
- `test/h01/tests/test_h01_failure_matrix.py` new SHA-256:
  `2353c7cfd5f960a9a369b8166cc7afb0608675caa0c87f6e56a9ecc6f8fcb668`
- `test/h01/conftest.py` new SHA-256:
  `42f1c846ae710ff37e0223b36085ef37c87fa5a8c20e416bacc6cf71d4947fe1`
- Isolated stack: two Docker containers only
  (`karmo-h01-test-postgres`, `karmo-h01-test-qdrant`), brought up and torn
  down cleanly via existing scripts; no production container referenced.
- Test run: 21 collected, 19 passed, 2 skipped (H01-T01/H01-T18, by
  design), 0 failed.

## Risk

Low. Test-only change to an already-accepted, already-superseded-in-
production-status isolated acceptance suite. No production access, no
schema/data change, no change to the frozen H0.1 design or acceptance
criteria, no change to what is actually running in production.

## Rollback

`git revert` the commit(s) on `staging/karmo-full-predeploy-20260912`
that introduced this change; the prior test suite/report/evidence remain
available in git history. No production or infrastructure rollback is
implicated — nothing outside this repository's working tree changed.

## Current stopping point

H0.1 isolated failure-matrix suite hardened and re-verified; evidence and
durable project-state records updated; committed and pushed to
`staging/karmo-full-predeploy-20260912`. No PR opened, no merge, no
deploy, per explicit instruction.

## Next action

At Kamara's discretion: open a PR from this branch for independent review
if/when she wants this test-hardening merged toward `main`. No other
action is required or blocked by this checkpoint.

## Safety status at save

- Production: UNCHANGED by this session
- Frozen H0.1 design (`test/h01/app/`): UNCHANGED (SHA-256 verified)
- Merge: NOT PERFORMED
- Deploy: NOT PERFORMED
- Branch pushed: `staging/karmo-full-predeploy-20260912`
