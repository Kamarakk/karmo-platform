# KARMO Core Service

Productionization boundary for the KARMO Control & Approval Layer (Core v2).

This directory is deliberately separate from `core-v2-prototypes/`. The prototype tree remains evidence/design material and is not itself deployed.

## v0.1 deployment boundary (historical)

The first production-safe boundary was intentionally local and
dependency-light:

- no database schema changes;
- no Qdrant access;
- no external network listener;
- no secrets;
- no marketplace/customer actions;
- no autonomous scheduling;
- no existing KARMO service dependency or restart;
- health is exposed through a local CLI/process exit code and JSON output.

The first service increment preserved the verified Core semantics that can be safely adopted without persistence or external side effects: capability classification, computed approval requirements, exact tool/version/argument approval binding, executor binding, TTL/terminal-state handling, and single-use execution.

Persistent approval/job state is intentionally not claimed by this increment. A service restart starts with an empty in-memory control state (`karmo-core.service`'s own approval/job control state — not the conversation-memory feature below). This limitation is explicit and must remain visible until a separately approved persistence design exists.

## Durable memory increment (superseding the "no Qdrant/no secrets" points above)

`core_service.durable_memory` (wired into the `chat` operator, PR #48)
reuses the existing H0.1/H0.2 PostgreSQL + Qdrant memory stack — this is
the one part of the v0.1 boundary above that no longer holds:

- reads/writes `public.conversation_memory` and inserts into
  `public.karmo_outbox` (existing tables, no schema change);
- reads Qdrant `karmo_semantic_memory` / `karmo_documents` (existing
  collections, read-only from Core);
- reads one secret: `/etc/karmo/core/postgres.dsn`, a least-privilege
  `karmo_core_memory` DB role (not `karmo_gateway`) — see
  `docs/review/KARMO_DURABLE_MEMORY_DEPLOYMENT_GATE.md` for exact
  provisioning.
- **runtime dependencies**: `core-service/requirements.txt` (`psycopg[binary]`,
  `qdrant-client`) must actually be installed for whichever Python
  interpreter runs `core_service` on the host — this was missed on first
  deploy (production assumed an existing venv had it; the `chat` CLI
  path uses system `/usr/bin/python3`, which didn't). Install with:
  `python3 -m pip install -r core-service/requirements.txt` for that
  same interpreter before restarting the service.
- still no external network listener, no marketplace/customer actions, no
  autonomous scheduling.

`chat` remains a manual, interactive CLI (`/usr/local/bin/karmo`, or
`python3 -m core_service chat`) run directly by a human operator — it is
**not** invoked by `karmo-core.service` itself. Any file this path reads
(e.g. `postgres.dsn`) must be owned/readable by the operator account that
actually runs `chat`, not by whichever account runs the systemd unit.

## Local health check

```bash
python3 -m core_service health
```

Expected: exit code `0` and JSON containing `"status": "healthy"`.

## Rollback

Stop/disable only the new Core service, then remove only its new service/application files. Existing KARMO services and data are untouched.
