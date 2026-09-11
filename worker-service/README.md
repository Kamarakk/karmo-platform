# KARMO Worker Service

Production-safe boundary for the Trusted Computer Worker System (Worker Runtime v0.1).

This package does **not** deploy the existing `worker-runtime/` prototype tree unchanged. The merged worker prototype still imports Core v2 prototype modules directly, so copying it into production would bypass the productionized Core boundary.

## v0.1 production boundary

This first increment is intentionally restricted:

- local systemd service only;
- requires `karmo-core.service`;
- imports the production `core_service` package and fails closed if unavailable;
- no network listener;
- no real worker network transport;
- no PostgreSQL or Qdrant writes;
- no secrets;
- no capability/job execution yet;
- no external/customer/marketplace actions.

Its purpose is to establish the production service lifecycle and prove the Worker is bound behind the production Core control layer before capability execution is enabled.

## Health check

From a repository checkout:

```bash
PYTHONPATH=core-service:worker-service python3 -m worker_service health
```

Expected: exit code `0`, `"status": "healthy"`, `"core_bound": true`, and all execution/network/write flags false.

## Planned production paths

- application: `/opt/karmo/worker-service`
- service: `karmo-worker.service`
- Core dependency: `/opt/karmo/core-service`

## Rollback

Disable/remove only `karmo-worker.service` and `/opt/karmo/worker-service`. Do not modify Core or any existing KARMO service/data during Worker rollback.
