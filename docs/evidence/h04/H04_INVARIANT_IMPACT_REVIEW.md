# H0.4 Production Integration — Invariant Impact Review

Applies `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01 through
I-09) to PR #6 (`feat/h04-production-integration`):
`h04/app/document_ingest_h04.py`, `h04/app/bootstrap_legacy_registry.py`,
`h04/app/run_auditor.py`, `h04/app/reconciliation.py` (modified). This is
a retrospective application to already-authored work, not a pre-
implementation gate -- future phases apply the review before substantial
implementation, per the governance document.

Scope discipline: this review fixes only genuine deployment blockers or
directly related defects. It does not redesign accepted H0.1-H0.4
architecture and does not rerun the frozen H0.4 acceptance suite (no
foundational/shared behavior, dependency/runtime, or security/integrity
rule changed since that suite last passed 10/10 -- see I-08 below for the
specific justification each time a targeted check was run instead).

```
Phase: H0.4 Production Integration (PR #6)

I-01 Inheritance/compatibility: AFFECTED
I-02 Production parity: AFFECTED
I-03 Data authority/transactions: AFFECTED
I-04 Idempotency/retry: AFFECTED
I-05 Resources/scale: AFFECTED
I-06 Migration/rollback: AFFECTED
I-07 Observability: AFFECTED
I-08 Validation scope: AFFECTED
I-09 Authority/permissions: AFFECTED
```

## I-01 / I-05 — Inheritance, pagination, scale

**Finding (fixed):** `document_ingest_h04.py`'s `active_points_for_document`
inherited H0.2's single bounded `client.scroll(limit=10000)` call with the
offset discarded. A logical document with more than 10000 active chunks
would have had only the first 10000 superseded, silently leaving the rest
`is_active=True` in Qdrant after a new version was ingested. Fixed with a
local `_scroll_all` that follows `next_page_offset` to exhaustion,
mirroring `reconciliation.py`'s already-fixed pagination shape (kept
local rather than imported, so the ingest pipeline has no dependency on
the audit module). Verified with a fake multi-page `scroll()` double
proving all pages are read (see Validation below); `document_exists`
(`limit=1`) confirmed correctly unchanged, since it is an existence check,
not an all-records read.

**Reviewed, no other gap found**, across every H0.4 production-path file:
- `reconciliation.py`'s `_scroll_all`/`actual_chunk_points`/`all_points`:
  already paginate to exhaustion (fixed and accepted before H0.4's 10/10
  acceptance run).
- `registry_db.py`'s `list_registry`/`list_by_document_id`: plain
  `SELECT` with no `LIMIT` at all -- already full-scan, not a truncating
  ceiling.
- `bootstrap_legacy_registry.py`: reads points exclusively via
  `reconciliation.all_points` (paginated); no separate scroll call of its
  own.
- `run_auditor.py`: no direct Qdrant/Postgres calls beyond
  `auditor.run_audit`/`registry_db.list_registry`, both already covered
  above.

**Inherited, not a phase-introduced gap, intentionally not touched:**
`process_inbox`'s `[p for p in INBOX.iterdir() if p.is_file()]` loads the
whole inbox directory listing at once -- byte-identical to
`docs/handoff/h04/document_ingest.py`'s untouched H0.2 behavior. Not a gap
this PR introduced; changing it would be redesigning accepted H0.2
architecture, out of this review's scope.

## I-02 — Production parity

Connection defaults (`127.0.0.1:5433`, db/user `karmo`,
`KARMO_DB_PASSWORD`) already match the documented production shape
(`registry_db.py`'s own docstring, citing `docs/handoff/h04/memory.py`).
No code defect found. Operational requirement for deployment (not a code
change): `KARMO_DB_PASSWORD` must be supplied through a persistent
mechanism appropriate to however this job is actually run in production
(e.g. a systemd `EnvironmentFile`, secrets manager, or equivalent) --
never a variable manually `export`ed in an interactive shell, per I-02.
This is a deployment-configuration requirement to satisfy at deploy time,
not a defect in this PR.

## I-03 — Data authority & transaction boundaries

Already addressed in the prior fail-closed correction on this PR:
PostgreSQL `document_registry` is the declared authoritative registry;
Qdrant is authoritative for vectors; write ordering is fixed
(convert/chunk/embed → Qdrant upsert → archive move → registry write);
the registry write (new-version insert + prior-version deactivation) is
one transaction, committed or rolled back together
(`_commit_registry_lifecycle`); a registry failure is reported as
`INTEGRITY INCOMPLETE / REGISTRY FAILED` and fails the job's exit code --
never silently reported as success. No new gap found this review.

## I-04 — Idempotency & retry safety

Reviewed, no code defect found; one **documented follow-up, not a
blocker**:

- Re-ingesting identical content is safe: `document_exists` skips it
  (`SKIPPED DUPLICATE`), so a retry never creates duplicate Qdrant
  knowledge.
- `bootstrap_legacy_registry.py` is idempotent: `get_by_hash` skips any
  document_hash already registered, so rerunning it (with or without
  `--apply`) never double-inserts or errors.
- `run_auditor.py` is read-only; trivially retry-safe.
- **Follow-up (not a blocker):** if a document's registry write fails
  (`INTEGRITY INCOMPLETE`), the file has already left the inbox, so
  simply rerunning `process_inbox` cannot retry just that registry write
  -- `document_exists` will skip it as a duplicate before reaching the
  registry step. The gap is not silent: `run_auditor.py` already detects
  it as `ORPHAN_VECTOR` (a Qdrant `document_hash` with no registry row).
  There is intentionally no automatic-repair tool for this yet, matching
  this PR's explicit "no automatic repair" design and I-09 (an automatic
  write-repair tool is a higher-impact capability requiring its own,
  separately authorized design) -- recovery today is a manual, audited
  action. Building that tool is future work, not in this PR's scope.

## I-06 — Migration & rollback compatibility

OLD (pre-H0.2, no `is_active` field) / MIXED (some documents
bootstrapped, some not; some H0.4-ingested documents registered, some
mid-gap per I-04 above) / NEW (fully H0.4-registered) states were already
designed for: `bootstrap_legacy_registry.py` only ever targets genuinely
legacy points and refuses (never guesses) on any internal
inconsistency (`INCONSISTENT_SOURCE_FILE`,
`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`,
`UNVERIFIABLE_CHUNK_COUNT`, `INCONSISTENT_PROVENANCE`, etc.); an
H0.4-lifecycle Qdrant point without a registry row is a normal,
detected `ORPHAN_VECTOR`, not a crash or corruption. No one-way
compatibility boundary is introduced. No defect found.

## I-07 — Observability before automation

Already satisfied in substance: `INTEGRITY INCOMPLETE / REGISTRY FAILED`
carries document identity, version, hash, and reason;
`LEGACY_PROVENANCE_UNVERIFIED` distinguishes known-legacy state from a
real `PROVENANCE_MISMATCH`; `run_auditor.py`'s `STATUS` field
(`CLEAN` / `CLEAN_WITH_KNOWN_LEGACY_GAPS` / `INTEGRITY_FINDINGS_PRESENT`)
and separate `LEGACY_PROVENANCE_UNVERIFIED_COUNT` /
`INTEGRITY_FINDING_COUNT` map cleanly onto I-07's suggested categories
(`DEPENDENCY_UNAVAILABLE`, `INTEGRITY_FAILURE`, `LEGACY_DATA_GAP`) even
though the exact label strings differ. No behavior-affecting gap found;
no code change made here to avoid reopening already-validated exit-code
logic for a labeling-only difference.

## I-08 — Validation scope for this review

No production-path behavior changed in this review beyond what was
already targeted-validated on this PR (the pagination fix, validated with
a fake multi-page `scroll()` double and an in-memory-Qdrant supersession
regression check, both already run and reported). This review itself adds
only documentation (`docs/governance/`, `docs/evidence/h04/`, `AGENTS.md`,
`CLAUDE.md` references) -- no executable code changed, so no additional
validation is needed for the review itself. Full H0.4 acceptance suite:
not rerun -- no foundational/shared behavior, dependency/runtime, or
security/integrity-sensitive rule changed since its last accepted 10/10
run; this satisfies I-08's "state why" requirement for not rerunning it.

## I-09 — Authority & permission boundaries

Reviewed, no defect found: `bootstrap_legacy_registry.py` defaults to
report-only and requires an explicit `--apply` flag to write (matches
I-09's DRAFT/PROPOSE-before-REVERSIBLE-WRITE classification);
`run_auditor.py` and `auditor.run_audit` are read-only by construction
(frozen, `test_auditor_is_report_only`); `document_ingest_h04.py`'s
Qdrant/archive/registry writes are the same class of action H0.2 was
already authorized to perform, not a new capability. No automatic
repair/write-back capability was added anywhere in this PR.

## Summary

One genuine defect found and fixed this cycle (I-01/I-05, the
`limit=10000` pagination ceiling -- already committed to PR #6 prior to
this review). No other I-01 through I-09 violation found in the current
H0.4 production-path code. One follow-up documented (I-04: a dedicated
registry-gap repair tool), explicitly deferred as future, separately
authorized work, not a blocker to this PR.
