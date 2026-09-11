# Worker Runtime Productionization — Gate C

Status: **IMPLEMENTATION IN PROGRESS — WORKER HOST DEPLOYMENT BLOCKED UNTIL CORE IS HEALTHY**

## Invariant Impact Review

Phase: Worker Runtime productionization

- I-01 Inheritance/compatibility: AFFECTED — existing Worker Runtime imports Core v2 prototype modules directly and cannot be deployed unchanged.
- I-02 Production parity: AFFECTED — production worker service/user/path/runtime must match KARMO-AI01 and must not depend on interactive shell state.
- I-03 Data authority/transactions: NOT AFFECTED in this increment — no database/Qdrant persistence is added.
- I-04 Idempotency/retry: AFFECTED — existing deterministic job/claim semantics remain design evidence; no network retry path is enabled.
- I-05 Resources/scale: AFFECTED — first production boundary stays idle/local-only with no unbounded queue/network loop.
- I-06 Migration/rollback: AFFECTED — no migration; rollback is disable/remove only the new worker service/files.
- I-07 Observability: AFFECTED — startup health must state Core binding, local-only transport posture, and failure reason.
- I-08 Validation scope: AFFECTED — targeted production-boundary tests only; do not rerun the historical 68-test suite unless shared behavior changes.
- I-09 Authority/permissions: AFFECTED — worker execution remains disabled until bound to production Core approval semantics; no real network transport.

## Repository findings

The merged Worker Runtime is verified prototype/proving code, but three reuse shims still import directly from `core-v2-prototypes/` through `_prototype_paths.py`:

- `approval_engine_reuse.py`
- `tool_registry_reuse.py`
- `job_model_reuse.py`

Therefore Worker Runtime **must not be copied unchanged into production**. Doing so would bypass the productionized Core boundary created under `core-service/`.

`transport.py` also explicitly documents that the current `LocalTransport` is in-process only and that real network transport is not production-ready. Real network transport remains disabled by this rollout.

## Restricted first production boundary

The first worker production increment will:

- run as a separate local systemd service on KARMO-AI01;
- expose no network listener;
- enable no real worker network transport;
- perform no PostgreSQL or Qdrant writes;
- require no secrets;
- execute no marketplace/customer/external actions;
- fail closed if the production Core package cannot be imported;
- report local health and Core-binding state;
- keep actual capability/job execution disabled until the prototype reuse shims are safely replaced/adapted to the production Core API.

## Deferred blockers that remain blockers for real network exposure

- cryptographic worker credential;
- subprocess environment allowlist;
- dedicated symlink-escape test;
- result-authenticity cryptographic binding;
- coordinator persistence.

These do not block an inert/local-only worker service boundary, but they do block real network worker transport.

## Gate C exit criteria

1. production worker service boundary exists and fails closed without `core_service`;
2. no prototype directory is imported by the production boundary;
3. no network listener/transport is enabled;
4. targeted CI proves Core binding and fail-closed startup behavior;
5. Core production smoke has passed before Worker host installation begins;
6. host install remains isolated to new Worker files/service and has a removal-only rollback.

Worker host deployment remains blocked until Core is installed and passes its single approved production smoke check.
