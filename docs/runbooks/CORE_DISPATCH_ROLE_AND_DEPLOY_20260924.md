# karmo_core_dispatch role + DSN + core-service redeploy (2026-09-24)

**Covers:** provisioning the `karmo_core_dispatch` Postgres role and
`/etc/karmo/core/worker-dispatch.dsn`, and redeploying `core-service` to
`karmo-ai01` so migration 011 and PRs #117-#122 (local eyes/coding-
helper/ears/voice, browser + phone client surface, D2/dispatch
decoupling) actually run there.
**Read this if:** finishing the karmo_core_dispatch/DSN provisioning
task started 2026-09-24, or redeploying core-service to `karmo-ai01`
for any later reason.
**Status:** point-in-time facts as of 2026-09-24 (deployed core-service
on `karmo-ai01` confirmed missing `migrations/011_grant_core_dispatch_least_privilege.sql`
-- predates PR #118). Steps 2-4 (role/DSN/restart) completed and
**verified working live** (`PostgresWorkerDispatchClient` constructs
and authenticates against production Postgres) -- see "Execution log"
below. **Step 0/1 (redeploy) still not run** -- the code that would
actually use this credential (migration 011's grants, and every
capability added since PR #118) is not yet on `karmo-ai01`.

---

## Execution log

- **2026-09-24, Kamara, before the redeploy (steps 0-1 skipped)**: ran
  an earlier version of step 2's role-creation SQL that wrapped the
  CREATE/ALTER choice in a `DO $$ ... $$` block. Hit
  `ERROR: syntax error at or near ":"` -- `psql`'s `:'newpw'`
  interpolation does not work inside dollar-quoted blocks (see step 2's
  own note below for the full explanation). The GRANT statements after
  it still printed success (psql doesn't abort on error by default),
  producing misleading clean-looking output. Consequence: the DSN file
  written immediately after (step 3, which itself wrote correctly this
  time) contains a password that does **not** match the role's actual
  password in Postgres.
- **2026-09-24, same day, corrected and verified**: re-ran step 2 with
  the corrected plain top-level `CREATE ROLE` + `ALTER ROLE` (no `$$`
  block), rewrote the DSN with the same fresh password (step 3),
  restarted (step 4), then ran the auth-check script below. Live
  result: `available: True` / `auth check: OK` -- the
  `PostgresWorkerDispatchClient` genuinely constructs and authenticates
  against production Postgres with this credential. The role/DSN half
  of this task is done and confirmed, not just assumed.
- Step 0/1 (redeploying `core-service` so migration 011 and PRs
  #117-#122 are actually present on `karmo-ai01`) has not been run as
  of this entry -- the role/DSN work above was attempted independently
  of it.

---

## Why a redeploy is needed at all

`karmo-ai01`'s `/opt/karmo/core-service` tree does not have migration
011 on disk (confirmed live 2026-09-24: `ls` on that path returned "No
such file or directory"). That means the deployed code predates PR
#118 (2026-09-20) -- everything since (local eyes/coding-helper/ears/
voice, the browser/phone client surface, the D2 dispatch-DSN
decoupling fix) is merged to `main` but not running on `karmo-ai01`.
Provisioning the role/DSN without redeploying would activate dispatch
for code that isn't there yet -- do the redeploy first, or at least in
the same session.

## Step 0 -- build and verify the deploy tarball (KARMO-DEV01, local, no SSH)

```sh
cd ~/KARMO-DEV
git fetch origin main
git log --oneline -1 origin/main   # expect c558e61 or later
git archive --format=tar.gz --output=/tmp/karmo-core-deploy.tar.gz origin/main:core-service
shasum -a 256 /tmp/karmo-core-deploy.tar.gz
tar -tzf /tmp/karmo-core-deploy.tar.gz | grep migrations/011
```
Last line must print `core_service/migrations/011_grant_core_dispatch_least_privilege.sql`.

## Step 1 -- copy to karmo-ai01 and back up current tree

```sh
scp /tmp/karmo-core-deploy.tar.gz lofason@100.75.239.44:/tmp/
```

```sh
ssh -tt lofason@100.75.239.44 '
set -eu
TS=$(date -u +%Y%m%dT%H%M%SZ)
echo "$TS" | tee /tmp/karmo_core_deploy_ts
sudo mkdir -p /opt/karmo/backups/core-deploy-$TS
sudo cp -a /opt/karmo/core-service /opt/karmo/backups/core-deploy-$TS/core-service-before
rm -rf /tmp/karmo-core-deploy-stage
mkdir /tmp/karmo-core-deploy-stage
tar -xzf /tmp/karmo-core-deploy.tar.gz -C /tmp/karmo-core-deploy-stage
sudo cp -a /tmp/karmo-core-deploy-stage/. /opt/karmo/core-service/
grep -c "011_grant_core_dispatch" /opt/karmo/core-service/core_service/migrations/011_grant_core_dispatch_least_privilege.sql || true
ls /opt/karmo/core-service/core_service/migrations/011_grant_core_dispatch_least_privilege.sql
'
```
Expected: the final `ls` succeeds (file now present). Do not restart
`karmo-core.service` yet -- the role/DSN steps below should land first
so the restart that finally picks up the DSN also has correct code.

## Step 2 -- provision the role and migration 011's grants

Still on `karmo-ai01` (same SSH session or a fresh one):

```sh
NEWPW=$(openssl rand -base64 32)
docker exec -i karmo-postgres psql -U karmo -d karmo -v newpw="$NEWPW" <<'SQL'
CREATE ROLE karmo_core_dispatch WITH LOGIN PASSWORD :'newpw';
ALTER ROLE karmo_core_dispatch WITH PASSWORD :'newpw';
GRANT CONNECT ON DATABASE karmo TO karmo_core_dispatch;
GRANT USAGE ON SCHEMA public TO karmo_core_dispatch;
GRANT INSERT, SELECT, UPDATE ON public.core_approval_records TO karmo_core_dispatch;
GRANT INSERT, SELECT ON public.karmo_worker_jobs TO karmo_core_dispatch;
GRANT INSERT, SELECT ON public.karmo_worker_job_payloads TO karmo_core_dispatch;
GRANT SELECT ON public.karmo_worker_job_results TO karmo_core_dispatch;
SQL
```
Expected: `CREATE ROLE` (or an "already exists" error, harmless --
psql keeps executing subsequent statements by default), then
`ALTER ROLE`, then `GRANT` x6.

**Real bug found and fixed live 2026-09-24, do not reintroduce it**: an
earlier version of this script wrapped the CREATE/ALTER choice in a
`DO $$ ... $$` block with an `IF NOT EXISTS` check. `psql`'s `:'var'`
client-side interpolation is **not performed inside dollar-quoted
regions** (`$$...$$` is treated as opaque text, specifically so
literal PL/pgSQL bodies can be embedded safely) -- so `:'newpw'` was
sent to the server literally, and PL/pgSQL has no such syntax, giving
`ERROR: syntax error at or near ":"`. The role's password was never
actually set that run, while all the GRANT statements after it still
"succeeded" (psql doesn't abort on error by default), producing
misleadingly clean-looking output while the about-to-be-written DSN
file's password wouldn't match the role's real password in Postgres.
**Always run `CREATE ROLE`/`ALTER ROLE ... WITH PASSWORD :'newpw'` as
plain top-level statements, never inside `$$...$$`.** The
CREATE-then-ALTER pair above is idempotent and always ends with the
role's password equal to `$NEWPW`, whether the role was just created
or already existed -- no conditional logic needed.

## Step 3 -- write the DSN file

Paste only this block, nothing else (a prior attempt in this same
session broke when surrounding prose got pasted alongside the
commands):

```sh
sudo install -d -m 700 -o root -g root /etc/karmo/core
sudo install -m 600 -o root -g root /dev/null /etc/karmo/core/worker-dispatch.dsn
printf 'host=127.0.0.1 port=5433 dbname=karmo user=karmo_core_dispatch password=%s\n' "$NEWPW" | sudo tee /etc/karmo/core/worker-dispatch.dsn > /dev/null
unset NEWPW
```

## Step 4 -- restart and verify

```sh
sudo systemctl restart karmo-core.service
systemctl is-active karmo-core.service
ss -H -lntu
sudo ls -la /etc/karmo/core/worker-dispatch.dsn
sudo wc -l /etc/karmo/core/worker-dispatch.dsn
```
Expected: `active`; no new listener beyond the existing baseline
(loopback 5433/6333/6334/11434, Tailscale interface, SSH); DSN file
`-rw-------` owned `root root`; exactly 1 line.

**Read-only confirmation that the grants actually took** (never prints
the password):
```sh
docker exec -i karmo-postgres psql -U karmo -d karmo -c "\du karmo_core_dispatch" -c "
SELECT table_name, privilege_type FROM information_schema.role_table_grants
WHERE grantee = 'karmo_core_dispatch' ORDER BY table_name, privilege_type;"
```
Expected 7 rows: `core_approval_records` (INSERT, SELECT, UPDATE),
`karmo_worker_job_payloads` (INSERT, SELECT), `karmo_worker_job_results`
(SELECT), `karmo_worker_jobs` (INSERT, SELECT).

**Confirm the dispatch client actually constructs** (prints only
`True`/`False`, never the DSN or password):
```sh
sudo -u root /usr/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/karmo/core-service')
from core_service.worker_dispatch_client import build_default_worker_dispatch_client
print(build_default_worker_dispatch_client().available)
"
```
Expected: `True`.

## What this does NOT do

- Does not activate Model Router Phase D2's chat-routing path -- that
  needs the separate `/etc/karmo/core/d2-chat-routing.enabled` gate
  file (PR #118), not touched here, and stays a deliberate later
  decision.
- Does not confirm Worker01 still has vision/ears/voice/coding-helper
  registered -- that was live-verified during PR #117's own build
  session; worth a real end-to-end test (e.g. a `/vision` call from the
  webui) after this lands, not assumed.
- Does not touch Worker01/Worker02 code at all -- only `karmo-ai01`'s
  `core-service`.

## Rollback

```sh
ssh lofason@100.75.239.44
B=$(ls -1dt /opt/karmo/backups/core-deploy-* | head -1)
sudo systemctl stop karmo-core.service
sudo rm -rf /opt/karmo/core-service
sudo cp -a "$B/core-service-before" /opt/karmo/core-service
sudo systemctl start karmo-core.service
```
The role/DSN are additive and read-only-safe to leave in place even on
a code rollback -- old code simply never reads the new DSN file.
