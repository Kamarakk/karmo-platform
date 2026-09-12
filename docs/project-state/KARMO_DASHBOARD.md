# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core v2 prototypes) — ✅ MERGED
- Trusted Computer Worker System (Worker Runtime v0.1) — ✅ SOURCE MERGE CLOSEOUT COMPLETE
- BloomBoss Historical Data Intelligence (Phase 1) — 🟠 PR #32 CODE GREEN, MERGE GATE SUSPENDED PENDING MAIN RESYNC; NOT MERGED OR DEPLOYED
- Production deployment of the Trusted Computer Worker System — ⛔ NOT STARTED
- Real network connection for trusted worker computers (Worker Runtime network transport) — ⛔ NOT ENABLED

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — makes sure important KARMO events are delivered reliably instead of being lost during failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active document versions, lifecycle state, and provenance so old versions are not treated as current.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — combines semantic/vector search with keyword-style search. Evaluated, but intentionally NOT deployed to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — compares expected KARMO state with database/vector-store state and reports mismatches.
- KARMO Control & Approval Layer (Core v2 prototypes) — defines tool permissions, approval rules, jobs, configuration patterns, and execution evidence.
- Trusted Computer Worker System (Worker Runtime v0.1) — lets approved computers register, advertise safe capabilities, pull bounded jobs, execute them in a sandbox, and return results/evidence.
- BloomBoss Historical Data Intelligence — normalizes purchase, sales, and listing history; preserves unknowns and provenance; validates contradictions; fingerprints raw evidence; and calculates reproducible business/quality metrics.

## CURRENT TASK

Keep improving the approved BloomBoss Historical Data Intelligence slice on PR #32 while preserving the merge/deployment approval boundary, then resynchronize with current `main` before reopening the merge gate.

## CURRENT ISSUE

No active Phase 1 code blocker. The latest fee-aware outcome analytics passed BloomBoss Phase 1 GitHub Actions run #105 at commit `187350b310cb4f1d325058e665d879f161782879`.

The branch has diverged from current `main`: GitHub comparison on 2026-09-11 reports PR #32 **23 commits behind** and 91 commits ahead. Therefore the prior BUILD GATE READY claim is suspended until a fresh non-production resynchronization is completed and the targeted BloomBoss suite passes again.

Raw-source fingerprinting, reproducible inspection snapshots, row-specific import errors, completeness reporting, relationship validation, matched-cost gross margin, purchase-batch loss/outcome analytics, unit/cultivar/channel outcomes, deterministic inventory-exposure analysis, and historical listing evidence remain on the feature branch.

Cultivar and channel intelligence now also reports **known net revenue, known net profit, and known net margin only when landed cost, selling fees, and shipping cost are all known**. Missing fee/shipping facts remain unknown rather than being treated as zero.

Supplier and purchase-batch intelligence continues to separate gross margin from return on known cost and adds known-outcome return that subtracts explicitly known plant-loss cost. Unknown cost remains unknown, and active unsold inventory remains capital exposure rather than realized loss.

## NEXT GATE

Resynchronize `feat/bloomboss-historical-intelligence` with current `main` in approved non-production GitHub/dev scope, resolve only real conflicts, rerun the targeted BloomBoss suite, and refresh build-gate evidence. High-level merge approval remains separate and is not authorized by the autonomous build instruction.

## AFTER THIS

- Use the real BloomBoss historical worksheet/export as the first source dataset in approved non-production scope.
- Measure completeness, relationship findings, listing activity, inventory exposure, realized return, known-outcome return, and known net outcomes before trusting supplier/cultivar/channel conclusions.
- Implement durable local/dev persistence only after the persistence design is reviewed at the next approved build slice.
- Continue the approved BloomBoss phase order; do not start marketplace write automation or external customer actions.
- Production remains separately approval-gated.

## ACTIVE SAFETY / AUTHORITY BOUNDARY

- PR #32 / `feat/bloomboss-historical-intelligence` only
- GitHub/dev scope only
- Production KARMO untouched
- No marketplace writes or customer actions
- No OBS
- No deployment or merge
- No secrets

## DEFERRED BEFORE ANY REAL WORKER NETWORK EXPOSURE

1. Cryptographic worker credential
2. Subprocess environment allowlisting
3. Dedicated symlink-escape test
4. Result-authenticity cryptographic binding
5. Coordinator persistence

These remain separate from BloomBoss Phase 1 and are not blockers for the isolated historical-data build.

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
