# KARMO Durable Memory Deployment Gate

Deploy only after explicit Production Access Authorization is granted per
`docs/governance/KARMO_ENGINEERING_INVARIANTS.md`'s Mandatory Production
Access Authorization Gate. This document does not itself authorize
anything.

Candidate: merged `main` at `7b50a381b2e19e1b12aecd59182df3fd4215216b`
(PR #48, `feat/durable-memory-core-integration`). CI green (Core
Productionization, KARMO Full Predeploy — all 4 jobs), independent
security review clean, local re-verification on merged `main`: 79 passed
core-service (33 skipped, no local Postgres — those ran and passed in
CI), 109 passed worker-runtime, 161 passed core-v2-prototypes, 2 passed
worker-service + healthy CLI.

## WHAT
Wire the already-live PostgreSQL `conversation_memory` / `karmo_outbox`
(H0.1) and Qdrant `karmo_semantic_memory` / `karmo_documents` (H0.2) into
the currently-deployed Core chat operator on `karmo-ai01`, so chat gains
recent-turn recall, semantic recall, and document recall, with every
exchange durably persisted through the existing outbox pattern.

## WHY
Restore durable conversational/semantic/document memory to Core chat
without adding a new service, listener, or datastore — closing the gap
recorded in `docs/project-state/CURRENT_STATE.md`/`NEXT_STEPS.md`.

## CHANGE
1. Provision a new least-privilege PostgreSQL role, `karmo_core_memory`,
   scoped to exactly:
   - `CONNECT` on the KARMO database
   - `USAGE` on schema `public`
   - `SELECT, INSERT` on `public.conversation_memory`
   - `INSERT` on `public.karmo_outbox`
   - nothing else — explicitly **not** `karmo_gateway`, and no access to
     `karmo_worker_jobs`, `core_approval_records`, `karmo_execution_tickets`,
     `karmo_workers`, `karmo_worker_events`, `tool_invocation_ledger`, etc.
2. Write `/etc/karmo/core/postgres.dsn` on `karmo-ai01`, containing only
   the new role's DSN, mode `0600`, owned by the account `karmo-core.service`
   runs as (currently root — no `User=` in the unit; confirm before writing).
3. Update `/opt/karmo/core-service` to merge commit `7b50a381b2e19e1b12aecd59182df3fd4215216b`
   (backup existing tree first, per established pattern).
4. Restart `karmo-core.service`.
5. Run one bounded production smoke test (Section VERIFY below).

## EXPLICITLY NOT CHANGED
- no schema migration (tables already exist from H0.1/H0.2)
- no Qdrant collection/schema change
- no change to `karmo_gateway`'s existing grants
- no Worker network listener
- no new daemon/service/port
- no firewall/Tailscale/SSH change
- no change to any table other than `conversation_memory` (SELECT/INSERT)
  and `karmo_outbox` (INSERT) via the new scoped role

## RISK
- Wrong/overbroad grant on the new role — mitigated by the exact GRANT
  list above; verify with `\dp` after creation.
- DSN file readable by an unintended account — mitigated by mode `0600`
  and ownership check (`durable_memory.py` itself refuses to start if the
  file is group/other-accessible).
- `KARMO_DB_PASSWORD`-style env-var expectation mismatch (flagged in the
  prior handoff) — this build reads the DSN from the file, not an env var,
  so that mismatch does not apply to this path; confirm no stale env var
  is set that could shadow it.
- Service restart briefly interrupts Core chat availability (Worker
  Commander READ paths are unaffected — separate service).

## CONFIRMED BY READ-ONLY AUDIT (2026-09-15, karmo-ai01)
- `karmo-core.service` `User=` is empty → runs as **root**; no stale
  `KARMO_DB_PASSWORD` env var present (no shadowing risk).
- `/etc/karmo/core/` does **not** exist yet — must be created (step 3).
- `karmo-postgres` container: `POSTGRES_DB=karmo`, `POSTGRES_USER=karmo`.
  Admin connection: `docker exec -it karmo-postgres psql -U karmo -d karmo`.
- Baseline listeners (for step 7 comparison): loopback-only 5433
  (Postgres), 6333/6334 (Qdrant), 11434 (Ollama), plus SSH (22), DNS, and
  Tailscale's own ports. No KARMO application listener present — this is
  the expected post-deploy state too.
- `DBNAME` below is `karmo`.

## VERIFY (exact commands, run on `karmo-ai01`)

**1. Confirm current service account for `karmo-core.service`:**
```
systemctl show karmo-core.service -p User
```
Expected: empty (root) or a named account — use that account for DSN file
ownership in step 3.

**2. Create the scoped role** (run on `karmo-ai01`; generates and injects
the password without ever printing or typing it into chat):
```
NEWPW=$(openssl rand -base64 32)
docker exec -i karmo-postgres psql -U karmo -d karmo -v newpw="$NEWPW" <<'SQL'
CREATE ROLE karmo_core_memory WITH LOGIN PASSWORD :'newpw';
GRANT CONNECT ON DATABASE karmo TO karmo_core_memory;
GRANT USAGE ON SCHEMA public TO karmo_core_memory;
GRANT SELECT, INSERT ON public.conversation_memory TO karmo_core_memory;
GRANT INSERT ON public.karmo_outbox TO karmo_core_memory;
SQL
```
Expected: `CREATE ROLE` / `GRANT` x4, no errors. If `docker exec -U karmo`
prompts for a password, stop and report — it means local trust auth
isn't configured the way the prior gateway-grant session assumed, and the
admin credential needs to come from you rather than being typed in chat.

