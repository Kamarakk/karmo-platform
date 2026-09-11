# PROJECT SAVE — Core Control Layer → Worker Runtime

Saved: 2026-09-11
Branch: `feat/core-v2-productionization`
PR: #33 — `feat: productionize Core v2 for approved rollout`

## Authorized rollout

Kamara approved the production rollout in this order:
1. KARMO Control & Approval Layer (Core v2)
2. Trusted Computer Worker System (Worker Runtime v0.1)

Production target: KARMO-AI01.
Authorized writes remain limited to new Core/Worker application files, configuration, and service definitions; starting/restarting only the new Core/Worker services; and one bounded smoke/health check after each component.

Not authorized: database schema changes, Qdrant mutation, modification/restart of existing KARMO production services, deletion of existing production state, secret changes, new network exposure, or real Worker Runtime network transport.

## Work completed this session

- Resumed PR #33 and re-read the rollout plan and Gate A evidence.
- Confirmed the existing `core-v2-prototypes/` tree is design/prototype evidence and must not be copied directly into production.
- Consolidated the rollout branch to one canonical production Core implementation under `core-service/`.
- Removed the competing duplicate `core-runtime/` implementation and its duplicate service/test files.
- Kept the production boundary local-only and inert with respect to external systems: no network listener, no PostgreSQL/Qdrant writes, no secrets, and no real worker transport.
- Updated Gate A evidence to reflect the canonical `core-service/` path and planned `/opt/karmo/core-service` production target.
- Remote Desktop Commander plugin was connected in ChatGPT, but no device was registered yet.

## Production host attempt / blocker

On KARMO-AI01, the Remote Desktop Commander setup command reached npm but failed because the server currently has:

- Node.js `v18.19.1`
- npm `9.2.0`

The current Remote Desktop Commander dependency chain requires newer Node versions (several packages require Node 20 or Node 22+). The attempt ended with `ERR_REQUIRE_ESM` from the temporary npx dependency tree.

This is a setup-tool/runtime compatibility issue, not a KARMO Core failure.

No Core or Worker production deployment was performed.
No existing KARMO production service was restarted or modified.
No database or Qdrant mutation occurred.

## Current stopping point

Gate A remains incomplete only because the live host preflight still needs to be performed before the first production write.

Required host checks remain:
- actual KARMO-AI01 Python path/version;
- target directory permissions for `/opt/karmo/core-service`;
- systemd availability/execution model;
- confirmation that `/opt/karmo/core-service` and `karmo-core.service` do not collide with existing production paths/services.

Worker Runtime remains blocked from deployment until Core passes its production smoke check.

## Next action

Do not rerun the failed Remote Desktop Commander installer under Node 18.

Next session, choose one safe path:
1. explicitly approve a user-local Node 22 installation for `lofason` solely to run Remote Desktop Commander without replacing production system Node; or
2. perform the bounded KARMO-AI01 host preflight manually over SSH under the already-approved Core/Worker production authorization.

After host preflight passes: install Core only → start new Core service only → one smoke check → if healthy, proceed to Worker productionization/deployment review.

## Safety status at save

- Production Core: NOT DEPLOYED
- Production Worker: NOT DEPLOYED
- Existing KARMO production: UNCHANGED by this rollout
- PR #33: ACTIVE
- BloomBoss background work: separate workstream
