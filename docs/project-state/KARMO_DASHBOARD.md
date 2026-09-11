# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation v1 — ✅ COMPLETE
- Core v2 prototypes — ✅ MERGED
- Worker Runtime v0.1 — ✅ SOURCE MERGE CLOSEOUT COMPLETE
- Production deployment of Worker Runtime — ⛔ NOT STARTED
- Real Worker Runtime network transport — ⛔ NOT ENABLED

## CURRENT TASK

Apply the KARMO workflow-visibility improvement so the current stage, task, blocker, next gate, and near-term direction stay visible while Kamara, ChatGPT, and Claude work.

## CURRENT ISSUE

No active Worker Runtime code blocker.

The problem being addressed now is workflow visibility: long implementation/debugging tasks can make the larger project stage easy to lose track of.

## NEXT GATE

Merge the Mission Control dashboard change, then use this dashboard as the pinned project-stage view during KARMO work.

## AFTER THIS

- KARMO AI / Agent Engineering Course — Day 1
- Continue applied Python + local-model learning
- Begin a directly useful capability, with BloomBoss as the leading practical candidate unless Kamara chooses another track
- Do not restart infrastructure-heavy engineering by default; open a new engineering track only by explicit decision

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- Worker Runtime v0.1 is merged in source only
- NOT deployed to production
- NOT connected to production KARMO
- No real network transport enabled
- Production access remains approval-gated

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These are deferred follow-ups, not active blockers for the merged isolated v0.1.

## SESSION STATUS FORMAT

For consequential KARMO work, ChatGPT should keep a compact orientation line near the top of the response when useful:

`KARMO │ <current stage> │ <current task> │ <step/gate> │ Next: <next action>`

Claude Code should use this dashboard as the human-facing stage snapshot when beginning or closing a substantial KARMO workload.

## PROJECT SAVE REFRESH RULE

Refresh this dashboard during every meaningful PROJECT SAVE whenever any of the following changes:

- current project stage
- current task
- active blocker/issue
- next approval or verification gate
- immediate post-task direction

Keep it short. Historical detail belongs in `CHANGE_LOG.md` and `CURRENT_STATE.md`, not here.

Last refreshed: 2026-09-10
