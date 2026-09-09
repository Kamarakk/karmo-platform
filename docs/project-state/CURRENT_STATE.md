# KARMO Current State

Last reconciled: 2026-09-09 (KARMO Large Autonomous Review of PR #14–#21).
See MASTER_INDEX.md for status-tag definitions.

**KARMO FOUNDATION v1: DECLARED COMPLETE, 2026-09-09.** See
`docs/evidence/foundation-v1/FOUNDATION_V1_CLOSEOUT_REPORT.md` for the full
closeout report and `docs/evidence/foundation-v1/` for the complete
independent-verification evidence package.

**Independent merge-readiness review of PRs #14–#21 completed 2026-09-09**
(same day, repository-only, zero production access, zero merges): fresh
reproduction of every test claim, a real cross-PR conflict found and
documented (PR #17 vs. #21, both editing the same `docs/project-state/`
files), and an adversarial security re-review of the Core v2 prototypes
that found and fixed **4 real defects** in PR #19 (154 → 160 tests) plus
2 stale test-count references in PR #20/#21 — all fixed **in the existing
PRs**, no new PR created for fixes. Full detail:
`docs/evidence/autonomous-review/KARMO_PR14_21_MERGE_READINESS.md`. **No
PR was merged. No capability was implemented or chosen.**

## Top-line

- KARMO v0.5 baseline: **HISTORICAL** — frozen, superseded in production by
  H0.1–H0.4 cutovers below. Baseline reference preserved at
  `workspace/app-v05-reference` per H0.0/H0.1 handoff (host-side path, not in
  this repo).
- H0.0: **VERIFIED** complete (per H0.1 handoff doc, `MANIFEST-H0-FINAL.sha256`).
- H0.1: **VERIFIED** production cutover complete (see below).
- H0.2: **VERIFIED** production implementation installed (see below).
- H0.3: **VERIFIED** evaluated, **explicitly APPROVED AS NO-PROMOTION** — not
  part of the active production architecture.
- H0.4: **VERIFIED** production integration complete (see below).
- KARMO Engineering Invariants (I-01–I-09): **VERIFIED** established in
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, mandatory for all future
  phases.
- Legacy registry bootstrap: **VERIFIED** partially applied; 2 records
  intentionally left unresolved (see "Legacy registry bootstrap" below).
- Spec Kit: **VERIFIED** — brownfield initialization completed 2026-09-08
  (`specify init --here --force --integration claude`, v1.0.4);
  `feat/h05-spec-kit-adoption` merged 2026-09-09 (PR #9, `cd72938`). See
  "Spec Kit decision" below.
- Production Access Authorization Gate: **VERIFIED** adopted and merged
  2026-09-09 (PR #12, `e3443e8`, superseding closed PR #11) — see
  "Production Access Authorization Gate adopted" below.
- Foundation Closeout Program: **VERIFIED COMPLETE** (2026-09-09). Workload
  1 merged (PR #7, `db4ff2f`). Workload 2 executed under Natalie's
  temporary, task-specific Production Access Authorization and **PASSED**
  both defined checks (H01-T01, H01-T18) — see
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.
  Workload 3 merged (PR #8, `06ab726`). Workload 4 merged (PR #9,
  `cd72938`). Workload 5 remains not started, per explicit instruction —
  not required for Foundation Complete (see below).
- Active/next phase: **KARMO FOUNDATION v1 — COMPLETE** (declared
  2026-09-09; see `docs/evidence/foundation-v1/FOUNDATION_V1_CLOSEOUT_REPORT.md`).
  H0.5's scope remains undefined and **NEEDS VERIFICATION** — it is the
  first post-foundation capability phase, not a required foundation
  increment, and was explicitly not started or invented tonight. See also
  NEXT_STEPS.md.
- Project Save Completion Rule: **VERIFIED** adopted (2026-09-08) — appended
  to `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, referenced from
  `AGENTS.md` and `CLAUDE.md`. Applies to this and every future session,
  phase, and workload, including Spec Kit work. This reconciliation itself
  is being closed under that rule — see the PROJECT SAVE report accompanying
  this update.
- ChatGPT Session Persistence: **VERIFIED** adopted (2026-09-08, same day) —
  extends the Project Save Completion Rule (same section, not a separate
  rule) to cover Natalie's ChatGPT KARMO planning sessions: ChatGPT
  conversation history is explicitly **not** the authoritative KARMO project
  record; a ChatGPT session's consequential decisions/approvals/requirements
  only count as durably recorded once a repository-capable agent reconciles
  the session's handoff against `docs/project-state/` and commits the
  result, per the same PROJECT SAVE steps already in force. No AGENTS.md or
  CLAUDE.md change was needed — both already reference the rule as a whole
  rather than enumerating its sub-parts.

## H0.1 — Transactional Outbox

**VERIFIED**, from `docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md`
(committed) plus this session's operator attestation:

- Isolated build and H01-T02–T17 failure-matrix acceptance: PASS (repo-evidenced).
- H01-T01 and H01-T18 (live production/host reverification components):
  recorded BLOCKED/NOT EXECUTED; Natalie accepted this residual risk on
  2026-09-06 and cleared H0.1 to proceed — **not** itself an authorization for
  cutover.
- **Production cutover completed** (operator-attested, this session):
  - `karmo_outbox` migration applied to production PostgreSQL.
  - `karmo-h01-relay` systemd **user** service created and enabled for user
    `lofason`.
  - Persistent startup enabled via `loginctl enable-linger lofason` (survives
    logout; reboot persistence depends on systemd user-instance-on-boot,
    flagged **NEEDS VERIFICATION** — not independently re-checked this
    session).
  - Production functional test produced one delivered outbox event.
- No repository evidence file documents the production cutover itself (by
  design — production actions are not recorded in this repo per `AGENTS.md`);
  the above is recorded as VERIFIED on Natalie's direct, specific attestation,
  not on independently re-read production state.

## H0.2 — Knowledge Lifecycle & Vector Versioning

**VERIFIED**:

- Isolated acceptance: PASS, 3/3 (`docs/evidence/h02/H02_LIFECYCLE_REPORT.md`).
- `fix/h02-legacy-active-compat` (PR #4, commit `e3cdca8`) merged: legacy
  vectors without an `is_active` field remain retrievable — existing legacy
  vectors were **not** rewritten to conform to H0.2.
- Production `document_ingest.py` and `document_memory.py` were backed up
  before install (operator-attested).
- H0.2 production implementation installed (operator-attested).
- `karmo_documents` remained green at 8 points during validation
  (operator-attested; matches the pre-H0.1 baseline count of 8 recorded in
  the H0.1 handoff doc).

## H0.3 — Hybrid Retrieval (Dense + BM25 + RRF)

**VERIFIED as evaluated / NO-PROMOTION**:

- Benchmark (`docs/evidence/h03/h03_hybrid_vs_dense_benchmark.md`, synthetic
  corpus, non-authoritative per its own header): Hybrid RRF improved
  Recall@3 (0.800→1.000), MRR (0.517→0.908), and top-1 correct-source rate
  (0.300→0.850) over dense-only, on a synthetic 10-document corpus.
- **Explicitly approved as NO-PROMOTION. Not deployed to production.** H0.3
  is retained as evaluated/retained evidence only and is **not** part of the
  active production retrieval architecture.

**Conflict/gap found during the 2026-09-08 reconciliation, resolved the same
day:** the H0.3 implementation (`h03/app/hybrid_ingest.py`,
`hybrid_memory.py`, `sparse_bm25.py`) and its benchmark evidence
(`docs/evidence/h03/*`, including `H03_EVALUATION_STATUS.md`) previously
existed only as untracked working-tree files. This was Workload 1 in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`, approved and merged
2026-09-08 (PR #7, `db4ff2f`) — the files are now committed to `main`,
byte-for-byte identical to their pre-commit working-tree content (verified
empty diff at commit time, per Workload 1's own acceptance criteria). This
does not change, and must not be read as changing, the NO-PROMOTION
decision — H0.3 remains explicitly not promoted to production; only its
evidence durability gap is closed.

## H0.4 — Integrity, Reconciliation & Production Integration

**VERIFIED**:

- Isolated acceptance: 10/10 PASS
  (`docs/evidence/h04/H04_INTEGRITY_RECONCILIATION_REPORT.md`), plus a
  targeted pagination-fix test after approval (post-approval fix, not a
  reopening of the frozen suite).
- PR #5 (`feat/h04-integrity-reconciliation`) and PR #6
  (`feat/h04-production-integration`) merged to `main`
  (`58daa3d` confirms PR #5; `5b97ddc` confirms PR #6).
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (I-01–I-09) established
  and committed (`db260de`); Mandatory Phase Invariant Impact Review is now
  required before substantial implementation on every future phase.
- H0.4 Invariant Impact Review performed retrospectively on PR #6
  (`docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`); one defect found and
  fixed (I-01/I-05 pagination ceiling in `document_ingest_h04.py`); one
  follow-up documented, not a blocker (I-04: no automatic registry-gap repair
  tool yet — see NEXT_STEPS.md).
- **Production cutover backup created** (operator-attested):
  `/home/lofason/karmo-ai/hardening/h0.4/cutover-20260907T063744Z/` containing
  `core-app-pre-h04.tar.gz` and `karmo-postgres-pre-h04.dump`.
- **Qdrant `karmo_documents` snapshot created** before H0.4 changes
  (operator-attested).
- **`public.document_registry` migration successfully applied** to production
  (operator-attested).
- H0.4 production modules transferred, SHA-256 verified, installed, and
  `py_compile`-validated (operator-attested); `document_registry` existence
  verified in production (operator-attested).

**Conflict found during the 2026-09-08 reconciliation, corrected and
committed the same day:** the migration file
`h04/app/migrations/001_h04_document_registry.sql` carried a stale header
comment ("Isolated build artifact only. Not applied to any production
database.") contradicted by the verified H0.4 cutover. The comment was
corrected to state that the migration was applied to production as part of
the H0.4 cutover, pointing back to this record. This was part of Workload 1
in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`, merged 2026-09-08
(PR #7, `db4ff2f`). No other content in that migration file was changed.

## Legacy registry bootstrap — current stopping point

**VERIFIED** (operator-attested production run of
`h04/app/bootstrap_legacy_registry.py`):

- Dry run: `READY_TO_REGISTER: 3`, `REFUSED: 2`.
- The 2 refused records both belong to source file `karmo-v05-new.html`,
  reason `AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE` (per the script's own
  documented refusal rule: more than one distinct `document_hash` maps to the
  same `source_file` among legacy points, so version ordering cannot be
  assigned without guessing).
  - Hash `23646203eed7e187ce2fe0de12c82d5cf83d0a97893a6bdcd2ed30ae3855af9c`
  - Hash `5f98126d41381a8a0a4c5034b3402b9a4b763fa043bcfa63f27bdefeb7414c78`
  - **These were intentionally not guessed or registered and remain
    unresolved.** Do not mark them resolved without an explicit human
    decision on version ordering.
- Apply run (3 verified-unambiguous legacy documents only):
  `REGISTERED_COUNT: 3`, `REGISTER_FAILED_COUNT: 0`.
  - `0754fbca9b7dd45b7db7d983fe529227ca70fe83d9c67df68cc39513496251ca`
  - `5d1b22a02341bff11ac8bd9f68d6b8ce340418fc7177da752f6307bfc980a7fc`
  - `bac7c97bbfa8e2311bcd67bd81abab5598c551e4ff6fe62bca8b62261d33395e`

## Spec Kit decision

**VERIFIED** (recorded this session, no repository code changed):

- GitHub Spec Kit (v1.0.4) is **approved for evaluation/integration**,
  operating strictly **under** KARMO governance, never above or in
  competition with it.
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, `AGENTS.md`, and
  `CLAUDE.md` remain authoritative; Spec Kit's constitution must reference,
  not duplicate or weaken, the invariants document.
- H0.0–H0.4 will **not** be retroactively reorganized for Spec Kit; adoption
  is prospective, starting with the next development phase (H0.5).
- Brownfield/existing-project integration path is required; no
  force/overwrite initialization is authorized without review.
- **Inspection completed** (CLI version, files added, brownfield workflow,
  constitution mechanism, collision check — no repo files changed).
- **Brownfield initialization plan formalized** as
  `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`, including the exact
  `specify init` command, the constitution content plan, and the KARMO
  governance-hierarchy diagram Spec Kit must operate beneath.
- **Initialization completed 2026-09-08** (Foundation Closeout Program,
  Workload 4), on Natalie's explicit pre-authorization to run the exact
  command already prepared in `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`:
  `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.0.4`
  then `specify init --here --force --integration claude`, on branch
  `feat/h05-spec-kit-adoption`. Diff inspected immediately after: only
  `.claude/skills/speckit-*/` and `.specify/` appeared, exactly as the
  brownfield plan's own acceptance criterion required — no other file was
  touched. `.specify/memory/constitution.md` was filled in (replacing the
  placeholder template) with content subordinating it to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, per the brownfield
  plan's constitution content plan, plus principles drawn from the
  repository's own existing conventions (isolated-before-production,
  report-only-by-default for audit/repair tools, no overlapping test
  suites). Merged to `main` 2026-09-09 (PR #9, `cd72938`).

## Foundation Closeout Program (2026-09-08)

**VERIFIED** — Natalie approved a consolidation review's recommendation to
run Workloads 2, 3, and 4 of `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`
as one autonomous program, with pre-authorization for the two standing-gate
actions each carried (read-only production access for Workload 2;
`specify init` for Workload 4).

- **Workload 2 (production verification closeout): PASS, executed
  2026-09-09.** Natalie's temporary, session-scoped, task-specific
  Production Access Authorization (2026-09-09) lifted the default
  prohibition for exactly this task, per the newly-adopted Mandatory
  Production Access Authorization Gate (see below). Both defined checks
  executed and passed: H01-T01 (manifest presence/hash) and H01-T18
  (baseline counts). Full detail, exact commands, and observed values:
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`. No
  write, restart, deployment, or configuration change was performed.
- **Workload 3 (registry integrity repair tool): complete, merged.**
  `h04/app/registry_repair.py` + `h04/tests/test_h04_registry_repair.py`
  (4/4 PASS) + targeted regression re-run (11/11 PASS, existing suite
  unchanged) + Invariant Impact Review, all per
  `docs/evidence/h04/H04_REGISTRY_REPAIR_REPORT.md`. PR #8 merged
  2026-09-09, `06ab726`. Still isolated-only — no production execution
  performed or authorized (that remains separate, future work).
- **Workload 4 (Spec Kit brownfield adoption): complete, merged.** See
  "Spec Kit decision" above. PR #9 merged 2026-09-09, `cd72938`.
- **Workload 5 (H0.5 scope definition): not started**, per explicit
  instruction not to invent H0.5's scope. Not required for Foundation
  Complete (see below).

### KARMO FOUNDATION v1 status: **COMPLETE, declared 2026-09-09**

Per the consolidation review's own criterion (Foundation Complete =
Workload 1 merged + an explicit Natalie decision on Workloads 2/3), applied
without modification: Workload 1 merged (PR #7); Workload 2 executed under
explicit authorization and passed; Workload 3 merged. PRs #8, #9, #10, and
the governance gate (PR #12, superseding closed PR #11) are all merged to
`main`. Full closeout report and independent-verification evidence package:
`docs/evidence/foundation-v1/`. H0.5/Workload 5 was correctly not required
and not started — it is the first post-foundation capability phase, not a
foundation increment.

One genuinely new, non-blocking finding surfaced during closeout: a
read-only H0.4 production audit (beyond Workload 2's own defined scope,
run as a directly-relevant supporting check) found `ORPHAN_VECTOR` (2,
matching the already-known ambiguous legacy hashes exactly — not new) and
`ACTIVE_STATE_MISMATCH` (3, traced to a `reconciliation.check_active_version_state`
design gap for legacy-bootstrapped documents — an auditor blind spot, not
a data problem; recommended, not required, future follow-up). Full detail:
`docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.

## Production Access Authorization Gate adopted (2026-09-08, governance correction)

**VERIFIED** — Natalie explicitly approved resolving the conflict this
session's Workload 2 attempt surfaced: `CLAUDE.md` item 4 and `AGENTS.md`'s
"Authority and boundaries" section both stated an unconditional,
no-exception prohibition on any production access, leaving no path for
Natalie's own explicit, task-specific authorizations (the same kind that
already governed the H0.1/H0.2/H0.4 production cutovers) to actually apply.

- Added the **Mandatory Production Access Authorization Gate** to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` (new section, between
  the existing Mandatory Phase Invariant Impact Review and Mandatory
  Project Save Completion Rule sections — same non-duplicating pattern as
  both) — the single canonical rule: production access prohibited by
  default; lifted only by an explicit, task-specific authorization defining
  target system, purpose, permitted operations, read-only vs. write
  authority, and applicable commands; read-only never implies write;
  writes/deployment/destructive actions/migrations/restarts/config
  changes/data repair/deletion each need their own separate grant;
  single-task scope, auto-expires on completion; defined STOP conditions
  (unexpected state, scope ambiguity, contradictory evidence, insufficient
  granted authority); secrets never exposed/printed/persisted; does not
  override any other invariant, review, validation, or approval gate; the
  narrower rule always wins; a general workload approval never substitutes.
  Includes a copy-pasteable authorization-record shape.
- `CLAUDE.md` item 4 and `AGENTS.md`'s equivalent bullet both rewritten to
  reference this gate rather than stating an unconditional, no-exception
  prohibition (`AGENTS.md` was not named in Natalie's request but carried
  the identical unresolved conflict in an even more absolute form — leaving
  it as-is would have left the conflict only partially resolved).
  `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`'s existing
  "access production when not explicitly authorized" bullet cross-referenced
  to the same gate, not restated.
- Invariant Impact Review performed before this change:
  `docs/evidence/governance/PRODUCTION_ACCESS_AUTHORIZATION_GATE_INVARIANT_IMPACT_REVIEW.md`.
- No production was accessed and no Production Access Authorization was
  issued or acted on by the governance-drafting task itself — a purely
  canonical-governance documentation change. Merged 2026-09-09 as PR #12
  (`e3443e8`) — the original PR #11 was auto-closed when its base branch
  (PR #10's, deleted on merge) disappeared; PR #12 carries identical
  content, rebased onto `main`. First actually exercised the same night,
  for Workload 2 — see "Foundation Closeout Program" above and
  `docs/evidence/foundation-v1/`.
- This does **not** retroactively require re-justifying the already-accepted
  H0.1/H0.2/H0.4 production cutover history (I-01: those predate this gate
  and remain VERIFIED as recorded); it governs future production access
  only.

## Confirmed data-state baselines (for reference, HISTORICAL unless restated)

- Pre-H0.1 production PostgreSQL: `conversation_memory=14`, `karmo_memory=1`,
  no `public.karmo_outbox` (H0.1 handoff doc).
- Pre-H0.1 production Qdrant: `karmo_semantic_memory=4`, `karmo_documents=8`,
  `karmo_h00_dense_baseline=8` (H0.1 handoff doc).
- `karmo_documents=8` reconfirmed green during H0.2 validation (operator-attested,
  VERIFIED, matches the baseline above).
