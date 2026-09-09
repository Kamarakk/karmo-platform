# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. As of the 2026-09-08
foundation-acceleration pass, the primary next action is **Natalie choosing
which workload(s) in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` to
approve next** — the items below map onto that plan's 5 workloads plus one
standing constraint that isn't a workload at all.

## 1. Keep the two ambiguous legacy hashes unresolved (no action required, active constraint)

`karmo-v05-new.html` hashes
`23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c` and
`5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78` remain
**intentionally unresolved** (`AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`).
Resolution requires a human decision on which hash is the correct
`document_version` ordering for that source file — `bootstrap_legacy_registry.py`
will not and should not guess. Do not mark these resolved in CURRENT_STATE.md
without that explicit decision recorded. Not part of any workload; this is a
standing constraint until Natalie decides.

## 2. Foundation Completion Workload 1 — Repository hygiene & evidence durability (APPROVED, in progress)

Natalie approved this workload on 2026-09-08. Scope now also includes the
Mandatory Project Save Completion Rule added to
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (and referenced from
`AGENTS.md`/`CLAUDE.md`) immediately before starting, per explicit
instruction, so the rule becomes durable together with the first
project-state-driven workload. Full scope: commit `h03/`,
`docs/evidence/h03/` (including `H03_EVALUATION_STATUS.md`),
`docs/handoff/h01/frozen-design/` byte-for-byte as they exist, the
already-made comment correction in
`h04/app/migrations/001_h04_document_registry.sql`, the governance rule
addition, and the `docs/project-state/` updates recording it. Full detail:
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`, Workload 1.

## 3. Approve Foundation Completion Workload 2 — Production verification closeout (H01-T01/T18)

Natalie accepted this residual risk on 2026-09-06 as not blocking further
phases, but the reverification itself (H0.0 final manifest, H01-implementation-build
manifest, and live PostgreSQL/Qdrant baseline counts) has still not been
performed. Requires Natalie's **separate, explicit authorization for
read-only production access** — workload approval alone does not clear
this. Full detail: `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`,
Workload 2.

## 4. Approve Foundation Completion Workload 3 — Registry integrity repair tool (I-04 follow-up)

Per `docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`: if a document's
registry write fails after the Qdrant write succeeds, there is no automatic
repair tool yet (the gap is not silent — `run_auditor.py` already reports it
as `ORPHAN_VECTOR`). Explicitly deferred, separately authorized future work;
now scoped as Workload 3 in the foundation completion plan, fully isolated
until a later, separate approval for any production run.

## 5. Approve Foundation Completion Workload 4 — Spec Kit brownfield adoption

Inspection is complete and the plan is formalized
(`docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`). **Do not run `specify init` or
install the `specify` CLI until Natalie explicitly approves this specific
action** — workload approval covers preparation; running `specify init`
itself is called out as its own stop point even within an approved
workload.

## 6. Foundation Completion Workload 5 — H0.5 scope definition & kickoff (blocked on Workload 4 + Natalie's scope choice)

Per the recorded workflow decision: KARMO Invariant Impact Review →
Spec Kit `/speckit.constitution` → `/speckit.specify` → `/speckit.plan` →
`/speckit.tasks` → `/speckit.implement` → validation ladder → phase
acceptance → deployment. H0.5's specific scope is **NEEDS VERIFICATION** —
not defined as of this reconciliation, and this plan does not invent one.

## 7. Confirm current live data counts (routine, low urgency, folds into Workload 2)

SOFTWARE_INVENTORY.md and NETWORK_INVENTORY.md both flag several current
counts (`conversation_memory`, `karmo_memory`, `karmo_semantic_memory`,
`karmo_documents`, `public.document_registry` row count) as **NEEDS
VERIFICATION** — known only as of their last-recorded checkpoint. Fold into
Workload 2's authorized production-facing check rather than a separate
session.

## Not next steps (explicitly out of scope until separately authorized)

- No production access, SSH, deploy, database/Qdrant modification, or
  runtime-service change was performed or is proposed by this pass.
- Spec Kit initialization (see #5) — not performed.
- Workload 1 is approved and in progress (see #2); Workloads 2–5 remain
  unapproved and not started.
- The two ambiguous H0.4 legacy hashes were not resolved (see #1).
- H0.3 was not promoted and remains NO-PROMOTION (see CURRENT_STATE.md).
