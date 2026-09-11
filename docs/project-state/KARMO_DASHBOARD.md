# KARMO Mission Control

Human-friendly working dashboard for keeping the active project stage visible during long engineering sessions.

`CURRENT_STATE.md` remains the authoritative detailed state record. This file is a concise cockpit view and must not contradict it.

## KARMO CURRENT STAGE

- Foundation & Reliability Layer (Foundation v1) — ✅ COMPLETE
- KARMO Control & Approval Layer (Core v2 prototypes) — ✅ MERGED
- Trusted Computer Worker System (Worker Runtime v0.1) — ✅ SOURCE MERGE CLOSEOUT COMPLETE
- BloomBoss Historical Data Intelligence (Phase 1) — 🟡 PR #32 BUILD GATE READY; NOT MERGED OR DEPLOYED
- Production deployment of Core/Worker/BloomBoss — ⛔ NOT PART OF THIS BLOOMBOSS WORKLOAD
- Real Worker Runtime network transport — ⛔ NOT ENABLED

## WHAT THE MAJOR KARMO SYSTEMS ACTUALLY DO

- Reliable Event Delivery (H0.1 Transactional Outbox) — makes sure important KARMO events are delivered reliably instead of being lost during failures.
- Document Memory & Versioning (H0.2 Knowledge Lifecycle) — manages active document versions, lifecycle state, and provenance so old versions are not treated as current.
- Experimental Hybrid Search (H0.3 Hybrid Retrieval) — combines semantic/vector search with keyword-style search. Evaluated, but intentionally NOT deployed to production.
- Integrity & Consistency Checker (H0.4 Integrity/Reconciliation) — compares expected KARMO state with database/vector-store state and reports mismatches.
- KARMO Control & Approval Layer (Core v2 prototypes) — defines tool permissions, approval rules, jobs, configuration patterns, and execution evidence.
- Trusted Computer Worker System (Worker Runtime v0.1) — lets approved computers register, advertise safe capabilities, pull bounded jobs, execute them in a sandbox, and return results/evidence.
- BloomBoss Historical Data Intelligence — normalizes BloomBoss purchase/sales/listing history, preserves unknowns and provenance, validates contradictions, fingerprints raw evidence, and calculates reproducible business/quality metrics.

## CURRENT TASK

Close the first BloomBoss Historical Data Intelligence build gate on PR #32 without crossing the merge/deployment approval boundary.

## CURRENT ISSUE

No active Phase 1 code blocker. The latest realized-return implementation/test commit `7b69483102e9f07cf829e35d90b07b91d6ff223b` passed GitHub Actions run #91 using the automatic targeted BloomBoss suite.

Raw-source fingerprinting, reproducible inspection snapshots, row-specific import errors, completeness reporting, relationship validation, matched-cost gross margin, purchase-batch loss/outcome analytics, cultivar/channel outcomes, deterministic inventory-exposure analysis, and historical listing evidence are present.

Supplier and purchase-batch intelligence now separates **gross margin** from **return on known cost** and adds a stricter **known-outcome return** that subtracts explicitly known plant-loss cost. This prevents profitable surviving units from hiding known supplier/batch losses. Unknown cost remains unknown, and active unsold inventory remains capital exposure rather than being mislabeled as a realized loss.

Supplier summaries now also expose average days-to-sale when dates are known, allowing later comparison of return and capital velocity without inventing dates.

Known purchase-quantity reconstruction gaps are reported without inventing missing units or converting incomplete reconstruction into assumed plant loss.

Listing validation reports broken inventory references, listings dated before known acquisition, and listings dated after a known sale without repairing or inventing missing facts.

Historical listing-activity analytics report listing volume, unique units listed, known asking-price averages, and completed listing durations overall and by channel. They intentionally do not infer that an unlisting was a sale or guess a realized sale/listing relationship.

Inventory exposure identifies active unsold units, known capital tied up, unknown-cost exposure, and days held measured to the latest date represented in the historical source rather than today's date.

## NEXT GATE

High-level approval to merge PR #32 when Kamara chooses to promote this Phase 1 slice. Merge is not authorized by the autonomous build instruction.

## AFTER THIS

- Use the real BloomBoss historical worksheet/export as the first source dataset in approved non-production scope.
- Measure field completeness, relationship findings, listing-history contradictions, listing activity, inventory exposure, realized return, and known-outcome return before trusting supplier/purchase conclusions.
- Use loss-aware batch/supplier results to identify purchases that actually destroyed or retained capital instead of ranking only successful survivors.
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
