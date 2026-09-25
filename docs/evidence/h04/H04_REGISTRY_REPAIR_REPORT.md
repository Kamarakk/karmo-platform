# H0.4 Registry Repair Tool — isolated acceptance evidence

- Date: 2026-09-08
- Branch: `feat/h04-registry-repair`
- Scope: isolated, local, Docker-based PostgreSQL + Qdrant test environment
  only (`h04/docker-compose.yml`, container name prefix `karmo-h04-test-`,
  non-default ports 57432/58333/58334). No production host, credential,
  database, Qdrant collection, or document was accessed.
- Frozen scope: Workload 3 of `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`
  — the I-04 follow-up `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`
  already documented as deferred, future, separately-authorized work: a
  dedicated tool that constructs the missing `document_registry` row for an
  `ORPHAN_VECTOR` finding strictly from the Qdrant payload's own recorded
  metadata, report-only by default.
- Invariant Impact Review: `docs/evidence/h04/H04_REGISTRY_REPAIR_INVARIANT_IMPACT_REVIEW.md`
  (performed before implementation, per the Mandatory Phase Invariant Impact
  Review).

## Architecture implemented

- **`h04/app/registry_repair.py`**: given the set of currently-registered
  `document_hash` values, finds orphaned document_hash groups via the
  existing, unmodified `reconciliation.find_orphan_vectors` /
  `reconciliation.actual_chunk_points`, verifies each group's `document_id`,
  `document_version`, chunk-number completeness, `archive_path` (and its
  agreement with any `source_path`), archived-file existence and SHA-256,
  `pipeline_version`/`embedding_model`/`chunker_version`, and `is_active`/
  `deactivated_at`/`superseded_by` consistency — refusing (never guessing)
  on any disagreement or missing value — and only then adds the group to a
  `ready` plan. `--apply` is required for any write; the default is
  report-only. Re-checks `registry_db.get_by_hash` immediately before
  planning each write, so a group already registered (including by a
  concurrent/retried run) is reported `ALREADY_REGISTERED` and skipped, not
  re-inserted.
- Distinct from `bootstrap_legacy_registry.py`: that tool targets legacy
  (pre-H0.2) points lacking `is_active`/`document_version` entirely, and
  defaults every registered group to version 1. This tool targets normal
  H0.4-lifecycle orphan points, which already carry full lifecycle and
  provenance fields on every point payload — so it never assumes a version
  number and never falls back to a legacy-provenance label; a genuinely
  legacy point that reaches it is refused (`INCONSISTENT_IS_ACTIVE`), not
  mis-registered.
- `auditor.py` is unmodified — confirmed by `git diff` (empty), not only by
  test.

## Refusal reasons (finding types)

| Reason | Detected by |
|---|---|
| `MISSING_DOCUMENT_HASH` | orphan point with no `document_hash` at all |
| `INCONSISTENT_DOCUMENT_ID` | group disagrees on `document_id` |
| `INCONSISTENT_DOCUMENT_VERSION` | group disagrees on `document_version` |
| `UNVERIFIABLE_CHUNK_COUNT` | `chunk_number` set is not exactly `{1..N}` |
| `MISSING_ARCHIVE_PATH` / `INCONSISTENT_ARCHIVE_PATH` | `archive_path` absent or disagreeing across the group |
| `INCONSISTENT_SOURCE_PATH` | a point's `source_path` disagrees with the group's `archive_path` |
| `MISSING_ARCHIVE_FILE` | no file at the recorded `archive_path` |
| `ARCHIVED_FILE_HASH_MISMATCH` | recomputed SHA-256 does not equal `document_hash` |
| `MISSING_PROVENANCE_FIELD` / `INCONSISTENT_PROVENANCE` | a provenance field absent or disagreeing across the group |
| `INCONSISTENT_IS_ACTIVE` | group disagrees on `is_active` (or lacks it — legacy points) |
| `MISSING_DEACTIVATED_AT` | `is_active=False` but `deactivated_at` absent/disagreeing |
| `INCONSISTENT_SUPERSEDED_BY` | group disagrees on `superseded_by` |
| `ALREADY_REGISTERED` | `document_hash` already has a registry row (idempotency guard) |

## Test stack

Identical isolated stack to the existing H0.4 suite: `postgres:17-alpine` +
`qdrant/qdrant:v1.9.7`, ports `127.0.0.1:57432` / `127.0.0.1:58333`,
containers `karmo-h04-test-postgres` / `karmo-h04-test-qdrant`, synthetic
credentials, collection `karmo_h04_test_documents`.

## New suite: `h04/tests/test_h04_registry_repair.py`

One test per scenario named in the approved workload scope:

1. `test_healthy_orphan_repaired_and_no_longer_reported` — a fully
   consistent H0.4-lifecycle orphan (real archived content, matching hash,
   agreeing provenance) is planned with no refusals, registered via
   `apply_plan`, and the auditor no longer reports `ORPHAN_VECTOR` for it
   afterward.
2. `test_ambiguous_group_is_refused_not_guessed` — one point's
   `pipeline_version` disagrees with the rest of its group; the group is
   refused (`INCONSISTENT_PROVENANCE`), nothing is written.
3. `test_already_registered_group_is_a_noop_on_rerun` — after a successful
   apply, re-running `build_plan` with the same (now-stale) `known_hashes`
   set — simulating a retried/concurrent invocation racing the first apply
   — reports `ALREADY_REGISTERED` and skips; re-applying is a true no-op
   (no duplicate row, no error).
4. `test_build_plan_is_report_only_by_default` — every mutating Qdrant API
   and every non-`SELECT` PostgreSQL statement is made to raise if called;
   `build_plan` still runs to completion and still reports the repairable
   group as `ready`, proving report-only-by-default the same way
   `test_auditor_is_report_only` proves `auditor.py`'s guarantee.

Result: **4/4 PASS**. Raw output: `h04-registry-repair-run.txt`. JUnit:
`h04-registry-repair-junit.xml`.

## Targeted regression re-run (I-08: state why)

Re-ran the existing, frozen `test_h04_integrity_reconciliation.py` (10
tests) and `test_h04_pagination.py` (1 test) unmodified, because this
workload shares `reconciliation.py`'s finding types and reads the same
registry/collection shape — a targeted re-run confirms nothing in the
already-accepted H0.4 suite regressed, without reopening or duplicating
that suite's own evidence. Result: **11/11 PASS**, unchanged from the
original H0.4 acceptance run. Raw output:
`h04-registry-repair-regression-rerun.txt`.

## Acceptance criteria (from the approved workload)

- New suite passes: **4/4 PASS**.
- `auditor.py` unchanged: confirmed by `git diff` (empty).
- Existing H0.4 10/10 suite (plus the pagination test) re-run once,
  targeted: **11/11 PASS**.

## Scope discipline

No automatic/scheduled/background repair was added — this remains a
human-run CLI, report-only by default, `--apply` required for any write,
matching `bootstrap_legacy_registry.py`'s own gating and
`CLAUDE.md`'s prohibition on new autonomous schedules without Kamara's
written approval. No change was made to `document_registry`'s schema, to
`auditor.py`, or to `reconciliation.py`. No production execution of this
tool was performed or is authorized by this evidence — a future, separate
approval, exactly as `bootstrap_legacy_registry.py`'s own production
dry-run and `--apply` runs each required.
