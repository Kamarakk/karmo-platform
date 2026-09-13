# KARMO Master Index

Status tags used throughout this record set: **VERIFIED** (confirmed by committed repo evidence, a merged PR, or explicit operator attestation with concrete detail), **HISTORICAL** (was true, superseded or no longer the active state, kept for record), **NEEDS VERIFICATION** (stated but not independently confirmed by repo evidence or a read-only recheck).

This is the single index for KARMO's persistent project-record set. Do not create a competing set of these files elsewhere in the repository — update the files listed here.

## Record set

| File | Purpose |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | Detailed historical/current state record. **Important 2026-09-11 note:** it still contains older pre-rollout deployment wording; use `PROJECT_SAVE_2026-09-11_ACCESS_CORE_WORKER_ROLLOUT.md`, the refreshed dashboard, and inventories for the latest rollout delta until that large file is fully reconciled. |
| [KARMO_DASHBOARD.md](KARMO_DASHBOARD.md) | Human-facing Mission Control view of current stage, task, blocker, next gate, and near-term direction. |
| [CHANGE_LOG.md](CHANGE_LOG.md) | Chronological record of merged work and production actions. |
| [SOFTWARE_INVENTORY.md](SOFTWARE_INVENTORY.md) | Services/software installed or running, isolated vs. production. |
| [NETWORK_INVENTORY.md](NETWORK_INVENTORY.md) | Hosts, addresses, ports, and verified/fallback access paths. |
| [DASHBOARD_INVENTORY.md](DASHBOARD_INVENTORY.md) | Monitoring/dashboard surfaces. |
| [COMMAND_LOG.md](COMMAND_LOG.md) | Commands materially necessary to reproduce or undo hardening work. |
| [ROLLBACK_AND_REMOVAL.md](ROLLBACK_AND_REMOVAL.md) | Backup/rollback locations and procedures per phase. |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Outstanding/blocked items and next authorized action. |
| [PROJECT_SAVE_2026-09-11_ACCESS_CORE_WORKER_ROLLOUT.md](PROJECT_SAVE_2026-09-11_ACCESS_CORE_WORKER_ROLLOUT.md) | Latest durable delta for direct Tailscale enrollment, Core/Worker production deployment, PR #34/#35 merge, maintenance finding, and remaining verification. |
| [PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md](PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md) | Latest durable delta for the H0.1 isolated failure-matrix test-hardening/review checkpoint (not yet merged). |
| [PROJECT_SAVE_2026-09-12_PR41_POST_MERGE_WORKER_ACTIVATION.md](PROJECT_SAVE_2026-09-12_PR41_POST_MERGE_WORKER_ACTIVATION.md) | PR #41 post-merge checkpoint plus Worker01/Worker02 activation-track opening, verified AI01 health/network state, access finding, and activation sequence. |

## Learning program

- `docs/learning/KARMO_AI_ENGINEERING_APPRENTICESHIP.md` — active, flexible hands-on AI/agent engineering course built around the real KARMO architecture and practical project work.
- `docs/learning/KARMO_LEARNING_PROGRESS.md` — durable completion log. Every finished course section must be recorded here before moving on; course changes do not erase completed progress.

## Access & connection knowledge system

- `docs/access/README.md` — front door for access/routing/login work.
- `docs/access/HOST_ACCESS_REGISTRY.yaml` — machine-readable host identity, role, addresses, SSH context, and alternate-access metadata.
- `docs/access/AUTH_METHOD_REGISTRY.yaml` — machine-readable authentication/privilege method references; never stores secret values.
- `docs/access/CONNECTION_PATHS.yaml` — context-aware HOME/OFFICE/TRAVEL/AGENT route selection and fallback paths.
- `docs/access/ACCESS_RECOVERY.md` — routing → transport → SSH → authentication → authorization → application recovery order.
- `docs/operations/KARMO_REMOTE_ACCESS_RUNBOOK.md` — KVE02 jump-host procedure retained as fallback/recovery documentation.

Agents must resolve context and consult this access system before changing credentials or networking during a connectivity failure.

## Authoritative governance

- `AGENTS.md` — agent authority and boundaries.
- `CLAUDE.md` — Claude Code implementer instructions.
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` — I-01 through I-09 and production/project-save gates.
- `docs/governance/KARMO_SYSTEM_FIT_REVIEW.md` — mandatory whole-system fit + reuse review before meaningful new tools/services/workers/access paths/configuration.
- `docs/governance/KARMO_VALIDATION_LADDER.md` — reusable validation sequence.
- `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` — autonomous execution boundaries.
- `KARMO_DASHBOARD.md` — concise human-facing cockpit for the same record set, not a competing source of truth.

## Vision, architecture, and plans

- `docs/vision/KARMO_PRODUCT_VISION.md` — current/planned/future capabilities.
- `docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md` — architecture review against product vision.
- `docs/plans/KARMO_SYSTEM_STEWARDSHIP_PLAN.md` — approved direction for QA, Security, Reliability/Maintenance, Housekeeping/Data-Hygiene, and Agent Governance roles implemented over existing Core/Worker infrastructure rather than separate always-on daemons.
- `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` — foundation completion planning record.
- `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md` — Spec Kit brownfield plan.

## Phase evidence and handoff

- `docs/evidence/h01/`, `docs/evidence/h02/`, `docs/evidence/h04/` — committed isolated-acceptance evidence.
- `docs/evidence/h03/` — retained NO-PROMOTION research/evaluation evidence.
- `docs/handoff/h01/`, `docs/handoff/h02/`, `docs/handoff/h03/`, `docs/handoff/h04/` — captured production references and frozen design.

## Prior external knowledge base (pre-repo, HISTORICAL)

Per `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`, an earlier authoritative record lived outside this repository under `Karmo Knowledge Base/01_KARMO_HOME_LAB/`. Whether it is still maintained separately remains **NEEDS VERIFICATION**.

## Last reconciliation

- 2026-09-08 — H0.1–H0.4 reconciliation and foundation acceleration records.
- 2026-09-10 — Worker Runtime v0.1 source merge closeout and Mission Control dashboard.
- 2026-09-11 — remote-access runbook and KVE02 jump path recorded.
- 2026-09-11 — Access & Connection Registry, System-Fit & Reuse Review, and System Stewardship design merged.
- 2026-09-11 — KARMO-AI01 joined Tailscale at `100.75.239.44`; Core and restricted local Worker services deployed/active; PR #34 and #35 merged; detailed rollout saved in `PROJECT_SAVE_2026-09-11_ACCESS_CORE_WORKER_ROLLOUT.md`.
- 2026-09-11 — flexible KARMO AI Engineering Apprenticeship and durable learning-progress log created; completed sections must be recorded before advancing.
- 2026-09-12 — H0.1 isolated failure-matrix test suite hardened (three review findings fixed: clock-skew-sensitive latency check, weak duplicate-delivery coverage, environment-dependent fault injection); full matrix re-run 19 passed/2 skipped/0 failed; frozen `test/h01/app/` untouched; see `PROJECT_SAVE_2026-09-12_H01_TEST_HARDENING.md`.
- 2026-09-12 — PR #41 merged (`879b242c801f10fc141e68874847d9b9315dd304`); post-merge production read-only checkpoint passed, Worker01/Worker02 activation branch opened, and verified access/activation findings saved in `PROJECT_SAVE_2026-09-12_PR41_POST_MERGE_WORKER_ACTIVATION.md`.
