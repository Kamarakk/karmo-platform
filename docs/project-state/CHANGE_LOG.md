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

## Governance correction: Mandatory Production Access Authorization Gate (2026-09-08)

- **VERIFIED** — Natalie explicitly approved resolving the conflict the
  Workload 2 attempt surfaced: `CLAUDE.md` item 4 and `AGENTS.md`'s
  "Authority and boundaries" section both stated an unconditional,
  no-exception production-access prohibition, with no path for Natalie's
  own explicit, task-specific authorizations to apply.
- Added the Mandatory Production Access Authorization Gate to
  `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`: production access
  prohibited by default; lifted only by an explicit, task-specific,
  narrowly-bounded authorization (target system, purpose, permitted
  operations, read-only vs. write, applicable commands); read-only never
  implies write; higher-impact actions (writes, deployment, destructive
  actions, migrations, restarts, config changes, data repair, deletion)
  each need their own separate grant; single-task scope, auto-expires;
  defined mandatory STOP conditions; secrets never exposed or persisted;
  does not override any other invariant/gate; narrower rule always wins; a
  general workload approval never substitutes. Includes an
  authorization-record shape for durable tracking.
- `CLAUDE.md` item 4 and `AGENTS.md`'s equivalent bullet rewritten to
  reference the gate rather than restate an unconditional prohibition
  (`AGENTS.md` was not named in the request but carried the identical
  conflict in an even more absolute form, so was updated too — otherwise
  the conflict would only be partially resolved).
  `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` cross-referenced
  to the same gate, not restated.
- Invariant Impact Review performed before the change:
  `docs/evidence/governance/PRODUCTION_ACCESS_AUTHORIZATION_GATE_INVARIANT_IMPACT_REVIEW.md`.
- No production accessed; no Production Access Authorization issued or
  acted on by this task, per explicit instruction. Branch
  `governance/production-access-authorization-gate`, PR opened, **not
  merged**.
- Does not retroactively require re-justifying the already-accepted
  H0.1/H0.2/H0.4 production cutover history — governs future production
  access only.

## KARMO Foundation v1 closeout — DECLARED COMPLETE (2026-09-09)

- **VERIFIED** — Natalie granted a temporary, session-scoped, task-specific
  Production Access Authorization (target: `karmo-ai01`; read-only;
  purpose: Foundation v1 closeout) under the newly-adopted Mandatory
  Production Access Authorization Gate, and directed a full PR review/merge
  + Workload 2 execution + Foundation-completeness determination pass.
