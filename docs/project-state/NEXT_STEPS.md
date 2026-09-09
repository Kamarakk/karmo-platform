# KARMO Next Steps

See MASTER_INDEX.md for status-tag definitions. As of the 2026-09-08
Foundation Closeout Program pass, the primary next action is **Natalie
resolving the Workload 2 blocker** (see below) and deciding how PRs #8/#9
merging relates to declaring KARMO FOUNDATION v1 complete — see
`docs/project-state/CURRENT_STATE.md`'s "Foundation Closeout Program"
section for full detail.

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

## 2. Foundation Completion Workload 1 — Repository hygiene & evidence durability (MERGED)

Approved and merged 2026-09-08 (PR #7, `db4ff2f`): `h03/`,
`docs/evidence/h03/` (including `H03_EVALUATION_STATUS.md`),
`docs/handoff/h01/frozen-design/` committed byte-for-byte; the
`h04/app/migrations/001_h04_document_registry.sql` comment correction
committed; the Mandatory Project Save Completion Rule (and its ChatGPT
Session Persistence extension) added to
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. Complete — no further
action.

## 3. Foundation Completion Workload 2 — Production verification closeout: BLOCKED, needs Natalie's decision

Natalie approved and pre-authorized this workload as part of the Foundation
Closeout Program (2026-09-08), but the read-only production connection was
**not attempted** — `CLAUDE.md` item 4's unconditional prohibition on
production database/Qdrant access governs this session and was not
overridden by the chat-level pre-authorization (see
`docs/project-state/CURRENT_STATE.md`, "Foundation Closeout Program"
section, for the full reasoning). **Natalie must choose one:**

- Run the two prepared read-only commands
  (`docs/project-state/COMMAND_LOG.md`, H01-T01/H01-T18) herself or via an
  operator, and provide the results for reconciliation into
  `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md` and `CURRENT_STATE.md`; or
- Explicitly amend `CLAUDE.md` to narrow item 4 for a defined class of
  read-only verification (a governance change requiring her own explicit,
  separate approval — not something any session should decide for itself); or
- Explicitly accept Workload 2 as permanently deferred, non-blocking
  closeout — consistent with how the residual risk it reverifies was
  already accepted on 2026-09-06.

## 4. Foundation Completion Workload 3 — Registry integrity repair tool (COMPLETE, PR OPEN)

Complete in isolation, 2026-09-08: `h04/app/registry_repair.py` + 4/4 new
suite PASS + 11/11 targeted regression re-run PASS + Invariant Impact
Review, per `docs/evidence/h04/H04_REGISTRY_REPAIR_REPORT.md`. PR #8
(`feat/h04-registry-repair`) open, awaiting Natalie's merge decision. No
production execution performed or authorized — a separate, future,
explicitly-authorized action if ever pursued.

## 5. Foundation Completion Workload 4 — Spec Kit brownfield adoption (COMPLETE, PR OPEN)

Complete 2026-09-08: `specify init --here --force --integration claude`
(v1.0.4) run on Natalie's explicit pre-authorization; diff confirmed
additive-only (`.claude/skills/`, `.specify/`); constitution filled in,
subordinated to `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. PR #9
(`feat/h05-spec-kit-adoption`) open, awaiting Natalie's merge decision.

## 6. Foundation Completion Workload 5 — H0.5 scope definition & kickoff (blocked on Workload 4 merge + Natalie's scope choice)

Per the recorded workflow decision: KARMO Invariant Impact Review →
`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`
→ validation ladder → phase acceptance → deployment. H0.5's specific scope
remains **NEEDS VERIFICATION** — not defined, and explicitly not invented by
this or any prior pass. The Foundation Closeout consolidation review's
extensibility-review-derived observation (a tool/capability registry as a
strong first candidate, since every planned domain depends on it) is a
suggestion for Natalie to weigh, not a decision made on her behalf.

## 7. Confirm current live data counts (routine, low urgency, folds into Workload 2)

`SOFTWARE_INVENTORY.md` and `NETWORK_INVENTORY.md` both flag several current
counts (`conversation_memory`, `karmo_memory`, `karmo_semantic_memory`,
`karmo_documents`, `public.document_registry` row count) as **NEEDS
VERIFICATION** — known only as of their last-recorded checkpoint. Folds into
Workload 2's authorized production-facing check once that is unblocked,
rather than a separate session.

## Not next steps (explicitly out of scope until separately authorized)

- No production access, SSH, deploy, database/Qdrant modification, or
  runtime-service change was performed by this pass — including the
  Workload 2 read-only checks, per item 3 above.
- No H0.5 spec/plan/tasks were written — Workload 5 remains blocked on
  Natalie's scope choice (see #6).
- The two ambiguous H0.4 legacy hashes were not resolved (see #1).
- H0.3 remains NO-PROMOTION (unaffected by its evidence now being
  committed — see CURRENT_STATE.md).
- No PR was merged by this pass (PRs #8 and #9 opened, not merged; PR #7
  was already merged before this pass began).
