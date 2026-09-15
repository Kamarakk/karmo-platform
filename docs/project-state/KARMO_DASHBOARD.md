# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core) — ✅ DEPLOYED TO KARMO-AI01
- Trusted Computer Worker System (Worker Runtime local service boundary) — ✅ DEPLOYED TO KARMO-AI01
- Direct remote network path to KARMO-AI01 over Tailscale — ✅ ACTIVE (`100.75.239.44`)
- Real Worker Runtime network transport / remote job execution — ✅ ENABLED (SSH stdio gateway; corrected 2026-09-15 — this line was stale since ~2026-09-13/14; see `CURRENT_STATE.md`'s reconciliation section for verification of all 5 previously-deferred security items, all now closed: cryptographic worker credential, subprocess env allowlisting, symlink-escape test, result-authenticity binding, durable Postgres-backed coordinator persistence)
- KARMO Access & Connection Registry — ✅ MERGED
- KARMO System Stewardship design — ✅ MERGED; workers not yet implemented/deployed
- Durable Memory Core integration (conversation/semantic/document recall in `chat`) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- KARMO PR #43 hardening (approval authority binding, model routing policy, recovery hardening) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- Keyword dispatch false-positive fix (PR #57) — ✅ DEPLOYED TO KARMO-AI01 (2026-09-15), canary-verified
- BloomBoss Historical Data Intelligence (Phase 1) — 🟡 reconciled against current `main` (PR #56); merge/promotion decision pending

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

Durable memory, PR #43's hardening, and the keyword false-positive fix
are all deployed and canary-verified on `karmo-ai01` as of 2026-09-15.
No outstanding documentation debt. The one open decision is BloomBoss
Phase 1 (PR #56, reconciled and tested, awaiting Kamara's
merge/promotion call) — see `NEXT_STEPS.md`. Otherwise, return focus to
useful KARMO capabilities instead of more infrastructure churn.

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
- Worker service boundary is production-deployed with real SSH-stdio Worker network transport enabled (corrected 2026-09-15) and bounded READ-only capability execution (`commander.system_snapshot`/`service_status`/`listener_snapshot`, `local_model_probe`) — still no arbitrary shell, no write/destructive capability, no inbound listener on either worker.
- Tailscale provides direct network reachability only; Tailscale SSH is not enabled.
- KVE02 remains the documented fallback remote path.
- Production access remains task-specific and approval-gated.

## CLOSED (2026-09-15 correction) — previously listed as deferred before real Worker network exposure

All 5 previously-named blockers were closed between roughly 2026-09-13 and
2026-09-14, verified present in code 2026-09-15: cryptographic worker
credential (`worker-runtime/app/crypto_boundary.py`), subprocess
environment allowlisting (fixed `env={...}` on every Commander subprocess
call), a dedicated symlink-escape test
(`worker-runtime/tests/test_runtime_file_security.py`,
`test_predeploy_security_hardening.py`), result-authenticity
cryptographic binding (`ResultAuthenticator`), and durable
Postgres-backed coordinator persistence (`PostgresWorkerCoordinatorStore`
— not in-memory). Real Worker network transport (SSH stdio gateway) is
now enabled and production-proven for Worker01/Worker02's Commander READ
path. This section previously listed these as still deferred; that was
stale.

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
