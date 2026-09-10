# Core v2 Prototypes — Adversarial Review Findings and Fixes

Produced under the KARMO Large Autonomous Review program (PRs #14–#21
review pass), Workstream 4. An independent, critical re-inspection of the
Core v2 prototypes (PR #19) found 4 real, credible defects — not
manufactured, each demonstrated with a failing/proving script or test
before being fixed. **154 → 160 tests** (net +6: 4 new regression tests, 1
existing test rewritten because the fix inverts its old assumption, 1
additional new test for a legitimate use case the fix must still permit).

## Finding 1 — Autonomous-run verifier never checked `evidence`/`test_results` at all

**Severity: HIGH.** The design doc
(`docs/architecture/KARMO_AUTONOMOUS_RUN_VERIFICATION_SYSTEM.md`)
explicitly promised checklist item 4: "does a raw run-output file
actually exist... and do its pass/fail counts match test_results?" The
shipped `validator.py` never implemented this check at all.
**Demonstrated**: a record claiming `"passed": 9999` backed by a
completely nonexistent evidence file passed every single check in
`run_all()` — the exact "cannot treat missing evidence as PASS" failure
mode this workstream was asked to test for.

**Fix**: added `check_evidence_and_test_results` — every claimed evidence
path must exist at `end_sha`; every claimed test suite must have a
corresponding, non-empty `test_results` entry. Wired into `run_all()`.
New tests: `test_catches_fabricated_test_results_backed_by_nonexistent_evidence`,
`test_catches_a_claimed_test_suite_with_no_corresponding_results_entry`.

## Finding 2 — Trust Score's placeholder components hid obviously-false evidence

**Severity: MEDIUM–HIGH.** `evidence_completeness` and `test_reliability`
were hardcoded to `1.0` regardless of input; `scope_compliance` re-derived
from the same `check_results` `independent_verification_agreement`
already used, rather than measuring something independent.
**Demonstrated**: with Finding 1 still open, a maximally-fabricated
record (every check failing) scored **~0.58** — nowhere near low enough
to read as "obviously false," failing the explicit adversarial
requirement "cannot produce a high trust score from obviously false
evidence."

**Fix**: `evidence_completeness` now derived from Finding 1's new check;
`test_reliability` now derived from the record's own claimed failure
counts (fails closed if any claimed suite reports a failure);
`scope_compliance` now derived from the record's own
production_writes/restarts/external_actions/governance_changes fields,
independent of the other components. A fully-fabricated record (including
a false production-access claim) now scores **0.167**, not 0.58. An
honest, fully-corroborated record scores **>0.9**. New tests:
`test_trust_score_stays_low_for_obviously_fabricated_evidence_even_with_record`,
`test_trust_score_stays_high_for_a_genuinely_honest_record`.

## Finding 3 — Approval Engine had no executor-identity binding at all

**Severity: MEDIUM.** `execute()` checked tool/version/arguments but
never checked *who* was presenting the approval. **Demonstrated**: the
existing prototype's own test,
`test_changed_requester_identity_does_not_let_a_second_party_reuse_the_approval`,
was *proving the opposite of its name* — its old body confirmed a
different, unrelated actor **could** successfully execute someone else's
approval, and its own docstring called this "a deliberate design choice."
That directly contradicts the adversarial checklist's explicit "changed
requester fails" requirement and is a real confused-deputy /
stolen-credential risk named in
`docs/architecture/KARMO_CORE_V2_SECURITY_THREAT_MODEL.md`.

**Fix**: added `authorized_executor` to `ApprovalRecord`, set at
`approve()` time (defaults to the original requester; can be explicitly
delegated, e.g. to a dispatcher service). `execute()` now requires an
`executor_identity` argument and refuses — invalidating the approval, the
same treatment as a tool/argument mismatch — on any mismatch. This
required renaming the callable parameter from `executor` to `action`
(the old name was already overloaded between "the identity" and "the
callable" once identity checking was added) — a clean rename since this
is an isolated, unreleased prototype with no external caller. The
existing test was rewritten to assert the corrected (secure) behavior;
a new test (`test_authorized_executor_can_differ_from_requester_when_explicitly_granted`)
confirms the legitimate delegation case still works.

## Finding 4 — Tool Registry silently accepted unknown manifest fields

**Severity: LOW–MEDIUM.** `register()` checked for missing required
fields and one specific forbidden field, but never rejected *unrecognized*
fields. **Demonstrated**: a manifest with a made-up field
(`required_approval_override`) registered successfully with the bogus
field silently stored — a "refuse rather than guess" discipline gap
relative to every other KARMO validator's own pattern.

**Fix**: `register()` now refuses any manifest key outside
`REQUIRED_MANIFEST_FIELDS` — the schema is closed, not merely additive.
New test: `test_refuses_unknown_fields_not_part_of_the_schema`.

## What was checked and found already correct (no fix needed)

- Tool Registry: authority-cannot-be-lowered (the full combinatorial
  matrix, re-verified), malformed registration refusal (per-field,
  re-verified).
- Job/Event model: duplicate-submission idempotency, claim-token
  crash/reclaim fencing, stale-worker fencing — all re-inspected against
  the H0.1 outbox relay's own proven pattern; no gap found.
- Approval Engine: single-use/double-execution enforcement, arguments
  digest binding, expiry — all held up under adversarial re-reading;
  only the executor-identity gap (Finding 3) was real.

## Result

**160/160 tests pass** (`core-v2-prototypes-run.txt`,
`core-v2-prototypes-junit.xml`, this directory). `MANIFEST.sha256`
generated for this evidence directory — previously absent, itself a
minor finding this review corrected (Foundation v1's evidence package had
one; this one didn't).
