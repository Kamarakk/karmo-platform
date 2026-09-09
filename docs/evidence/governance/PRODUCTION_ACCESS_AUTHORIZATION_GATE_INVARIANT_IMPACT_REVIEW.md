# Mandatory Production Access Authorization Gate — Invariant Impact Review

Performed before this governance change was made durable, per
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s own Mandatory Phase
Invariant Impact Review requirement — a governance change is itself a
change this document's compliance rule applies to.

## Background

The Foundation Closeout Program (2026-09-08) surfaced a real conflict:
`CLAUDE.md` item 4 and `AGENTS.md`'s "Authority and boundaries" section
both stated an unconditional, no-exception prohibition on any production
access from an AI session, while KARMO's actual working model already
relies on Natalie granting specific human approvals for specific
production-facing actions (e.g. the H0.1/H0.2/H0.4 production cutovers,
each operator-attested and explicitly authorized in the moment). Under the
literal, unconditional wording, no explicit authorization — however
specific — could lift the prohibition, which is not what either the
existing approval model or `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`
actually intended. Natalie explicitly approved resolving this conflict by
defining a narrow, explicit, task-specific authorization path while
keeping production access prohibited by default.

## Invariant Impact Review

```
Phase: Mandatory Production Access Authorization Gate (governance change)

I-01 Inheritance/compatibility: AFFECTED
I-02 Production parity: NOT AFFECTED
I-03 Data authority/transactions: NOT AFFECTED
I-04 Idempotency/retry: NOT AFFECTED
I-05 Resources/scale: NOT AFFECTED
I-06 Migration/rollback: NOT AFFECTED
I-07 Observability: AFFECTED
I-08 Validation scope: AFFECTED
I-09 Authority/permissions: AFFECTED
```

### I-01 — Inheritance / compatibility

Every prior production action recorded in `docs/project-state/` (H0.1,
H0.2, H0.4 cutovers; the legacy registry bootstrap dry-run and apply)
happened before this gate existed, under direct, in-the-moment operator
attestation rather than a written authorization record in this shape. This
gate does not retroactively invalidate, re-open, or require re-justifying
any of that already-accepted history — it governs future production
access only. No backfill of a retroactive authorization record for past
actions is required or performed by this change.

### I-07 — Observability

This is a net observability improvement: the "Authorization record" shape
this gate defines gives every future production access a durable,
consistent, greppable record (target system, purpose, permitted
operations, read/write authority, commands, grant/expiry) in
`docs/project-state/CURRENT_STATE.md` and the task's own PR/evidence —
strictly more than the prior unconditional-prohibition wording produced,
since that wording had no defined path for recording an authorized
exception at all.

### I-08 — Validation scope

Documentation-only governance change; no code, schema, or test-affecting
behavior changed. Per `docs/governance/KARMO_VALIDATION_LADDER.md`, this
needs rung 1 at most (this review) plus the standard PROJECT SAVE
consistency checks (`git diff --check`, contradiction/duplicate-governance/
secret scan) — not the isolated Docker suites, which this change does not
touch.

### I-09 — Authority / permissions

This is the core subject of the change. It does not create a new class of
autonomous authority — it narrows an ambiguous, internally-conflicting
absolute prohibition into an explicit, bounded exception path that already
matches I-09's existing capability classification (READ / DRAFT-PROPOSE /
REVERSIBLE WRITE / EXTERNAL ACTION / DESTRUCTIVE-HIGH-IMPACT) and
least-privilege principle. Read-only and write authority are kept
strictly separate by construction (item 4 of the gate); every
higher-impact action category the requesting instruction named (writes,
deployment, destructive actions, migrations, restarts, configuration
changes, data repair, deletion, irreversible actions) is enumerated as
requiring its own separate grant, not implied by a read-only one. The
gate explicitly states it narrows, never widens, authority, and that it
does not override any other invariant, the Invariant Impact Review
requirement, the validation ladder, rollback requirements, or the standing
gates in `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`. A
general workload approval or autonomous-execution-contract approval is
explicitly stated as never substituting for this gate, closing the
specific loophole a careless reading of the Foundation Closeout Program's
"pre-authorization" language could otherwise have created.

## Known inherited assumptions

`CLAUDE.md`'s preamble ("these instructions OVERRIDE any default behavior")
and `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s own precedence
statement ("if AGENTS.md/CLAUDE.md and this document ever appear to
disagree, this document governs") together already establish that the
invariants document is the correct home for the canonical rule, with
`CLAUDE.md`/`AGENTS.md` referencing rather than restating it — the same
pattern already used for the Mandatory Phase Invariant Impact Review and
the Mandatory Project Save Completion Rule. This change follows that
existing pattern rather than introducing a new one.

## Authorization boundaries

This governance change itself required, and received, Natalie's explicit
approval (the request that prompted it). It does not grant any production
access by itself — no Production Access Authorization was issued or acted
on as part of making this change; production was not accessed during this
task, per explicit instruction.

## Validation plan

Rung 1 only: this review, plus `git diff --check`, a documentation
consistency scan (contradictions, duplicate governance, secrets,
accidental resolution of historical unknowns), and confirmation that
`CLAUDE.md`, `AGENTS.md`, and
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` all now point to
the same single canonical rule rather than restating it differently.

## Rollback implications

Trivial — a documentation-only change on a dedicated branch, not merged by
this task. `git revert` if ever needed; nothing production-facing, nothing
destructive.
