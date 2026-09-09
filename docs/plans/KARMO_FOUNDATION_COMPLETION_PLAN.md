# KARMO Foundation Completion Plan

Consolidates the *actual* remaining foundation work, as evidenced by
`docs/project-state/` and the H0.1–H0.4 evidence/handoff record — not
reconstructed from assumption. Where the record does not yet define a
scope (H0.5's content), this plan says so rather than inventing one.

Each workload below is designed to run under
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` once Natalie
approves it, and to validate itself using
`docs/governance/KARMO_VALIDATION_LADDER.md`. Neither is restated per
workload — only the workload-specific scope of each is given.

Order reflects dependency, not strict priority; Workloads 1–3 are mutually
independent and could run in any order or in parallel sessions.

---

## Workload 1 — Repository Hygiene & Evidence Durability

**Objective:** bring committed git history in line with the verified
project-state record by committing evidence/artifacts that currently exist
only in the working tree, and correcting one stale in-repo comment.

**Prerequisites:** none beyond this plan's approval. `docs/project-state/`
reconciliation is already complete.

**Exact scope:**
- Commit, byte-for-byte as they exist today: `h03/app/`, `h03/requirements.txt`,
  `h03/tests/`, `docs/evidence/h03/*` (including the new
  `H03_EVALUATION_STATUS.md`).
- Commit, byte-for-byte, unmodified: `docs/handoff/h01/frozen-design/`.
- Commit the already-made comment correction in
  `h04/app/migrations/001_h04_document_registry.sql`.

**Explicitly out of scope:** any code change to H0.3 implementation, any
edit to frozen-design content, any schema/behavior change to the H0.4
migration, promoting H0.3, resolving the two ambiguous
`karmo-v05-new.html` hashes, any production action.

**Affected invariants:** I-08 only, meaningfully (a targeted re-run, not the
full suite, since only a comment changed in a migration file — see Tests).
I-06 is NOT AFFECTED (no schema/behavior change).

**Compatibility requirements:** none.

**Implementation tasks:** create branch; `git add` exactly the listed paths;
one commit (or a small number, logically grouped); open PR.

**Tests:** re-run the H0.4 isolated acceptance suite once, targeted,
because a file under `h04/app/migrations/` was touched even though only a
comment changed (I-08: state-why — touching a migration file, however
trivially, is cheap enough to reverify rather than assume). No test is
needed for the H0.3/frozen-design commits since nothing in their content
changes — `git diff` against the working tree before/after staging should
be empty.

**Acceptance criteria:** `git status` clean except the new branch; H0.4
suite still 10 passed; `git diff --check` clean; a diff of the newly
committed H0.3/frozen-design files against their pre-commit working-tree
content is empty.

**Evidence required:** a short note (in this workload's PR description and
an addendum to `docs/project-state/CHANGE_LOG.md`) recording the commit
hash(es) and confirming no content changed for the H0.3/frozen-design files
beyond adding them to git.

**Rollback requirements:** trivial — `git revert` the commit(s); nothing
production-facing, nothing destructive.

**Approval boundaries:** this workload's own purpose is to commit, so
workload approval covers branch/commit/PR creation (an ordinary reversible
git operation on a feature branch, not one of the standing gates). Merge
still requires Natalie's separate approval, matching every prior PR in this
repository's history.

**Dependencies on previous workloads:** none.

**What Claude may execute autonomously:** branch, stage, commit, targeted
H0.4 re-verification, PR preparation.

**Where Claude must STOP for Natalie:** before merging the PR; immediately,
without committing, if any diff of the H0.3/frozen-design content shows an
unexpected difference from what this reconciliation already read (would
indicate undocumented drift, not a simple commit).

**Estimated effort:** small — well under an hour of autonomous execution;
mostly gated by PR review turnaround, not implementation time.

---

## Workload 2 — Production Verification Closeout (H01-T01/H01-T18)

**Objective:** close the residual risk Natalie accepted on 2026-09-06 by
reverifying, read-only, the two production-state components the H0.1
failure matrix left BLOCKED.

**Prerequisites:** Natalie's **explicit, separate authorization for
read-only production access** — workload approval alone does not clear
this; production access is a standing gate regardless of workload
approval, per the autonomous execution contract.

**Exact scope:**
- Confirm presence/hash of `MANIFEST-H0-FINAL.sha256` and
  `MANIFEST-H01-ISOLATED-BUILD.sha256` on `karmo-ai01` (H01-T01).
- Reverify live PostgreSQL counts (`conversation_memory`, `karmo_memory`,
  presence of `public.karmo_outbox`) and live Qdrant point counts
  (`karmo_semantic_memory`, `karmo_documents`, `karmo_h00_dense_baseline`)
  against the values recorded in
  `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`
  (H01-T18).

**Explicitly out of scope:** any write action of any kind; remediating any
discrepancy found (a new, separately scoped workload if one is found); any
other area of production.

**Affected invariants:** I-02 (this validates production parity claims
already made), I-07 (this is itself an observability/verification action).

**Compatibility requirements:** none — read-only.

**Implementation tasks:** prepare the exact read-only commands in advance
(see `docs/project-state/COMMAND_LOG.md`); execute only after explicit
authorization; record results.

**Tests:** none in the code sense — this reverification *is* the test.
Passing means recorded values match; a mismatch is not a failure to fix
here, it is a finding to report.

**Acceptance criteria:** both manifests confirmed present with matching
hashes, or a discrepancy explicitly reported; baseline counts confirmed or
a discrepancy explicitly reported.

**Evidence required:** an addendum to `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md`
(appended, not rewritten — the original PASS/BLOCKED record for H01-T02–T17
stays intact) recording the H01-T01/T18 reverification result, plus a
`docs/project-state/CURRENT_STATE.md` update.

**Rollback requirements:** none — no write occurs.

**Approval boundaries:** Claude may prepare the exact commands and the
report template autonomously. **Must STOP before any actual production
connection** and present the exact commands for Natalie's authorization
first.

**Dependencies on previous workloads:** none; independent of Workload 1.

**Where Claude must STOP for Natalie:** before establishing any production
connection; immediately upon finding any discrepancy against the recorded
baseline (do not silently reconcile — this is exactly the "evidence
conflicts with an authoritative record" stop condition).

**Estimated effort:** small once authorized — the checks themselves are
quick; total time is dominated by scheduling the authorized session, not
execution.

---

## Workload 3 — Registry Integrity Repair Tool (I-04 follow-up)

**Objective:** build the dedicated, explicitly-authorized repair tool for
the `ORPHAN_VECTOR` registry-gap case that
`docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md` documented as deferred,
future, separately-authorized work — not a blocker to H0.4, but the next
concrete piece of it.

**Prerequisites:** none technical; Workload 1 is recommended first so the
H0.4 evidence base is fully committed before extending it, but not a hard
blocker.

**Exact scope:** a new isolated module (working name
`h04/app/registry_repair.py`) that, given an `ORPHAN_VECTOR` finding from
the existing auditor, can construct the missing `document_registry` row
strictly from the Qdrant payload's own recorded metadata — following
`bootstrap_legacy_registry.py`'s verify-don't-guess pattern (refuse on any
ambiguity, never fabricate provenance). Report-only by default; an explicit
`--apply` flag gated exactly like `bootstrap_legacy_registry.py`'s. New
isolated acceptance suite against the existing H0.4 Docker stack.

**Explicitly out of scope:** any automatic/scheduled/background repair (no
cron, no daemon — `CLAUDE.md` prohibits new autonomous schedules without
Natalie's written approval); any change to `auditor.py`'s report-only
guarantee; any production execution of the new tool (a separate, future
approval, exactly as `bootstrap_legacy_registry.py`'s own production dry-run
and `--apply` runs each required explicit authorization).

**Affected invariants:** I-04 (idempotency/retry — this is the tool's core
purpose), I-09 (authority — report-only default, explicit `--apply`, human-
run, never automatic), I-03 (data authority — must refuse rather than
fabricate on any ambiguous/inconsistent case, mirroring the bootstrap tool).

**Compatibility requirements:** purely additive; no `document_registry`
schema change; must not alter `auditor.py`'s or `reconciliation.py`'s
existing behavior.

**Implementation tasks:** design the refusal/verification rules (mirroring
`bootstrap_legacy_registry.py`); implement; write one isolated test per
scenario (healthy repair, ambiguous/refuse case, already-registered no-op,
report-only-by-default proven the same way `test_auditor_is_report_only`
proves it — write-call injection that fails hard if triggered).

**Tests:** new suite, e.g. `h04/tests/test_h04_registry_repair.py`, run
against the existing isolated Docker stack.

**Acceptance criteria:** new suite passes; `auditor.py` unchanged (verified
by diff, not just by test); existing H0.4 10/10 suite re-run once, targeted,
because this shares `reconciliation.py`'s finding types (I-08: state-why).

**Evidence required:** a new report under `docs/evidence/h04/`, in the
shape of the existing H0.4 reports.

**Rollback requirements:** none needed until/unless a future workload
approves running it against production — additive, isolated-only tool
until then.

**Approval boundaries:** Claude may design, implement, and fully test this
within isolated infrastructure autonomously once the workload is approved.
**Must STOP before any production run of the tool** — a separate approval,
matching the bootstrap tool's own history.

**Dependencies on previous workloads:** none strictly; logically extends
already-accepted H0.4 architecture.

**Where Claude must STOP for Natalie:** before any production execution of
the tool (even with `--apply` on the isolated stack, that's fine — only
production is gated); if the design would require touching `auditor.py`'s
report-only guarantee (a scope-expansion signal, not an ordinary
implementation detail).

**Estimated effort:** medium — comparable in shape to the original H0.4
integrity/reconciliation build, but narrower in scope (one tool, reusing
existing patterns); a few hours of autonomous implementation and testing.

---

## Workload 4 — Spec Kit Brownfield Adoption

**Objective:** adopt Spec Kit tooling for the next development phase, per
the brownfield inspection already completed and the detailed plan in
`docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`.

**Prerequisites:** Natalie's **explicit, separate authorization to actually
run `specify init`** — this remains a standing requirement regardless of
workload approval, per Phase 7's explicit instruction to prepare but not
execute.

**Exact scope:** install `specify-cli` (local machine only, not a repo
change); on branch `feat/h05-spec-kit-adoption`, run
`specify init --here --force --integration claude`; write
`.specify/memory/constitution.md` via `/speckit.constitution`, explicitly
referencing `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`; commit the
resulting `.specify/` and `.claude/skills/` files; open PR.

**Explicitly out of scope:** writing any H0.5 spec/plan/tasks yet (begins
only in Workload 5, once H0.5's scope is chosen); any modification to
`AGENTS.md`, `CLAUDE.md`, or any governance file; retroactively speccing
H0.0–H0.4.

**Affected invariants:** I-01 (tooling forward-compat — low risk, purely
additive), I-09 (the constitution should reference, not reinvent, I-09's
capability classification).

**Compatibility requirements:** none — additive only; verified by diff that
nothing outside `.specify/`, `.claude/skills/`, is touched.

**Implementation tasks:** as described in
`docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`.

**Tests:** none in the code sense; validation is `git diff` review
confirming only the additive paths changed, plus a read of the generated
constitution for correct invariant reference.

**Acceptance criteria:** constitution explicitly subordinates itself to
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`; no other file modified.

**Evidence required:** the diff itself, attached to the PR; an update to
`docs/project-state/CURRENT_STATE.md` recording initialization as complete
(only once it actually is).

**Rollback requirements:** `git branch -D` before merge, or revert the
single commit after; `uv tool uninstall specify-cli` removes the local CLI
only.

**Approval boundaries:** Claude may prepare everything (branch, constitution
draft text, exact commands) autonomously. **Must STOP before running
`specify init`.** Merge requires Natalie's separate approval.

**Dependencies on previous workloads:** none technically; logically should
precede Workload 5, since H0.5 is intended to run through the Spec Kit
workflow.

**Where Claude must STOP for Natalie:** before executing `specify init`;
before merging the resulting PR.

**Estimated effort:** small — under an hour of autonomous execution once
authorized; the CLI install and init are single commands, the constitution
draft is the only real writing task.

---

## Workload 5 — H0.5 Scope Definition & Kickoff

**Objective:** define and begin the next KARMO development phase under the
now-mandatory invariant-review-first, Spec Kit-structured workflow.

**Prerequisites:** Workload 4 merged; **Natalie has chosen H0.5's actual
feature scope.** This is explicitly undetermined as of this plan — no H0.5
hardening-plan document exists anywhere in this repository, and this plan
does not invent one, per instruction.

**Exact scope:** TBD, pending Natalie's scope decision. Once chosen, the
fixed process is: Invariant Impact Review → `/speckit.specify` →
`/speckit.plan` → `/speckit.tasks` → `/speckit.implement` → validation
ladder → evidence → phase acceptance (per
`docs/governance/KARMO_VALIDATION_LADDER.md`).

**Explicitly out of scope:** Claude choosing H0.5's scope unilaterally;
implementing any "Future Ideas" vision-domain capability
(`docs/vision/KARMO_PRODUCT_VISION.md`) without its own separate scoping
and approval.

**Affected invariants:** all nine, to be assessed fresh via the Mandatory
Phase Invariant Impact Review once scope is known — cannot be predetermined
here.

**Compatibility requirements / implementation tasks / tests / acceptance
criteria / evidence required / rollback requirements:** all TBD, to be
defined by this workload's own `/speckit.specify` and `/speckit.plan`
artifacts once scope is chosen — that is the point of running it through
Spec Kit rather than predefining it in this document.

**Approval boundaries:** Natalie must approve H0.5's scope before
`/speckit.specify` is run. After that, ordinary implementation follows the
autonomous execution contract like any other approved workload, subject to
whatever production/destructive/external boundaries that workload's own
`/speckit.plan` identifies.

**Dependencies on previous workloads:** Workload 4.

**Where Claude must STOP for Natalie:** before choosing H0.5's scope (must
come from Natalie, not be inferred); at whatever production/destructive/
external-action boundary this workload's own plan identifies, once scoped.

**Estimated effort:** cannot be meaningfully estimated until scope is
chosen — could range from a small, single-session workload to something
comparable to H0.4 depending on what is chosen.

---

## Summary table

| # | Workload | Depends on | Production access? | Estimated effort |
|---|---|---|---|---|
| 1 | Repository hygiene & evidence durability | — | No | Small (<1 hr + PR review) |
| 2 | Production verification closeout | — | Yes (read-only, gated) | Small once authorized |
| 3 | Registry integrity repair tool | — (logically after 1) | No (isolated only) | Medium (a few hours) |
| 4 | Spec Kit brownfield adoption | — | No | Small (<1 hr) |
| 5 | H0.5 scope definition & kickoff | 4 | TBD, scope-dependent | Undetermined until scoped |
