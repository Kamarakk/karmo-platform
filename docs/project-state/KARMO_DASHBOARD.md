# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core) — ✅ DEPLOYED TO KARMO-AI01
- Trusted Computer Worker System (Worker Runtime local service boundary) — ✅ DEPLOYED TO KARMO-AI01
- Direct remote network path to KARMO-AI01 over Tailscale — ✅ ACTIVE (`100.75.239.44`)
- Real Worker Runtime network transport / remote job execution — ⛔ NOT ENABLED
- KARMO Access & Connection Registry — ✅ MERGED
- KARMO System Stewardship design — ✅ MERGED; workers not yet implemented/deployed
- Durable Memory Core integration (conversation/semantic/document recall in `chat`) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — protects event delivery across failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active versions and provenance.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — evaluated and intentionally not promoted to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — detects state mismatches across KARMO data systems.
- KARMO Control & Approval Layer (Core) — production control boundary for capability classes and approval requirements; local-only, no network listener.
- Trusted Computer Worker System (Worker service boundary) — production-local Worker shell bound to Core; no network listener, no real worker transport, no capability execution, no persistent writes.
- KARMO Access & Connection Registry — durable machine-readable host, route, authentication-reference, and recovery knowledge for humans and agents.
- KARMO System Stewardship — planned QA, Security, Reliability/Maintenance, Housekeeping/Data-Hygiene, and Agent-Governance roles implemented over existing Core/Worker architecture rather than separate infrastructure stacks.

## CURRENT TASK

Durable Memory Core integration is deployed and canary-verified
(2026-09-15). The full 2026-09-11–15 reconciliation into
`CURRENT_STATE.md`'s narrative is now done — no outstanding
documentation debt from that period. Open decisions (PR #43 staged
hardening work, PR #32 BloomBoss, choice of next capability) are listed
in `NEXT_STEPS.md`. Otherwise, return focus to useful KARMO capabilities
instead of more infrastructure churn.

## CURRENT ISSUE

No active Core/Worker deployment blocker.

One host-maintenance item is pending: Ubuntu installed kernel `6.8.0-139-generic` while KARMO-AI01 is currently running `6.8.0-138-generic`. A planned reboot is needed later to load the new kernel; no reboot was performed during this rollout.

Direct OpenSSH over KARMO-AI01's new Tailscale address from KARMO-DEV01 remains a client-side verification item. The tailnet enrollment itself is verified and KARMO-AI01 is visible at `100.75.239.44`.

## NEXT GATE

At the next convenient maintenance window:

1. verify direct `ssh lofason@100.75.239.44` from KARMO-DEV01;
2. schedule one controlled KARMO-AI01 reboot for the pending kernel update;
3. after reboot, verify Tailscale, Core, Worker, and existing KARMO services once.

These are maintenance/verification actions, not a reason to reopen architecture work.

## AFTER THIS

- Resume useful capability work, with BloomBoss still the leading practical domain unless Kamara chooses another track.
- Use the new System-Fit & Reuse Review before adding new tools/services.
- Build stewardship roles by reusing Core/Worker rather than creating separate daemons or platforms.
- Keep real Worker network exposure deferred until the previously recorded security blockers are addressed.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- Core is production-deployed, local-only, and has no network listener.
- Worker service boundary is production-deployed, local-only, and has no real Worker network transport or capability execution enabled.
- Tailscale provides direct network reachability only; Tailscale SSH is not enabled.
- KVE02 remains the documented fallback remote path.
- Production access remains task-specific and approval-gated.

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These are blockers for real Worker network exposure, not for the currently deployed local-only Worker boundary.

## SESSION STATUS FORMAT

For consequential KARMO work, ChatGPT should keep a compact orientation line near the top of the response when useful:

`KARMO │ <plain-English current stage> (<technical name>) │ <current task> │ <step/gate> │ Next: <next action>`

Plain-English purpose comes first. Engineering names remain in parentheses so Kamara can learn the real terminology without losing context.

## PROJECT SAVE REFRESH RULE

Refresh this dashboard during every meaningful PROJECT SAVE whenever any of the following changes:

- current project stage
- current task
- active blocker/issue
- next approval or verification gate
- immediate post-task direction

Keep it short. Historical detail belongs in `CHANGE_LOG.md` and `CURRENT_STATE.md`, not here.

Last refreshed: 2026-09-15
