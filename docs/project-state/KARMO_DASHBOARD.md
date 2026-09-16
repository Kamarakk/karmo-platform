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
- BloomBoss Historical Data Intelligence — normalizes purchase, sales, listing, propagation, and Palmstreet staging history; preserves unknowns and provenance; validates contradictions; fingerprints raw evidence; and calculates reproducible business/quality metrics.
- KARMO-FIRST Orchestration — target control plane where KARMO owns durable task state, routing, capabilities, approvals, execution authority, verification evidence, and audit while ChatGPT/Claude/local/future models remain replaceable intelligence adapters.

## CURRENT TASK

Durable memory, PR #43's hardening, and the keyword false-positive fix
are all deployed and canary-verified on `karmo-ai01` as of 2026-09-15.
No outstanding documentation debt. The one open decision is BloomBoss
Phase 1 (PR #56, reconciled and tested, awaiting Kamara's
merge/promotion call) — see `NEXT_STEPS.md`. Otherwise, return focus to
useful KARMO capabilities instead of more infrastructure churn.

## CURRENT ISSUE

No active code blocker. KARMO-AI01, KVE01–03, and both workers are all
verified reachable and healthy as of the 2026-09-11–15 reconciliation
(`CURRENT_STATE.md`) — the Sept-11-era Remote Desktop Commander/Proxmox
reachability concern previously noted here is resolved.

Palmstreet's built-in order export was unreliable/unavailable as of the
Phase 1 build session; Seller Hub table evidence remains staged as a
fallback source pending re-verification, not the long-term primary
ingestion design.

## NEW GOVERNING RULE

**KARMO FIRST:** Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be sources, destinations, or adapters — not KARMO's brain, workflow engine, authority layer, or source of truth.

## NEXT GATE

1. Kamara's merge/promotion decision on BloomBoss Phase 1 (PR #56, now reconciled against current `main`).
2. Deploy PR #43's merged hardening to `karmo-ai01` (code merge only so far).
3. Choose the next KARMO capability track once the above are resolved.

## AFTER THIS

- Extend Palmstreet staging so all verified Seller Hub fields, including Buyer Note and Seller Note, are represented and tested without storing unnecessary customer PII in source control.
- Keep Palmstreet purchases and sales as structured platform evidence when possible; screenshots/invoices remain fallback evidence only.
- Continue BloomBoss reconciliation only when source evidence can be reliably mapped to canonical inventory without invented matches.
- Production remains separately approval-gated.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- Core is production-deployed, local-only, and has no network listener.
- Worker service boundary is production-deployed with real SSH-stdio Worker network transport enabled (corrected 2026-09-15) and bounded READ-only capability execution (`commander.system_snapshot`/`service_status`/`listener_snapshot`, `local_model_probe`) — still no arbitrary shell, no write/destructive capability, no inbound listener on either worker.
- Tailscale provides direct network reachability only; Tailscale SSH is not enabled.
- KVE02 remains the documented fallback remote path.
- Production access remains task-specific and approval-gated.
- BloomBoss (PR #32) remains isolated dev/GitHub scope only: no production DB implementation, no marketplace writes, no customer actions, no OBS, no deployment or merge until Kamara's separate high-level decision.

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

Keep it short. Historical detail belongs in `CHANGE_LOG.md`, `CURRENT_STATE.md`, and dated PROJECT SAVE files.

Last refreshed: 2026-09-15