- PR #8 (Workload 3) merged: `06ab726`. PR #9 (Workload 4 / Spec Kit)
  merged: `cd72938`. PR #10 (PROJECT SAVE) merged: `87fd9cd`. PR #11
  (governance gate) auto-closed when its base branch (PR #10's) was
  deleted on merge; superseded by PR #12, identical content rebased onto
  `main`, merged: `e3443e8`.
- Workload 2 executed: H01-T01 (manifest presence/hash) PASS; H01-T18
  (baseline counts) PASS, every value either an exact match to the
  recorded pre-H0.1 baseline or a fully-explained delta traceable to an
  already-recorded event. No production write, restart, deployment, or
  configuration change was performed. Full detail:
  `docs/evidence/foundation-v1/PRODUCTION_READONLY_VERIFICATION.md`.
- Additional read-only check (beyond Workload 2's own defined scope, run
  as directly-relevant supporting evidence): the H0.4 report-only
  production auditor returned `INTEGRITY_FINDINGS_PRESENT` — 2
  `ORPHAN_VECTOR` (matching the already-documented ambiguous legacy
  hashes exactly, not new) and 3 `ACTIVE_STATE_MISMATCH` (a newly
  identified, non-blocking auditor-design gap in
  `reconciliation.check_active_version_state` for legacy-bootstrapped
  documents — underlying data correct and already fully accounted for by
  the existing legacy-bootstrap record). Recorded as a recommended future
  follow-up, not a new Foundation-completion criterion, per explicit
  instruction not to invent criteria after seeing results.
- Applying the Foundation Complete criterion already established
  2026-09-08 (Workload 1 merged + explicit Natalie decision on Workloads
  2/3), unmodified: **all criteria met.** Full closeout report and
  independent-verification evidence package committed at
  `docs/evidence/foundation-v1/` (`FOUNDATION_V1_CLOSEOUT_REPORT.md`,
  `PRODUCTION_READONLY_VERIFICATION.md`, `GIT_AND_PR_VERIFICATION.md`,
  `POST_CLOSEOUT_HEALTH.md`, `VERIFICATION_CHECKLIST.md`,
  `RUN_SUMMARY.json`, `MANIFEST.sha256`).
- H0.5/Workload 5 correctly not started — first post-foundation capability
  phase, Natalie's scope choice, not invented.
- **KARMO FOUNDATION v1 — COMPLETE.**

## KARMO Worker Runtime v0.1 — implemented, isolated prototype (2026-09-09)

- **VERIFIED (repo)** — Natalie authorized a 15-phase Large Autonomous
  Implementation Program to build KARMO's first real post-foundation
  capability: a distributed worker runtime. Branch
  `worker-runtime/implementation`, based on `core-v2/prototypes` (a
  disclosed, deliberate dependency — see
  `docs/evidence/worker-runtime/WORKER_RUNTIME_INVARIANT_IMPACT_REVIEW.md`).
- Built: worker registry (identity, heartbeat, lifecycle), resource
  discovery (real hardware facts for KARMO-DEV01, VERIFIED vs
  AVAILABLE-IN-PRINCIPLE labeled throughout), a closed capability manifest
  (9 SAFE capabilities, 9 permanently forbidden), a job protocol
  genuinely wiring the reused Tool Registry + Approval Engine prototypes
  together (closing an integration gap the prior session's adversarial
  review had flagged), an execution sandbox (handler-registry-only
  dispatch, path-traversal refusal, timeout, output cap, sanitized
  errors), a pull-based transport abstraction (`LocalTransport`,
  in-process; no inbound port anywhere), a coordinator, and a worker
  client — full pull cycle proven end-to-end.
- 44/44 tests passing, including all 24 explicitly required
  failure/adversarial scenarios. 4 real defects found and fixed while
  building the suite (see CURRENT_STATE.md's Worker Runtime section for
  the list); one of them required a fix to the shared, reused
  `core-v2-prototypes/job_model/jobs.py` state machine (missing
  `WAITING_FOR_APPROVAL → FAILED` transition) — core-v2-prototypes'
  regression suite reconfirmed 161/161 after the fix.
- M3 acceleration benchmark run (bounded, local only, no production
  comparison): `docs/evidence/worker-runtime/BENCHMARK_RESULTS.json`.
- Adversarial security review with 5 explicitly named, unresolved open
  gaps (not fixed this workload, not hidden):
  `docs/evidence/worker-runtime/SECURITY_REVIEW.md`.
- Future network integration (Tailscale transport, worker credentials,
  TLS, coordinator auth) designed but explicitly **not implemented, not
  deployed** — `docs/architecture/KARMO_WORKER_RUNTIME_NETWORK_PLAN.md`.
- Full evidence package: `docs/evidence/worker-runtime/`
  (`WORKER_RUNTIME_REPORT.md`, `SECURITY_REVIEW.md`, `TEST_RESULTS.txt`,
  `BENCHMARK_RESULTS.json`, `VERIFICATION_CHECKLIST.md`,
  `RUN_SUMMARY.json`, `MANIFEST.sha256`).
- **Production access: 0. Network/firewall/Tailscale changes: 0. Merges:
  0.** Worker Runtime v0.1 is not connected to production KARMO and no PR
  from this workload was merged.

## KARMO Worker Runtime v0.1 — independent-verification fixes (2026-09-09, same day, before any merge)

- **VERIFIED (repo)** — an independent (ChatGPT) verification pass of PRs
  #23–#25 found 4 real blocking findings this workload's own review had
  missed, and Natalie directed that PRs #23–#25 not be merged until they
  were fixed and re-verified. Work was confined to the existing Worker
  Runtime branches and the synthetic/local KARMO-DEV01 environment — no
  production access, no network changes, no new PRs.
- **Finding 1 — approval gated job completion, not execution.** A
  worker's sandboxed capability handler ran unconditionally the moment a
  job was leased; approval state was checked only afterward, at
  `complete()`. Fixed: `job_protocol.WorkerJobQueue.execute()` is now the
  sole path to invoking a capability's action; for any
  `authority_requirement != NONE`, the action only runs from inside the
  reused `ApprovalEngine.execute()` (never duplicated), which validates
  approval state, executor identity, expiry, and an exact arguments
  digest, then atomically consumes the approval into `EXECUTED`.
  `complete()` now requires `EXECUTED` (was `APPROVED`) as defense in
  depth. Wired through `transport.execute()` into `worker_client.py`. 10
  new tests cover exactly the 6 required adversarial cases (unapproved,
  expired, changed payload, wrong executor, double-execution, successful
  EXECUTED outcome) plus 4 more.
- **Finding 2 — timeout enforcement was a post-return check, not a real
  deadline.** Fixed: `sandbox.run_capability()` now runs each handler in
  a forked child process under a hard deadline; on overrun the child is
  terminated (SIGTERM then SIGKILL) and the call fails closed. A real
  multiprocessing deadlock was found and fixed while building this fix's
  own test: waiting via `process.join(timeout)` before draining the
  result pipe hangs whenever a handler's result exceeds the pipe's
  kernel buffer (~64KB) — fixed by waiting on the connection
  (`parent_conn.poll(timeout)`) as the primary deadline gate instead.
- **Finding 3 — only `stdout_summary` was bounded, not the full result.**
  Fixed: new `MAX_RESULT_BYTES` (64KB, refuses rather than truncates a
  structured dict) and `MAX_EVIDENCE_FILES` (20) bound the complete
  returned result.
- **Finding 4 — a worker heartbeat could set coordinator-owned
  scheduling state directly**, letting a worker force itself `AVAILABLE`
  while actually `BUSY` on a live lease (enabling a double-lease), or the
  reverse. Fixed: `WorkerRegistry.heartbeat()` now accepts only an
  optional self-reported `WorkerHealth` (HEALTHY/DEGRADED), never a raw
  `WorkerStatus`; `BUSY` is untouchable by a worker's own heartbeat in
  either direction.
- 18 new adversarial tests added; **worker-runtime suite now 62/62
  passing** (was 44/44); core-v2-prototypes regression reconfirmed
  161/161, unaffected. All fixes and new tests verified via a fresh full
  run, not merely re-read from prior output.
- Documentation updated to match: `SECURITY_REVIEW.md` (2 new threat rows,
  updated rows 20), `WORKER_RUNTIME_INVARIANT_IMPACT_REVIEW.md` (I-09
  corrective note), `KARMO_WORKER_RUNTIME_NETWORK_PLAN.md` (new section
  flagging that `execute()`'s callable shape cannot cross a real network
  boundary as designed — a future execution-ticket redesign is needed
  before Phase 15 can be implemented), `WORKER_RUNTIME_REPORT.md`,
  `RUN_SUMMARY.json`, `TEST_RESULTS.txt`, `BENCHMARK_RESULTS.json`
  (re-run), `VERIFICATION_CHECKLIST.md` (new command 11),
  `MANIFEST.sha256` (regenerated).
- PR #23 updated at commit `5906f61`. PR #24 updated at commit `8533642`.
  PR #25 updated at this entry's accompanying commit (see this file's own
  commit hash). **No new PRs opened. No merge.**
- **Blockers: None** — but only as of this fix round; the four findings
  above were genuine blockers until fixed and re-tested. PRs #23–#25
  remain open and unmerged, awaiting re-verification.
