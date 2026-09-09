# KARMO Change Log

Chronological. Repo-evidenced entries cite a commit/PR; production entries
are marked operator-attested where no repo evidence file exists (by design —
production state is not recorded in this repo per `AGENTS.md`). See
MASTER_INDEX.md for status-tag definitions.

## Pre-repo / bootstrap

- **VERIFIED** (repo) — `f23d439` "chore: complete KARMO repository bootstrap";
  `8559924`, `c5c0a7d` initial uploads. PR #1 (`6b852d4`,
  `chore/mac-dev-bootstrap`) merged.

## H0.1 — Transactional Outbox

- **VERIFIED** (repo) — `e9a39a0` import of verified H0.1 handoff artifacts.
- **VERIFIED** (repo) — `b38c851` add isolated H0.1 failure matrix;
  `e26626d` align H0.1 validation with frozen matrix. PR #2 (`f27adf2`,
  `feat/h01-handoff-import`) merged. Failure-matrix report corrected and
  superseded in place (`docs/evidence/h01/H01_FAILURE_MATRIX_REPORT.md`);
  H01-T02–T17 PASS, H01-T01/H01-T18 BLOCKED, closeout accepted by Natalie
  2026-09-06.
- **VERIFIED** (operator-attested, 2026-09-07/08) — H0.1 production cutover:
  `karmo_outbox` migration applied; `karmo-h01-relay` systemd user service
  created and enabled; `loginctl enable-linger lofason` set; production
  functional test delivered one outbox event. No repo evidence file for this
  step (correct, per governance — no production data in this repo).

## H0.2 — Knowledge Lifecycle & Vector Versioning

- **VERIFIED** (repo) — `5308bfc` capture H0.2 production document
  references; `ec5c52f` add H0.2 knowledge lifecycle and vector versioning;
  `5fb5d7e` add deployable H0.2 lifecycle implementation. PR #3 (`8eb4b27`,
  `feat/h02-knowledge-lifecycle`) merged.
- **VERIFIED** (repo) — `e3cdca8` fix: preserve legacy document retrieval in
  H0.2 (legacy-active compatibility). PR #4 (`7398a18`,
  `fix/h02-legacy-active-compat`) merged.
- **VERIFIED** (operator-attested) — production `document_ingest.py` and
  `document_memory.py` backed up; H0.2 production implementation installed;
  `karmo_documents` remained green at 8 points during validation.

## H0.3 — Hybrid Retrieval Evaluation

- **VERIFIED** (repo) — `d7919f0` capture H0.3 production retrieval
  references (`docs/handoff/h03/*.py`, committed).
- **VERIFIED as evaluated, NO-PROMOTION** (operator-attested + local
  evidence) — dense+BM25+RRF benchmark completed on a synthetic corpus,
  showed improved retrieval quality; explicitly **not** promoted to
  production.
- **NEEDS VERIFICATION / gap** — the H0.3 implementation
  (`h03/app/*.py`) and benchmark evidence (`docs/evidence/h03/*`) are present
  in the local working tree only; they were never committed to `main` or to
  `feat/h03-hybrid-retrieval` (branch tip identical to `main`). No commit
  hash exists for this work as of 2026-09-08.

## H0.4 — Integrity, Reconciliation & Production Integration

- **VERIFIED** (repo) — `ea97310` capture H0.4 production integrity
  references; `b0d0233` add H0.4 integrity and reconciliation. PR #5
  (`58daa3d`, `feat/h04-integrity-reconciliation`) merged. Isolated
  acceptance 10/10 PASS.
- **VERIFIED** (repo) — `db260de` add KARMO Engineering Invariants
  governance framework (I-01–I-09 established).
- **VERIFIED** (repo) — `cc0b59f` fix: add inheritance/forward-compat rule;
  fix H0.4 ingest pagination ceiling; `b6c8fcc` wire H0.4 production
  integrity integration. PR #6 (`5b97ddc`, `feat/h04-production-integration`)
  merged. Retrospective Invariant Impact Review performed
  (`docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md`).
- **VERIFIED** (operator-attested, 2026-09-07) — H0.4 production cutover:
  backup created at
  `/home/lofason/karmo-ai/hardening/h0.4/cutover-20260907T063744Z/`
  (`core-app-pre-h04.tar.gz`, `karmo-postgres-pre-h04.dump`); Qdrant
  `karmo_documents` snapshot created; `public.document_registry` migration
  applied to production; production modules transferred, SHA-256 verified,
  installed, `py_compile`-validated; `document_registry` existence verified.

## Legacy registry bootstrap

- **VERIFIED** (operator-attested, 2026-09-08) — dry run:
  `READY_TO_REGISTER: 3`, `REFUSED: 2` (both `karmo-v05-new.html`,
  `AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE`). Apply run:
  `REGISTERED_COUNT: 3`, `REGISTER_FAILED_COUNT: 0`. The 2 refused records
  remain intentionally unresolved.

## Workflow decisions

- **VERIFIED** (this session, 2026-09-07/08) — GitHub Spec Kit approved for
  evaluation/integration under KARMO governance; brownfield inspection
  completed (no repo files changed); initialization **not** performed,
  pending Natalie's approval.

## Foundation acceleration (2026-09-08, second pass same day)

- **VERIFIED** (this session) — Natalie approved the `docs/project-state/`
  persistent record set created in the prior pass, then requested
  restructuring the remaining foundation work into large autonomous
  workloads.
