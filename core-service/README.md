# KARMO Core Service

Productionization boundary for the KARMO Control & Approval Layer (Core v2).

This directory is deliberately separate from `core-v2-prototypes/`. The prototype tree remains evidence/design material and is not itself deployed.

## v0.1 deployment boundary

This first production-safe boundary is intentionally local and dependency-light:

- no database schema changes;
- no Qdrant access;
- no external network listener;
- no secrets;
- no marketplace/customer actions;
- no autonomous scheduling;
- no existing KARMO service dependency or restart;
- health is exposed through a local CLI/process exit code and JSON output.

The first service increment preserves the verified Core semantics that can be safely adopted without persistence or external side effects: capability classification, computed approval requirements, exact tool/version/argument approval binding, executor binding, TTL/terminal-state handling, and single-use execution.

Persistent approval/job state is intentionally not claimed by this increment. A service restart starts with an empty in-memory control state. This limitation is explicit and must remain visible until a separately approved persistence design exists.

## Local health check

```bash
python3 -m core_service health
```

Expected: exit code `0` and JSON containing `"status": "healthy"`.

## Rollback

Stop/disable only the new Core service, then remove only its new service/application files. Existing KARMO services and data are untouched.
