# Core v2 Productionization — Gate A

Status: **IMPLEMENTATION IN PROGRESS — HOST DEPLOYMENT NOT AUTHORIZED BY THIS FILE**

## Invariant Impact Review

Phase: Core v2 productionization

- I-01 Inheritance/compatibility: AFFECTED — prototype semantics must be preserved when adapters are introduced; no legacy data is touched in this increment.
- I-02 Production parity: AFFECTED — bounded service has explicit working directory, system Python entry point, restart behavior, boot persistence target, stdout/journal failure visibility, and no interactive-shell configuration dependency. Actual host runtime remains to be verified before deployment.
- I-03 Data authority/transactions: NOT AFFECTED in this increment — persistent writes are disabled.
- I-04 Idempotency/retry: NOT AFFECTED in this increment — no actions/jobs execute.
- I-05 Resources/scale: AFFECTED — runner is constant-memory and performs no unbounded data operation.
- I-06 Migration/rollback: AFFECTED — no migration; rollback is removal/disable of only the new Core files/service.
- I-07 Observability: AFFECTED — explicit STARTING/HEALTHY/FAILED state and failure reason; startup health is emitted to service logs.
- I-08 Validation scope: AFFECTED — targeted service-boundary tests only until the integration boundary changes.
- I-09 Authority/permissions: AFFECTED — service is deliberately inert: no network listener, persistent writes, worker transport, subprocess execution, or secrets.

Known inherited assumptions: Core v2 prototype semantics are design evidence, not deployable production code.
Legacy-data considerations: none; no persistent data read/write.
Authoritative data stores: none in this increment.
Transaction/failure boundaries: process lifecycle only.
Scale considerations: constant-memory idle service.
Runtime/dependency requirements: Python 3 standard library only; actual KARMO-AI01 execution user/path/runtime must be verified before host write.
Migration/mixed-state requirements: none.
Observability requirements: health state + failure reason in-process; startup state emitted to service logs.
Authorization boundaries: no capability execution in this increment.
Validation plan: targeted unit validation of healthy inert startup and visible failure; deployment smoke only after host preflight passes.
Rollback implications: disable/remove only new `karmo-core` service and `/opt/karmo/core-runtime` files; existing KARMO services remain untouched.

## Stable application boundary added

`core-runtime/karmo_core/` now defines the first real Core service boundary rather than copying `core-v2-prototypes/` into production.

Properties of this increment:

- local process only;
- no listening socket;
- no PostgreSQL/Qdrant access;
- no subprocess/tool execution;
- no worker network transport;
- no secret dependency;
- explicit health/failure state;
- standard-library-only runtime;
- hardened systemd service definition prepared for later bounded host installation.

## Gate A remaining work

Before any production host write:

1. run targeted tests in the isolated dev checkout;
2. verify actual KARMO-AI01 execution user, Python path/version, target directory permissions, and systemd availability without exposing secrets;
3. confirm the proposed `/opt/karmo/core-runtime` and `karmo-core.service` names do not collide with existing production paths/services;
4. only then perform the already-authorized isolated Core installation and one smoke check.

Worker remains blocked until Core passes its production smoke check.
