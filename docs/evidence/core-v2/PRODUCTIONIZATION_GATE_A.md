# Core v2 Productionization — Gate A

Status: **REPOSITORY IMPLEMENTATION CONSOLIDATED — HOST PREFLIGHT / DEPLOYMENT STILL PENDING**

## Invariant Impact Review

Phase: Core v2 productionization

- I-01 Inheritance/compatibility: AFFECTED — prototype semantics must be preserved when adapters are introduced; no legacy data is touched in this increment.
- I-02 Production parity: AFFECTED — bounded service has explicit working directory, system Python entry point, restart behavior, boot persistence target, stdout/journal failure visibility, and no interactive-shell configuration dependency. Actual host runtime remains to be verified before deployment.
- I-03 Data authority/transactions: NOT AFFECTED in this increment — persistent writes are disabled.
- I-04 Idempotency/retry: AFFECTED — the adopted approval engine preserves exact binding and single-use execution semantics in-memory; no durable retry path is added in this increment.
- I-05 Resources/scale: AFFECTED — runner is constant-memory and performs no unbounded data operation.
- I-06 Migration/rollback: AFFECTED — no migration; rollback is removal/disable of only the new Core files/service.
- I-07 Observability: AFFECTED — startup health is emitted to service logs and the CLI health path returns machine-readable JSON.
- I-08 Validation scope: AFFECTED — targeted service-boundary tests only until the integration boundary changes.
- I-09 Authority/permissions: AFFECTED — service remains local-only: no network listener, database/Qdrant writes, worker transport, subprocess execution, or secrets.

Known inherited assumptions: Core v2 prototype semantics are design evidence, not deployable production code.
Legacy-data considerations: none; no persistent data read/write.
Authoritative data stores: none in this increment.
Transaction/failure boundaries: in-memory approval lifecycle + process lifecycle only.
Scale considerations: constant-memory idle service; approval state is intentionally in-memory and bounded to the process lifetime.
Runtime/dependency requirements: Python 3 standard library only; actual KARMO-AI01 execution user/path/runtime must be verified before host write.
Migration/mixed-state requirements: none.
Observability requirements: JSON startup/CLI health plus systemd/journal process state.
Authorization boundaries: approval requirement floors, exact tool/version/argument binding, executor binding, TTL/terminal-state handling, and single-use execution are preserved inside the bounded service package.
Validation plan: targeted tests for approval-floor escalation, exact binding/single use, changed-argument rejection, and local health; deployment smoke only after host preflight passes.
Rollback implications: disable/remove only new `karmo-core` service and `/opt/karmo/core-service` files; existing KARMO services remain untouched.

## Canonical application boundary

`core-service/` is the single productionization boundary for this rollout.

A duplicate `core-runtime/` implementation was discovered on the branch during resumed review. It duplicated service lifecycle and deployment concerns while `core-service/` already contained the actual adopted Core approval semantics. The duplicate `core-runtime/` files were removed so production does not have two competing Core implementations.

Canonical components now are:

- `core-service/core_service/control.py` — bounded adoption of verified Core approval/capability semantics;
- `core-service/core_service/__main__.py` — local CLI health path;
- `core-service/core_service/runner.py` — long-running local-only process entry point;
- `core-service/deploy/karmo-core.service` — hardened systemd service definition;
- `core-service/tests/test_core_service.py` — targeted control-boundary tests.

Properties of this increment:

- local process only;
- no listening socket;
- no PostgreSQL/Qdrant access;
- no subprocess/tool execution;
- no worker network transport;
- no secret dependency;
- standard-library-only runtime;
- hardened systemd service definition prepared for bounded host installation;
- persistent approval/job state is deliberately **not** claimed; restart resets in-memory state.

## Gate A remaining work

Before any production host write:

1. run targeted tests in the isolated dev checkout against the consolidated `core-service/` implementation;
2. verify actual KARMO-AI01 execution user, Python path/version, target directory permissions, and systemd availability without exposing secrets;
3. confirm `/opt/karmo/core-service` and `karmo-core.service` do not collide with existing production paths/services;
4. only then perform the already-authorized isolated Core installation and one smoke check.

Worker remains blocked until Core passes its production smoke check.

## Current blocker classification

This is **not** a design-approval blocker. The production authorization is already granted.

The remaining gate is operational verification of the real host execution model before the first production write, as required by I-02 and the approved rollout plan.
