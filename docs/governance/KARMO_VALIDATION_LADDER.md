# KARMO Validation Ladder

A reusable validation sequence for every future KARMO workload. This
document operationalizes I-08 (Validation Ladder / No Redundant Testing) in
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` — it does not restate or
alter I-08's rule ("use the smallest validation scope justified by the
change... state WHY when repeating a previously accepted test"), it gives
that rule ten concrete rungs so a workload plan can just say "ladder steps
1–5" instead of re-deriving scope each time.

Referenced by `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` and intended
for every workload under `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.

## The ten rungs

1. **Static/syntax validation** — linting, type checking, `py_compile` or
   equivalent. Cheap; run on every change.
2. **Targeted unit tests** — tests for exactly the changed behavior. The
   default floor for any code change.
3. **Compatibility/regression tests** — targeted tests proving inherited
   behavior (I-01) and previously-accepted contracts still hold, scoped to
   what the change could plausibly affect.
4. **Isolated integration tests** — the isolated Docker/in-memory
   PostgreSQL+Qdrant pattern already used by H0.1/H0.2/H0.4, when a change
   crosses a real integration boundary (a new store, a new external call).
5. **Invariant review** — the Mandatory Phase Invariant Impact Review
   (I-01–I-09) from the invariants document, before substantial
   implementation for a new phase/feature/service, or retrospectively for a
   scoped fix within an already-approved workload.
6. **Evidence generation** — a written report + raw run output + (where
   applicable) JUnit XML under `docs/evidence/<phase>/`, following the shape
   already established by H0.1–H0.4's evidence reports.
7. **Pre-production review** — an independent read of the evidence and diff
   (Codex or equivalent, per README.md's "Codex is the independent design,
   security, and evidence reviewer" operating rule) before anything is
   proposed for production.
8. **Explicit production approval** — Kamara's explicit go-ahead, per
   `AGENTS.md`; never implied by an earlier, narrower approval.
9. **Production verification** — a minimal, read-only functional check after
   deployment (e.g. H0.1's "one delivered outbox event" test), not a full
   re-run of the isolated suite against production.
10. **Rollback verification where applicable** — for anything with a
    rollback/backup step (a migration, a production file swap), confirm the
    rollback artifact exists and, where practical, that a restore drill has
    been exercised in isolation (as H0.4's `recovery.py` backup/restore
    drill did) before relying on it in production.

## How to scope a workload against the ladder

Not every workload climbs every rung, and not every rung is expensive:

- A documentation-only change (like this document) needs rung 1 at most
  (e.g. a markdown lint) — rungs 2–10 do not apply.
- A scoped bug fix inside an already-accepted isolated suite needs rungs
  1–3, occasionally 4; it does not require re-running the full accepted
  suite (I-08) unless the fix touches foundational/shared behavior,
  dependency/runtime, or a security/integrity-sensitive rule — and if it
  does, state why, per I-08.
- A new phase/feature/service/integration needs the full ladder, rungs 1–10,
  because it is exactly what I-08's "release/phase acceptance" and "a new
  integration boundary changed" triggers describe.
- Production-facing steps (rungs 8–10) always require Kamara's explicit
  approval per workload, regardless of how narrow rungs 1–7 were — this
  ladder never implies production authorization by itself.

## What this document does not do

It does not replace the Mandatory Phase Invariant Impact Review template in
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (rung 5 points to it, not
around it), and it does not create a new approval gate — approval gates are
defined in `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`. This
document is a shared checklist for *how much testing is enough*, not *who
approves what*.
