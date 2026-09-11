# Core v2 -> Worker Runtime Production Rollout

Status: **APPROVED FOR PRODUCTIONIZATION; HOST DEPLOYMENT NOT YET EXECUTED**

## High-level approval

Kamara approved production rollout in this order:

1. KARMO Control & Approval Layer (Core v2)
2. Trusted Computer Worker System (Worker Runtime v0.1)

## Production Access Authorization

Task: Core v2 first, then Worker Runtime production rollout

Target system/environment: KARMO-AI01 production

Purpose: deploy the KARMO Control & Approval Layer, verify it, then deploy the Trusted Computer Worker System behind that control layer.

Permitted operations:
- install application files, configuration, and service definitions required only for these two components;
- start/restart only the new Core/Worker services created for this rollout;
- perform one bounded post-deployment smoke/health verification for Core, then one for Worker.

Authority: WRITE, limited to the above operations.

Explicitly not authorized:
- database schema changes;
- Qdrant mutation;
- restart/modification of existing KARMO production services;
- deletes of existing production data/services;
- secret changes;
- new network exposure;
- real Worker Runtime network transport exposure;
- any action outside this rollout scope.

Granted: 2026-09-10 by Kamara

Expires: automatically when this rollout completes, fails, or is abandoned.

## Critical repository finding

`core-v2-prototypes/README.md` explicitly states that the current Core v2 tree is isolated prototype code and is **not wired into any existing KARMO application path**. Therefore the approved rollout does **not** mean copying prototype files directly into production.

Productionization must first turn the approved Core v2 design into a bounded real implementation with a stable service/application boundary and production-safe configuration. Direct deployment of the prototype directory is prohibited.

This is not a new approval request; it is the safe implementation path required to fulfill the already-approved rollout.

## Rollout gates

### Gate A — Core v2 productionization

Required before host deployment:
- define the exact production Core service/application boundary;
- reuse the verified Tool/Capability Registry, Approval Engine, Job/Event, configuration, and evidence concepts without silently changing their semantics;
- no database or Qdrant migration in this rollout;
- no network listener unless separately approved;
- configuration must not depend on an interactive shell;
- health state and failure reason must be observable;
- rollback must be file/service removal only and must leave existing KARMO services unchanged;
- targeted acceptance validation for the productionized integration boundary.

### Gate B — Core host deployment

After Gate A passes:
- capture pre-deployment file/service state for the new target paths only;
- install Core files/config/service;
- start only the new Core service;
- perform one smoke/health check;
- if smoke fails, disable/remove the new service/files and stop.

Worker deployment is prohibited until Core passes its smoke check.

### Gate C — Worker Runtime productionization review

Before Worker host deployment:
- confirm Worker Runtime uses Core approval/control boundaries rather than bypassing them;
- keep real worker network transport disabled;
- preserve the existing deferred network-exposure blockers (cryptographic worker credential, subprocess environment allowlist, symlink-escape test, result-authenticity cryptographic binding, coordinator persistence) as blockers for real network exposure, not blockers for a local/restricted worker service;
- define restricted local capability scope;
- define health/failure status and rollback.

### Gate D — Worker host deployment

After Gate C passes and Core is healthy:
- install Worker files/config/service;
- start only the new Worker service;
- perform one bounded smoke/health check;
- if smoke fails, disable/remove the Worker service/files without disturbing Core or existing KARMO services.

## Stop conditions

Stop before any production write if:
- the actual production execution model contradicts the repo record;
- the deployment requires database/Qdrant mutation;
- the deployment would require restarting an existing KARMO service;
- secrets would need to be exposed or reconfigured;
- real network transport/exposure is required;
- scope becomes ambiguous;
- rollback cannot remain isolated to the new Core/Worker components.

## Current execution state

- High-level rollout approval: **APPROVED**
- Production access authorization: **APPROVED**
- Core productionization branch: `feat/core-v2-productionization`
- Core host deployment: **NOT YET EXECUTED**
- Worker host deployment: **NOT YET EXECUTED**
- Existing production KARMO: **UNTOUCHED BY THIS ROLLOUT SO FAR**

## Operational principle

Build -> targeted validation -> deploy Core -> verify once -> deploy Worker -> verify once -> PROJECT SAVE.

Do not reopen broad architecture work unless a concrete productionization blocker requires it.