- **VERIFIED** (this session, documentation only, nothing committed) —
  created `docs/vision/KARMO_PRODUCT_VISION.md`,
  `docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md`,
  `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` (5 workloads),
  `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`,
  `docs/governance/KARMO_VALIDATION_LADDER.md`, and
  `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md`.
- **VERIFIED** (this session, uncommitted working-tree edit) — corrected the
  stale "not applied to production" comment in
  `h04/app/migrations/001_h04_document_registry.sql`; no schema/behavior
  change.
- **VERIFIED** (this session, new file, uncommitted) — added
  `docs/evidence/h03/H03_EVALUATION_STATUS.md` stating H0.3's NO-PROMOTION
  status at the evidence location and enumerating the exact file set for a
  future commit.
- **Explicitly not done this session:** no workload was approved or
  started; the H0.3/frozen-design artifacts were not committed; Spec Kit
  was not initialized; the two ambiguous `karmo-v05-new.html` hashes were
  not resolved; no production access occurred.

## Project Save Completion Rule adopted (2026-09-08, third pass same day)

- **VERIFIED** (this session) — Natalie approved Workload 1 and requested
  the Mandatory Project Save Completion Rule be added to governance before
  it starts. Appended to `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`
  (new section, not a numbered invariant, structured like the existing
  Mandatory Phase Invariant Impact Review section); referenced (not
  duplicated) from `AGENTS.md` and `CLAUDE.md`.
- Per instruction, not committed separately — staged to be included in the
  Workload 1 commit/PR alongside the repository-hygiene fixes, so the rule
  and the first project-state-driven workload become durable together.
- This entry's Workload 1 commit landed as `fd1d724` on branch
  `chore/repo-hygiene-and-project-save-rule` (PR #7, opened, not merged).

## ChatGPT Session Persistence adopted (2026-09-08, follow-up to Workload 1, before PR #7 merge)

- **VERIFIED** (this session) — Natalie requested an extension to the
  Mandatory Project Save Completion Rule (not a new rule) covering
  consequential KARMO information produced in her ChatGPT planning
  sessions: ChatGPT conversation history is explicitly not the
  authoritative KARMO project record; the Git repository, including
  `docs/project-state/`, is. Added as an "Extension: ChatGPT Session
  Persistence" subsection directly under the existing Mandatory Project
  Save Completion Rule in
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`.
- `AGENTS.md`/`CLAUDE.md` were not modified — both already reference the
  rule as a whole rather than restating its sub-parts, so their existing
  references already cover this extension.
- Committed as a follow-up to the existing
  `chore/repo-hygiene-and-project-save-rule` branch, updating PR #7 rather
  than opening a new one, per instruction not to redo Workload 1. PR #7
  remains unmerged.

## Workload 1 merged (2026-09-08)

- **VERIFIED** — PR #7 (`chore/repo-hygiene-and-project-save-rule`) merged
  as `db4ff2f`. `h03/`, `docs/evidence/h03/`, `docs/handoff/h01/frozen-design/`
  committed byte-for-byte; H0.4 migration comment correction committed; the
  Mandatory Project Save Completion Rule and its ChatGPT extension are now
  durable in `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`.

## Foundation Closeout Program (2026-09-08)

- **VERIFIED** — a consolidation review (requested by Natalie) analyzed
  whether Workloads 2–5 of `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md`
  could be run as one autonomous program. Natalie approved and
  pre-authorized running Workloads 2, 3, and 4 together in one session,
  including the two standing-gate actions each carried (read-only
  production access for Workload 2; `specify init` for Workload 4).
- **Workload 2 (production verification closeout): NOT EXECUTED, blocked.**
  `CLAUDE.md` item 4's unconditional prohibition on production database/
  Qdrant/SSH access was treated as controlling over the chat-level
  pre-authorization, since it carries no approval-override clause (unlike
  item 5) and the file's own preamble marks it as overriding session
  instructions. No connection to `karmo-ai01` was attempted, though the
  host was confirmed network-reachable. Full reasoning and the three
  resolution paths offered to Natalie: `docs/project-state/CURRENT_STATE.md`,
  "Foundation Closeout Program" section.
- **Workload 3 (registry integrity repair tool): complete in isolation.**
  `h04/app/registry_repair.py`, isolated report/apply CLI constructing a
  missing `document_registry` row for an `ORPHAN_VECTOR` finding strictly
  from Qdrant payload metadata, refusing on any ambiguity — mirrors
  `bootstrap_legacy_registry.py`'s verify-don't-guess pattern for full
  H0.4-lifecycle orphan points rather than legacy points. New suite 4/4
  PASS; targeted existing-suite re-run 11/11 PASS, unchanged; `auditor.py`
  diff confirmed empty. Evidence: `docs/evidence/h04/H04_REGISTRY_REPAIR_REPORT.md`.
  PR #8 (`feat/h04-registry-repair`), opened, not merged.
- **Workload 4 (Spec Kit brownfield adoption): complete.** `specify-cli`
  v1.0.4 installed; `specify init --here --force --integration claude` run
  on `feat/h05-spec-kit-adoption`; diff confirmed additive-only
  (`.claude/skills/`, `.specify/`); constitution filled in per
  `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md`'s content plan, subordinated to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`. PR #9, opened, not
  merged.
- **Workload 5: not started**, per explicit instruction not to invent
  H0.5's scope. Remains blocked on Natalie's choice.
- **KARMO FOUNDATION v1: not declared complete this pass** — see
  `docs/project-state/CURRENT_STATE.md` for the exact remaining blocker
  (Workload 2's resolution) and the three paths offered to close it.
