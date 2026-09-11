# KARMO Master Index

Status tags used throughout this record set: **VERIFIED** (confirmed by
committed repo evidence, a merged PR, or explicit operator/Natalie
attestation with concrete detail), **HISTORICAL** (was true, superseded or
no longer the active state, kept for record), **NEEDS VERIFICATION**
(stated but not independently confirmed by repo evidence or a read-only
recheck).

This is the single index for KARMO's persistent project-record set. Do not
create a competing set of these files elsewhere in the repository — update
the files listed here.

## Record set

| File | Purpose |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | Snapshot of what is true right now across phases, production, and workflow decisions. |
| [KARMO_DASHBOARD.md](KARMO_DASHBOARD.md) | Human-facing Mission Control view of the current stage, task, blocker, next gate, and near-term direction; refreshed during meaningful PROJECT SAVE updates. |
| [CHANGE_LOG.md](CHANGE_LOG.md) | Chronological record of merged work and production actions. |
| [SOFTWARE_INVENTORY.md](SOFTWARE_INVENTORY.md) | Services/software installed or running, isolated vs. production. |
| [NETWORK_INVENTORY.md](NETWORK_INVENTORY.md) | Hosts, addresses, ports known for KARMO. |
| [DASHBOARD_INVENTORY.md](DASHBOARD_INVENTORY.md) | Monitoring/dashboard surfaces (currently none established). |
| [COMMAND_LOG.md](COMMAND_LOG.md) | Commands materially necessary to reproduce or undo H0.1–H0.4. |
| [ROLLBACK_AND_REMOVAL.md](ROLLBACK_AND_REMOVAL.md) | Backup/rollback locations and procedures per phase. |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Outstanding/blocked items and the next authorized action. |

## Authoritative governance (not duplicated here)

- `AGENTS.md` — agent authority and boundaries.
- `CLAUDE.md` — Claude Code implementer instructions.
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md` — I-01 through I-09,
  single source of truth for permanent engineering invariants; governs over
  this record set if the two ever disagree.
- `docs/governance/KARMO_VALIDATION_LADDER.md` — reusable 10-rung validation
  sequence for future workloads; operationalizes I-08, does not replace it.
- `docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` — defines what
  Claude may execute autonomously within an approved workload and where it
  must stop for Natalie.
- `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s **Mandatory Project
  Save Completion Rule** (added 2026-09-08, appended to that document, not
  a separate file) — no major session/phase/workload is complete until
  `docs/project-state/` is updated and durably committed (or explicitly
  marked PROJECT SAVE PENDING). Referenced, not duplicated, from `AGENTS.md`
  and `CLAUDE.md`. Extended the same day with a **ChatGPT Session
  Persistence** subsection (same rule, not a second rule): a ChatGPT
  planning-session handoff only counts as recorded once a repository-capable
  agent reconciles it against `docs/project-state/` and commits the result —
  ChatGPT conversation history itself is not the authoritative record.
- `KARMO_DASHBOARD.md` is the concise human-facing cockpit for that same
  record set, not a competing source of truth. During a meaningful PROJECT
  SAVE, refresh it whenever the current stage, current task, blocker/issue,
  next gate, or immediate post-task direction materially changes.

## Vision, architecture, and plans (not duplicated here)

- `docs/vision/KARMO_PRODUCT_VISION.md` — current capabilities, planned
  platform capabilities, and future (not-yet-approved) capability domains.
  Documenting a future capability there does not authorize building it.
- `docs/architecture/KARMO_EXTENSIBILITY_REVIEW.md` — review of H0.1–H0.4
  architecture against the product vision; no credible blocker found for
  any future domain, with forward design recommendations for what gets
  built next.
- `docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md` — the 5 remaining
  foundation workloads, each with its own scope, invariant impact,
  approval boundaries, and autonomy boundaries.
- `docs/plans/SPEC_KIT_BROWNFIELD_PLAN.md` — the prepared (not executed)
  Spec Kit initialization plan.

## Phase evidence and handoff (not duplicated here)

- `docs/evidence/h01/`, `docs/evidence/h02/`, `docs/evidence/h04/` —
  committed isolated-acceptance evidence.
- `docs/evidence/h03/` — **untracked in git as of 2026-09-08**; now includes
  `H03_EVALUATION_STATUS.md` documenting the NO-PROMOTION status and the
  exact file set recommended for commit under Foundation Completion
  Workload 1. See CURRENT_STATE.md conflict note.
- `docs/handoff/h01/`, `docs/handoff/h02/`, `docs/handoff/h03/`,
  `docs/handoff/h04/` — captured production references and frozen design.
  `docs/handoff/h01/frozen-design/` is **untracked in git** as of
  2026-09-08; see CURRENT_STATE.md conflict note.

## Prior external knowledge base (pre-repo, HISTORICAL)

Per `docs/handoff/h01/KARMO_HANDOFF_2026-09-04_H01_BUILD_COMPLETE.md`, an
earlier authoritative record lived outside this repository:
`Karmo Knowledge Base/01_KARMO_HOME_LAB/{CURRENT_STATE.md, MASTER_BUILD_LOG.md,
KARMO_FOUNDATION_HARDENING_PLAN.md}`. Those files are not present in this
repository and are not superseded by this record set automatically — flagged
**NEEDS VERIFICATION** whether they are still maintained separately or have
been fully retired in favor of this repo's records.

## Last reconciliation

2026-09-08 — full reconciliation against H0.1–H0.4 evidence, the H0.4
production cutover checkpoint, the legacy registry bootstrap stopping point,
and the Spec Kit evaluation decision. See CHANGE_LOG.md for detail.

2026-09-08 (same day, second pass) — foundation acceleration: product
vision, extensibility review, foundation completion plan (5 workloads),
validation ladder, autonomous execution contract, and Spec Kit brownfield
plan created; two of three repository-hygiene issues partially addressed
(migration comment corrected; H0.3 evidence given an explicit status note)
without committing anything. See CHANGE_LOG.md for detail.

2026-09-10 — Worker Runtime v0.1 source merge closeout completed and the
human-facing `KARMO_DASHBOARD.md` Mission Control view added to keep project
stage/task/gate orientation visible during long engineering sessions.
