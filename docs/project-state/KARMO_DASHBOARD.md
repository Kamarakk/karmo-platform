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
- BloomBoss Historical Data Intelligence (Phase 1) — ✅ PR #32 BUILD GATE READY; DECISION-RANKING SLICE TARGETED CI GREEN; NOT MERGED OR DEPLOYED

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — protects event delivery across failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active versions and provenance.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — evaluated and intentionally not promoted to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — detects state mismatches across KARMO data systems.
- KARMO Control & Approval Layer (Core) — production control boundary for capability classes and approval requirements; local-only, no network listener.
- Trusted Computer Worker System (Worker service boundary) — production-local Worker shell bound to Core; no network listener, no real worker transport, no capability execution, no persistent writes.
- KARMO Access & Connection Registry — durable machine-readable host, route, authentication-reference, and recovery knowledge for humans and agents.
- KARMO System Stewardship — planned QA, Security, Reliability/Maintenance, Housekeeping/Data-Hygiene, and Agent-Governance roles implemented over existing Core/Worker architecture rather than separate infrastructure stacks.
- BloomBoss Historical Data Intelligence — normalizes purchase, sales, listing, propagation, and Palmstreet staging history; preserves unknowns and provenance; validates contradictions; fingerprints raw evidence; calculates reproducible business/quality metrics; buckets unsold inventory by deterministic historical age; and now emits deterministic decision rankings for the Phase 1 release questions without imputing unknown facts.

## CURRENT TASK

Hold PR #32 at the Phase 1 build gate for Kamara's separate high-level merge/promotion decision while continuing safe, Phase-1-scoped historical intelligence improvements in the isolated feature branch.

## CURRENT ISSUE

No active Phase 1 code blocker.

The prior mainline-divergence blocker was resolved by merge commit `d2519180a868f84a7da77d5cad9363ee992b5b84`, which incorporated `main` `53fb64f7f04ddd8c4377cf8b898db4b60714e4a2` while preserving BloomBoss Phase 1 changes.

The latest BloomBoss slice adds deterministic machine-readable rankings for: plants by realized profit on known cost, purchase batches by known loss cost, suppliers by known-outcome return, cultivars by average days to sale, and channels by known net profit. Unknown values are omitted from the corresponding ranking rather than treated as zero, and ties are deterministic.

GitHub Actions BloomBoss Phase 1 run #152 on code head `66ec331743864da81bddc75ebebcd54afb8a7c54` completed successfully using the targeted `tests/test_bloomboss_*.py` suite under Python 3.12.

Raw-source fingerprinting, reproducible inspection snapshots, row-specific import errors, completeness reporting, relationship validation, matched-cost gross margin, purchase-batch loss/outcome analytics, unit/cultivar/channel outcomes, deterministic inventory-exposure/aging analysis, historical listing evidence, propagation lineage, Palmstreet staging, Palmstreet staging-quality evidence, and decision rankings remain in Phase 1 scope.

## NEXT GATE

High-level merge/promotion decision for PR #32. The autonomous build instruction does **not** authorize merging the PR, deployment, production access, marketplace writes, or customer actions.

## AFTER THIS

- Use the real BloomBoss historical worksheet/export as the first source dataset in approved non-production scope.
- Use an official Palmstreet seller export to lock the staged field map before canonical reconciliation; buyer-side bulk purchase export support remains NEEDS VERIFICATION.
- Measure completeness, relationship findings, listing activity, inventory exposure/aging, realized return, known-outcome return, known net outcomes, and decision rankings before trusting supplier/cultivar/channel conclusions.
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
