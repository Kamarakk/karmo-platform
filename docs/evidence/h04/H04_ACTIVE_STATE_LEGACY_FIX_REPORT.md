# H0.4 `check_active_version_state` Legacy-Definition Fix — Evidence

- Date: 2026-09-09
- Branch: `review/foundation-verification-and-h04-fix`
- Scope: Workstream 2 of the Post-Foundation Overnight Readiness Program —
  the recorded H0.4 auditor gap from `docs/project-state/NEXT_STEPS.md`
  item 7.
- Invariant Impact Review:
  `docs/evidence/h04/H04_ACTIVE_STATE_LEGACY_FIX_INVARIANT_IMPACT_REVIEW.md`
  (performed before implementation).

## Root cause (determined from evidence, not assumed)

`docs/handoff/h04/document_memory.py`'s `search_documents` — the real,
already-shipped production retrieval code — defines "active" as
`is_active=True` **or** the field being absent entirely; only an explicit
`is_active=False` excludes a point. `reconciliation.check_active_version_state`
used a narrower definition (`is_active is True` only), which disagreed
with the application's own definition. This is why the three documents
`bootstrap_legacy_registry.py` already registered (legacy Qdrant points,
no `is_active` field at all) were permanently reported as
`ACTIVE_STATE_MISMATCH` — not because anything was wrong, but because the
auditor's comparison used a different notion of "active" than the app.

## Fix

`h04/app/reconciliation.py`, `check_active_version_state`: changed the
Qdrant-active membership test from `point.payload.get("is_active") is True`
to `point.payload.get("is_active") is not False` — i.e. a point counts as
active unless it is explicitly marked inactive, matching
`document_memory.search_documents` exactly. One function, 28 lines changed
(mostly an expanded docstring explaining the correction and its
precedent). `auditor.py` untouched (confirmed empty `git diff`).

## Why this doesn't weaken detection

The fix is not merely "more lenient" — it changes what counts as
Qdrant-active in both directions, matching production:

- **Removes** a spurious mismatch for a legacy-bootstrapped, genuinely
  consistent document (registry active, Qdrant points missing the field —
  production retrieval already treats this as active).
- **Adds** detection of a real gap the old code silently missed: a
  document the registry marks inactive/superseded, whose Qdrant points
  still lack an explicit `is_active=False` — production retrieval would
  still surface those points, which the *old*, narrower definition never
  flagged as a mismatch (both `registry_active_hashes` and
  `qdrant_active_hashes` would have excluded that hash, appearing
  consistent when the real serving behavior was not).

## Tests

New file `h04/tests/test_h04_active_state_legacy_fix.py`:

1. `test_legacy_bootstrapped_document_no_longer_falsely_flagged` — a
   document shaped exactly like the three already-bootstrapped legacy
   documents produces **zero** `ACTIVE_STATE_MISMATCH` findings.
2. `test_registry_inactive_qdrant_missing_field_now_detected` — a document
   the registry marks inactive, whose Qdrant points still lack an
   explicit `is_active=False`, **is** now flagged — proving the fix adds
   real detection rather than only removing findings.

Result: **2/2 PASS**. Raw output: `h04-active-state-fix-run.txt`. JUnit:
`h04-active-state-fix-junit.xml`.

## Targeted regression re-run (I-08: state why)

Re-ran, unmodified: `test_h04_integrity_reconciliation.py` (10 tests),
`test_h04_pagination.py` (1 test), `test_h04_registry_repair.py` (4
tests) — because `reconciliation.py` is foundational/shared behavior every
H0.4 finding type and the registry-repair tool both depend on. Result:
**15/15 PASS**, unchanged, including
`test_multiple_active_versions_detected` and
`test_healthy_consistent_document_has_no_findings` (the two existing
tests closest to this change). Raw output:
`h04-active-state-fix-regression-rerun.txt`.

## Scope discipline

- No production accessed, no Qdrant data modified, no legacy vector
  rewritten (isolated Docker stack only, same as every prior H0.4 change).
- The two ambiguous `karmo-v05-new.html` hashes are untouched — they
  remain `ORPHAN_VECTOR` findings from a different, unmodified check
  (`find_orphan_vectors`).
- `auditor.py`'s report-only guarantee unmodified and unaffected.
- No schema change. No new finding type. No change to any other H0.4
  module.
- Not merged — prepared as a PR for Kamara's review, per explicit
  instruction.