**3. Write the DSN file** (as root, since `karmo-core.service` runs as
root; `/etc/karmo/core/` does not exist yet per the audit):
```
sudo install -d -m 700 -o root -g root /etc/karmo/core
sudo install -m 600 -o root -g root /dev/null /etc/karmo/core/postgres.dsn
printf 'host=127.0.0.1 port=5433 dbname=karmo user=karmo_core_memory password=%s\n' "$NEWPW" \
  | sudo tee /etc/karmo/core/postgres.dsn > /dev/null
unset NEWPW
```
Expected: file exists, mode `600`, owned `root:root`. Never `cat` this
file to the terminal after writing.

**4. Build and ship the exact reviewed tree, then deploy it — same
tarball + SHA-256 + backup pattern used for the Worker02 rollout.**

On **KARMO-DEV01** (this Mac):
```
cd ~/KARMO-DEV
git rev-parse HEAD   # must print 7b50a381b2e19e1b12aecd59182df3fd4215216b
tar -czf /tmp/karmo-core-service-7b50a38.tar.gz -C core-service .
shasum -a 256 /tmp/karmo-core-service-7b50a38.tar.gz
scp -i ~/.ssh/karmo_admin_ed25519 /tmp/karmo-core-service-7b50a38.tar.gz lofason@100.75.239.44:/tmp/
```
Note the SHA-256 printed here.

On **karmo-ai01**:
```
shasum -a 256 /tmp/karmo-core-service-7b50a38.tar.gz
```
Expected: matches the SHA-256 from KARMO-DEV01 exactly. Stop if it
doesn't.
```
stat -c '%U:%G' /opt/karmo/core-service    # note current owner:group
mkdir -p /tmp/karmo-core-service-new
tar -xzf /tmp/karmo-core-service-7b50a38.tar.gz -C /tmp/karmo-core-service-new
sudo cp -a /opt/karmo/core-service /opt/karmo/core-service.bak.$(date +%Y%m%dT%H%M%S)
sudo rm -rf /opt/karmo/core-service
sudo mv /tmp/karmo-core-service-new /opt/karmo/core-service
sudo chown -R <owner:group from stat above> /opt/karmo/core-service
rm -f /tmp/karmo-core-service-7b50a38.tar.gz
```
Expected: `/opt/karmo/core-service` now contains `core_service/durable_memory.py`;
`/opt/karmo/core-service.bak.<timestamp>` holds the pre-deploy tree.

**5. Restart and confirm service health:**
```
sudo systemctl restart karmo-core.service
systemctl is-active karmo-core.service
python3 -m core_service health
```
Expected: `active`; health JSON `"status": "healthy"`.

**6. Bounded production smoke/canary — one chat turn, verify memory wired:**
```
printf 'Remember for this canary only: the phrase is durable-memory-canary-2026-09-15.\n' | /usr/local/bin/karmo chat
```
Expected CLI output includes `KARMO> memory=ACTIVE` (not
`DEGRADED_CONFIG_MISSING` or `DEGRADED_*`).

Then confirm the write landed durably:
```
docker exec -i karmo-postgres psql -U karmo -d karmo -c \
  "SELECT role, content FROM public.conversation_memory ORDER BY id DESC LIMIT 2;"
docker exec -i karmo-postgres psql -U karmo -d karmo -c \
  "SELECT event_type, status FROM public.karmo_outbox ORDER BY created_at DESC LIMIT 1;"
```
Expected: the two new rows (`user`/`assistant`) and one new
`semantic_memory.upsert.v1` outbox row, `status='pending'` (delivered
asynchronously by the existing H0.1 relay — do not wait/poll here beyond
this one check).

**7. Confirm no new listener, no other service disturbed:**
```
ss -H -lntu
systemctl is-active karmo-worker.service
```
Expected: unchanged from pre-deploy listener set; `karmo-worker.service`
still `active`.

## ROLLBACK
1. `sudo systemctl stop karmo-core.service`
2. `sudo rm -rf /opt/karmo/core-service && sudo mv /opt/karmo/core-service.bak.<timestamp> /opt/karmo/core-service`
3. `sudo systemctl start karmo-core.service` and re-run step 5's health
   check against the restored code.
4. Leave the new `karmo_core_memory` role in place unless it is
   implicated in the failure (dropping a role is a separate, explicit
   decision — do not drop it reflexively).
5. `/etc/karmo/core/postgres.dsn` may remain; the restored old code does
   not read it.

Stop and roll back on: any VERIFY step failing, an unexpected
`ACTIVE_STATE_MISMATCH`/data-integrity signal, a new listening socket, or
`karmo-worker.service` becoming inactive.

## Production Access Authorization required

Per `docs/governance/KARMO_ENGINEERING_INVARIANTS.md`, record before any
step above is executed:

```
PRODUCTION ACCESS AUTHORIZATION
Task: Durable memory Core integration deployment (PR #48 / commit 7b50a381)
Target system/environment: karmo-ai01 — karmo-postgres (conversation_memory,
  karmo_outbox tables only), /opt/karmo/core-service, /etc/karmo/core/,
  karmo-core.service
Purpose: deploy merged, tested, security-reviewed durable-memory Core
  integration
Permitted operations: create scoped Postgres role + grants (step 2); write
  /etc/karmo/core/postgres.dsn (step 3); backup + replace
  /opt/karmo/core-service (step 4); restart karmo-core.service (step 5);
  one bounded chat canary + read-only verification queries (step 6); read
  listener/service status (step 7)
Authority: READ-ONLY + WRITE — specifically: CREATE ROLE/GRANT (scoped as
  above), file write to /etc/karmo/core/postgres.dsn, file replace under
  /opt/karmo/core-service, one service restart. No other write.
Commands/command class: exactly the numbered commands in this document's
  VERIFY section
Granted: <date, by Kamara>
Expires: automatically on task completion
```
