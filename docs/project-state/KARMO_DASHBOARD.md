# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core) — ✅ DEPLOYED TO KARMO-AI01
- Trusted Computer Worker System (Worker Runtime local service boundary) — ✅ DEPLOYED TO KARMO-AI01
- Direct remote network path to KARMO-AI01 over Tailscale — ✅ ENROLLED; direct client SSH smoke still needs verification
- Real Worker Runtime network transport / remote job execution — ⛔ NOT ENABLED
- KARMO Access & Connection Registry — ✅ MERGED
- KARMO System Stewardship design — ✅ MERGED; workers not yet implemented/deployed
- BloomBoss Historical Data Intelligence (Phase 1) — ✅ PR #32 BUILD GATE READY; NOT MERGED OR DEPLOYED
- KARMO-FIRST Orchestration Direction — 🟡 ARCHITECTURE LOCKED IN PRINCIPLE; implementation scaffold pending

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

Preserve BloomBoss Phase 1 at its existing gate while designing the next KARMO control-plane slice around:

`KARMO Orchestration Layer -> Model Router -> Common KARMO Capability Interface -> Core Approval -> Worker Execution -> Independent Verification -> Durable Memory/Audit`

At the same time, recover and verify the original three-node KVE compute design before assigning distributed roles or recommending new hardware.

## CURRENT ISSUE

No active BloomBoss code blocker.

The immediate infrastructure blocker is management-path verification: Remote Desktop Commander currently knows only `karmo-ai01`, which was observed offline during this session; KVE01/KVE03 were separately shown reachable by SSH from KARMO-DEV01, while KVE02's LAN target is user-supplied and still needs live verification.

Palmstreet's built-in order export is currently unreliable/unavailable in the observed account/session even for a one-day range. Seller Hub table evidence is therefore staged as a fallback source, not as the long-term primary ingestion design.

## NEW GOVERNING RULE

**KARMO FIRST:** Before recommending an app, SaaS product, manual export, cloud folder, phone shortcut, or third-party workflow, first determine whether KARMO can own the capability using infrastructure already available.

External systems should be sources, destinations, or adapters — not KARMO's brain, workflow engine, authority layer, or source of truth.

## NEXT GATE

Before any distributed deployment or Proxmox changes:

1. Restore/verify KARMO-AI01 management availability.
2. Perform read-only reachability checks from KARMO-controlled infrastructure to KVE01/KVE02/KVE03.
3. Verify hostnames, cluster state, and real hardware capacity.
4. Persist that truth in KARMO records.
5. Only then assign workload roles and decide whether hardware upgrades are justified.

## AFTER THIS

- Scaffold orchestration task/job state, model-provider abstraction, common capability registry, approval/risk contract, Worker job contract, verification-result contract, and audit/event format in non-production scope.
- Extend Palmstreet staging so all verified Seller Hub fields, including Buyer Note and Seller Note, are represented and tested without storing unnecessary customer PII in source control.
- Keep Palmstreet purchases and sales as structured platform evidence when possible; screenshots/invoices remain fallback evidence only.
- Continue BloomBoss reconciliation only when source evidence can be reliably mapped to canonical inventory without invented matches.
- Production remains separately approval-gated.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- PR #32 / `feat/bloomboss-historical-intelligence` remains isolated from production
- GitHub/dev scope only for current architecture/scaffolding work
- No marketplace writes or customer actions
- No OBS
- No BloomBoss deployment or merge
- No secrets
- No Proxmox cluster/network/configuration changes until live state is verified
- No new daemon/model service installation merely for convenience

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These remain blockers for real Worker network exposure.

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

Last refreshed: 2026-09-11
