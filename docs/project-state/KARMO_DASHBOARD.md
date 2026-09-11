# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core v2 prototypes) — ✅ MERGED
- Trusted Computer Worker System (Worker Runtime v0.1) — ✅ SOURCE MERGE CLOSEOUT COMPLETE
- Production deployment of the Trusted Computer Worker System — ⛔ NOT STARTED
- Real network connection for trusted worker computers (Worker Runtime network transport) — ⛔ NOT ENABLED

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — makes sure important KARMO events are delivered reliably instead of being lost during failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active document versions, lifecycle state, and provenance so old versions are not treated as current.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — combines semantic/vector search with keyword-style search. Evaluated, but intentionally NOT deployed to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — compares expected KARMO state with database/vector-store state and reports mismatches.
- KARMO Control & Approval Layer (Core v2 prototypes) — defines tool permissions, approval rules, jobs, configuration patterns, and execution evidence.
- Trusted Computer Worker System (Worker Runtime v0.1) — lets approved computers such as KARMO-DEV01 register, advertise safe capabilities, pull bounded jobs, execute them in a sandbox, and return results/evidence.
- Real Worker Network Connection (Worker Runtime network transport) — future networking that would connect trusted worker computers to live KARMO. Not enabled yet.

## CURRENT TASK

Make KARMO project naming easier to understand by showing the plain-English purpose first and the engineering name in parentheses.

## CURRENT ISSUE

No active Worker Runtime code blocker.

The current usability issue is terminology: technical phase and component names such as H0.3 or Worker Runtime v0.1 do not immediately explain what the system does.

## NEXT GATE

Merge this plain-English dashboard-label update, then keep using plain-English names first in active KARMO work while retaining technical names in parentheses for traceability.

## AFTER THIS

- KARMO AI / Agent Engineering Course — Day 1
- Continue applied Python + local-model learning
- Review live production services before any new production deployment
- Begin a directly useful capability, with BloomBoss as the leading practical candidate unless Kamara chooses another track
- Do not restart infrastructure-heavy engineering by default; open a new engineering track only by explicit decision

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- Trusted Computer Worker System (Worker Runtime v0.1) is merged in source only
- NOT deployed to production
- NOT connected to production KARMO
- No real worker network connection enabled
- Production access remains approval-gated

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These are deferred follow-ups, not active blockers for the merged isolated Trusted Computer Worker System (Worker Runtime v0.1).

## SESSION STATUS FORMAT

For consequential KARMO work, ChatGPT should keep a compact orientation line near the top of the response when useful:

`KARMO │ <plain-English current stage> (<technical name>) │ <current task> │ <step/gate> │ Next: <next action>`

Plain-English purpose comes first. Engineering names remain in parentheses so Kamara can learn the real terminology without losing context.

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
