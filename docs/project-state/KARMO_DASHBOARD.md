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
- BloomBoss Historical Data Intelligence (Phase 1) — 🟠 PR #32 RESYNCHRONIZED WITH CURRENT `main`; FRESH TARGETED CI REQUIRED BEFORE BUILD GATE REOPENS; NOT MERGED OR DEPLOYED

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

## CURRENT TASK

Validate the approved BloomBoss Historical Data Intelligence slice on PR #32 after resynchronizing its feature branch with current `main`, while preserving the separate merge/deployment approval boundary.

## CURRENT ISSUE

No active Phase 1 implementation blocker. Before resynchronization, BloomBoss Phase 1 GitHub Actions run #129 passed successfully at commit `f90e6d53dfcd9d5262022d9a5d2dbde0451b8f10`, covering Palmstreet staging completeness. The branch head then received a documentation-only PROJECT SAVE commit.

The previous divergence blocker is resolved in branch history by a non-production merge commit that preserves current `main` state plus the BloomBoss feature changes. A fresh targeted BloomBoss CI run on the synchronized head is required before the build gate can be declared READY again.

Raw-source fingerprinting, reproducible inspection snapshots, row-specific import errors, completeness reporting, relationship validation, matched-cost gross margin, purchase-batch loss/outcome analytics, unit/cultivar/channel outcomes, deterministic inventory-exposure analysis, historical listing evidence, propagation lineage, Palmstreet staging, and Palmstreet staging-quality evidence remain in Phase 1 scope.

## NEXT GATE

Require a successful fresh BloomBoss Phase 1 GitHub Actions run on the synchronized PR #32 head. If it passes and GitHub reports the branch mergeable, reopen the Phase 1 BUILD GATE for Kamara's separate high-level merge/promotion decision. No merge is authorized by the autonomous build instruction.

## AFTER THIS

- Use the real BloomBoss historical worksheet/export as the first source dataset in approved non-production scope.
- Use an official Palmstreet seller export to lock the staged field map before canonical reconciliation; buyer-side bulk purchase export support remains NEEDS VERIFICATION.
- Measure completeness, relationship findings, listing activity, inventory exposure, realized return, known-outcome return, and known net outcomes before trusting supplier/cultivar/channel conclusions.
- Implement durable local/dev persistence only after the persistence design is reviewed at the next approved build slice.
- Continue the approved BloomBoss phase order; do not start marketplace write automation or external customer actions.
- Production remains separately approval-gated.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- PR #32 / `feat/bloomboss-historical-intelligence` only
- GitHub/dev scope only for BloomBoss build work
- Production KARMO untouched by BloomBoss work
- No marketplace writes or customer actions
- No OBS
- No BloomBoss deployment or merge
- No secrets

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These are blockers for real Worker network exposure, not for the isolated BloomBoss historical-data build.

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

Last refreshed: 2026-09-11
