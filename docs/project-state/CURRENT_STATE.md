# KARMO Current State

Last reconciled: 2026-09-08 (foundation-acceleration pass). See
MASTER_INDEX.md for status-tag definitions.

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
- Spec Kit: **VERIFIED** approved for evaluation/integration preparation;
  inspection completed; a formal brownfield plan is written
  (`docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`); **still not initialized** — no
  `specify init` command has been run. Initialization requires Natalie's
  separate, explicit approval.
- Foundation acceleration: **VERIFIED** (this session) — a product vision
  (`docs/vision/KARMO_PRODUCT_VISION.md`), an extensibility review
  (`docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md`), a 5-workload
  foundation completion plan (`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`),
  a reusable validation ladder (`docs/governance/KARMO_VALIDATION_LADDER.md`),
  and an autonomous workload execution contract
  (`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`) were created.
  **None of the 5 workloads has been approved or started** as of this
  reconciliation — see NEXT_STEPS.md.
- Active/next phase: **NEEDS VERIFICATION** — H0.5's scope is still
  undefined; Workload 5 in the foundation completion plan is explicitly
  blocked on Natalie choosing it. See NEXT_STEPS.md.
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

**Conflict/gap found during the 2026-09-08 reconciliation, addressed but not
resolved:** the H0.3 implementation (`h03/app/hybrid_ingest.py`,
`hybrid_memory.py`, `sparse_bm25.py`) and its benchmark evidence
(`docs/evidence/h03/*`) still exist only as **untracked working-tree
files** — not committed to `main` or to `feat/h03-hybrid-retrieval` (that
branch's tip is identical to `main`). A fresh clone of this repository today
would still not have the H0.3 prototype or its evidence. This does not
change, and must not be read as changing, the NO-PROMOTION decision — H0.3
remains explicitly not promoted to production. `docs/evidence/h03/H03_EVALUATION_STATUS.md`
was added this session to state the NO-PROMOTION status at the evidence
location itself and enumerate exactly which files belong in the eventual
commit. Committing them is now Workload 1 in
`docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` — not yet approved or
executed.

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

**Conflict found during the 2026-09-08 reconciliation, corrected the same
day:** the migration file `h04/app/migrations/001_h04_document_registry.sql`
carried a stale header comment ("Isolated build artifact only. Not applied
to any production database.") contradicted by the verified H0.4 cutover.
The comment was corrected in the working tree during the foundation-
acceleration pass to state that the migration was applied to production as
part of H0.4 cutover, pointing back to this record. **This edit has not
been committed** — it is staged in the working tree only, pending Workload 1
in `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`. No other content in
that migration file was changed.

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
- **Initialization has still NOT occurred and requires Natalie's separate,
  explicit approval** before any `specify init` command is run. This
  foundation-acceleration pass prepared the plan only — it did not run the
  command, per explicit instruction.

## Confirmed data-state baselines (for reference, HISTORICAL unless restated)

- Pre-H0.1 production PostgreSQL: `conversation_memory=14`, `karmo_memory=1`,
  no `public.karmo_outbox` (H0.1 handoff doc).
- Pre-H0.1 production Qdrant: `karmo_semantic_memory=4`, `karmo_documents=8`,
  `karmo_h00_dense_baseline=8` (H0.1 handoff doc).
- `karmo_documents=8` reconfirmed green during H0.2 validation (operator-attested,
  VERIFIED, matches the baseline above).
