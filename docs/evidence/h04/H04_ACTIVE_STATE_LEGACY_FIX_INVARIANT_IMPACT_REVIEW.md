# H0.4 `check_active_version_state` Legacy-Definition Fix — Invariant Impact Review

Performed before implementation, per the Mandatory Phase Invariant Impact
Review. Scope: `h04/app/reconciliation.py`'s `check_active_version_state`
— the smallest safe correction for the auditor-design gap recorded in
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md` and
`docs/project-state/NEXT_STEPS.md` item 7.

## What the evidence actually showed (determining correct behavior first)

`docs/handoff/h04/document_memory.py`'s `search_documents` — the real,
already-production, already-accepted definition of retrieval — states
explicitly: "the filter treats `is_active=True` and a missing `is_active`
field as active, and excludes only `is_active=False`." This is not a
proposal; it is the authoritative, already-shipped semantics of "active"
in KARMO. `reconciliation.check_active_version_state`'s `qdrant_active_hashes`
computation used a narrower, different definition (`is_active is True`
only), which disagrees with the application's own definition. This is a
genuine correctness bug in the auditor, not merely an unhelpful legacy
false-positive: the auditor's notion of "Qdrant-active" simply did not
match what the application itself treats as active.

## Invariant Impact Review

```
Phase: H0.4 check_active_version_state legacy-definition correction

I-01 Inheritance/compatibility: AFFECTED
I-02 Production parity: NOT AFFECTED
I-03 Data authority/transactions: NOT AFFECTED
I-04 Idempotency/retry: NOT AFFECTED
I-05 Resources/scale: NOT AFFECTED
I-06 Migration/rollback: NOT AFFECTED
I-07 Observability: AFFECTED
I-08 Validation scope: AFFECTED
I-09 Authority/permissions: NOT AFFECTED
```

### I-01 — Inheritance / compatibility

This is exactly an I-01 case: "previous schema assumptions" and "identity/
provenance compatibility" for legacy (pre-H0.2) data. The fix makes the
auditor's assumption about legacy data match the assumption
`document_memory.py` already makes and has always made — it does not
introduce a new assumption, it removes a disagreement between two parts of
the codebase that should have agreed from H0.4's original design. No
production data, schema, or Qdrant payload is touched (`auditor.py` and
`reconciliation.py` remain read-only, .scroll()-only, by construction,
unmodified by this change beyond the one function's comparison logic).

### I-07 — Observability

The fix does not add or remove a finding *type* — `ACTIVE_STATE_MISMATCH`
still exists, still fires, with the same fields. What changes is *which*
document states trigger it: three already-known, already-explained
legacy-bootstrapped documents stop triggering a spurious, permanent
false-positive, and one previously-silent, genuinely-inconsistent state
(registry inactive, Qdrant points still lacking an explicit
`is_active=False`) starts triggering it correctly. Net effect: the
finding's signal-to-noise ratio improves; nothing about a real problem
becomes harder to see.

### I-08 — Validation scope

A scoped, isolated, one-function correction inside an already-accepted
H0.4 module. Per the Validation Ladder: rungs 1–4 (static check, targeted
unit tests for the new/changed behavior, a targeted regression re-run of
the existing frozen H0.4 suite because this touches
`reconciliation.py` — foundational/shared behavior every H0.4 finding
type depends on — I-08's own "state why" trigger), rung 5 (this review),
rung 6 (evidence). Not rungs 8–10 (no production step is proposed or
performed by this workstream).

## Explicit requirement compliance (from the authorizing instruction)

- **Does not weaken detection for real lifecycle inconsistencies:**
  verified by construction and by a new regression test
  (`test_registry_inactive_qdrant_missing_field_now_detected`) proving the
  fix *adds* detection of a real gap the old code silently missed — see
  "Test plan" below.
- **Distinguishes known pre-H0.2 legacy state from corruption:** a
  legacy-bootstrapped document (registry active, Qdrant points genuinely
  missing `is_active`) now correctly produces **zero findings** — not an
  informational "known-legacy" finding like `LEGACY_PROVENANCE_UNVERIFIED`,
  because after the fix there is no actual disagreement left to report
  (the registry and Qdrant sets are literally equal) — this differs from
  the provenance case, where a real value-level difference (a string vs.
  `None`) still exists even in the "expected" case. A genuinely corrupted
  or ambiguous state (e.g. registry inactive but Qdrant still surfaces the
  content) is still, and now more reliably, flagged.
- **No production modified; no Qdrant data modified; no legacy vector
  rewritten:** this change touches one Python comparison function only.
  `auditor.py`'s report-only guarantee is unmodified and unaffected (not
  in this diff at all). No production access was performed or required —
  the fix was designed entirely from already-committed evidence
  (`document_handoff/h04/document_memory.py`) and validated entirely
  against the isolated Docker stack.
- **The two ambiguous `karmo-v05-new.html` hashes are untouched:** they
  remain `ORPHAN_VECTOR` findings (a different check,
  `reconciliation.find_orphan_vectors`, not touched by this fix) and are
  not registered, guessed, or resolved by this change.
- **Targeted regression tests added; existing regression tests run.** See
  "Test plan."

## Rollback implications

Trivial — a single-function, isolated-tested change on a feature branch,
not merged. `git revert` if ever needed. No schema, no production, no
irreversible action.
