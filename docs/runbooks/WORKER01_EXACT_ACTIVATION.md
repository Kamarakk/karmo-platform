# Worker01 exact activation commands

Prepared only. Run only after PR #44 is reviewed, green, and merged. Worker02 remains untouched until Worker01 passes every verification gate.

## 0. Required trust gate

From KVE01, independently read the VM101 ED25519 host fingerprint through QGA:

```sh
qm guest exec 101 -- ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Expected fingerprint from the earlier DEV01 observation:

```text
SHA256:442Z8de+bifl75mAgeJYKUYa9eXwzaJRJf1RVRlfVuo
```

Mismatch means STOP.

## 1. Set the reviewed merge SHA on KARMO-DEV01

```sh
cd ~/KARMO-DEV
git fetch origin
export DEPLOY_SHA='<PR44_MERGE_SHA>'
git cat-file -t "$DEPLOY_SHA"
git archive --format=tar.gz --output=/tmp/karmo-worker-deploy.tar.gz "$DEPLOY_SHA"
shasum -a 256 /tmp/karmo-worker-deploy.tar.gz
```

## 2. Production dependency preflight on AI01

```sh
ssh lofason@192.168.1.235 '/usr/bin/python3 -c "import psycopg; print(psycopg.__version__)"'
```

If that fails, STOP. Do not improvise a package installation during activation; install the reviewed Python PostgreSQL dependency in a separately approved production step.

## 3. Copy reviewed source to AI01 and Worker01

```sh
scp /tmp/karmo-worker-deploy.tar.gz lofason@192.168.1.235:/tmp/
scp -i ~/.ssh/karmo_admin_ed25519 /tmp/karmo-worker-deploy.tar.gz karmo@192.168.1.251:/tmp/
```

AI01 backup and install:

```sh
ssh -t lofason@192.168.1.235 '
set -eu
TS=$(date -u +%Y%m%dT%H%M%SZ)
echo "$TS" | tee /tmp/karmo_worker_deploy_ts
sudo mkdir -p /opt/karmo/backups/worker-deploy-$TS
sudo cp -a /opt/karmo/core-service /opt/karmo/backups/worker-deploy-$TS/core-service-before
[ ! -d /opt/karmo/worker-runtime ] || sudo cp -a /opt/karmo/worker-runtime /opt/karmo/backups/worker-deploy-$TS/worker-runtime-before
rm -rf /tmp/karmo-worker-deploy-stage
mkdir /tmp/karmo-worker-deploy-stage
tar -xzf /tmp/karmo-worker-deploy.tar.gz -C /tmp/karmo-worker-deploy-stage
sudo install -d -o root -g root -m 0755 /opt/karmo/core-service /opt/karmo/worker-runtime /usr/local/libexec
sudo cp -a /tmp/karmo-worker-deploy-stage/core-service/. /opt/karmo/core-service/
sudo cp -a /tmp/karmo-worker-deploy-stage/worker-runtime/. /opt/karmo/worker-runtime/
sudo install -o root -g root -m 0755 /tmp/karmo-worker-deploy-stage/core-service/deploy/karmo-worker-gateway /usr/local/libexec/karmo-worker-gateway
sudo systemctl restart karmo-core.service
systemctl is-active karmo-core.service
/usr/local/bin/karmo status
ss -lntup
'
```

Worker01 backup and install:

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 '
set -eu
TS=$(date -u +%Y%m%dT%H%M%SZ)
sudo mkdir -p /opt/karmo/backups/worker-deploy-$TS
[ ! -d /opt/karmo/worker-runtime ] || sudo cp -a /opt/karmo/worker-runtime /opt/karmo/backups/worker-deploy-$TS/worker-runtime-before
rm -rf /tmp/karmo-worker-deploy-stage
mkdir /tmp/karmo-worker-deploy-stage
tar -xzf /tmp/karmo-worker-deploy.tar.gz -C /tmp/karmo-worker-deploy-stage
sudo install -d -o root -g root -m 0755 /opt/karmo/worker-runtime
sudo cp -a /tmp/karmo-worker-deploy-stage/worker-runtime/. /opt/karmo/worker-runtime/
'
```

## 4. Create the dedicated AI01 gateway account

```sh
ssh -t lofason@192.168.1.235 '
set -eu
getent group karmo-gateway >/dev/null || sudo groupadd --system karmo-gateway
id karmo-gateway >/dev/null 2>&1 || sudo useradd --system --create-home --home-dir /var/lib/karmo-gateway --shell /bin/sh --gid karmo-gateway karmo-gateway
sudo passwd -l karmo-gateway >/dev/null
sudo install -d -o root -g karmo-gateway -m 0750 /etc/karmo/worker-gateway
sudo install -d -o root -g root -m 0755 /var/lib/karmo-gateway/.ssh
'
```

## 5. Create Worker01's dedicated SSH transport key

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 '
set -eu
sudo install -d -o root -g karmo -m 0750 /etc/karmo/worker01
if [ ! -f /etc/karmo/worker01/ssh_identity ]; then
  ssh-keygen -q -t ed25519 -N "" -f /tmp/karmo-worker01-transport
  sudo install -o karmo -g karmo -m 0600 /tmp/karmo-worker01-transport /etc/karmo/worker01/ssh_identity
  rm -f /tmp/karmo-worker01-transport /tmp/karmo-worker01-transport.pub
fi
ssh-keygen -y -f /etc/karmo/worker01/ssh_identity
' > /tmp/karmo-worker01.pub
```

Build the one-line forced-command authorization file on DEV01:

```sh
PUB=$(cat /tmp/karmo-worker01.pub)
printf 'command="/usr/local/libexec/karmo-worker-gateway KARMO-WORKER01",restrict,no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty,no-user-rc %s\n' "$PUB" > /tmp/karmo-worker01.authorized_keys
scp /tmp/karmo-worker01.authorized_keys lofason@192.168.1.235:/tmp/
ssh -t lofason@192.168.1.235 'sudo install -o root -g root -m 0644 /tmp/karmo-worker01.authorized_keys /var/lib/karmo-gateway/.ssh/authorized_keys; rm -f /tmp/karmo-worker01.authorized_keys'
rm -f /tmp/karmo-worker01.pub /tmp/karmo-worker01.authorized_keys
```

## 6. Independently pin AI01's ED25519 host key on Worker01

Read the fingerprint locally on AI01 first:

```sh
ssh lofason@192.168.1.235 'sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub'
```

Then export the exact public key from AI01 itself and build the Worker01 pin file on DEV01:

```sh
ssh lofason@192.168.1.235 'sudo awk "{print \$1,\$2}" /etc/ssh/ssh_host_ed25519_key.pub' > /tmp/ai01-ed25519.pub
awk '{print "192.168.1.235 "$1" "$2}' /tmp/ai01-ed25519.pub > /tmp/worker01-known_hosts
scp -i ~/.ssh/karmo_admin_ed25519 /tmp/worker01-known_hosts karmo@192.168.1.251:/tmp/
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 'sudo install -o root -g root -m 0644 /tmp/worker01-known_hosts /etc/karmo/worker01/known_hosts; rm -f /tmp/worker01-known_hosts'
rm -f /tmp/ai01-ed25519.pub /tmp/worker01-known_hosts
```

Do not substitute `ssh-keyscan` for this anchor.

## 7. Create the Worker01 HMAC material

Generate only on DEV01, copy over SSH to the two endpoints, then delete the DEV01 copy:

```sh
umask 077
openssl rand -base64 48 > /tmp/karmo-worker01-v1.key
scp /tmp/karmo-worker01-v1.key lofason@192.168.1.235:/tmp/
scp -i ~/.ssh/karmo_admin_ed25519 /tmp/karmo-worker01-v1.key karmo@192.168.1.251:/tmp/
rm -f /tmp/karmo-worker01-v1.key
```

AI01:

```sh
ssh -t lofason@192.168.1.235 'sudo install -o root -g karmo-gateway -m 0640 /tmp/karmo-worker01-v1.key /etc/karmo/worker-gateway/worker01-v1.key; rm -f /tmp/karmo-worker01-v1.key'
```

Worker01:

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 'sudo install -o root -g karmo -m 0640 /tmp/karmo-worker01-v1.key /etc/karmo/worker01/worker.key; rm -f /tmp/karmo-worker01-v1.key'
```

## 8. Create the Core-only ticket key and DB DSN on AI01

```sh
ssh -t lofason@192.168.1.235 '
set -eu
sudo sh -c "umask 027; openssl rand -base64 48 > /etc/karmo/worker-gateway/core-ticket-v1.key"
sudo sh -c "umask 027; printf %s\\n postgresql://karmo@127.0.0.1:5433/karmo > /etc/karmo/worker-gateway/postgres.dsn"
sudo chown root:karmo-gateway /etc/karmo/worker-gateway/core-ticket-v1.key /etc/karmo/worker-gateway/postgres.dsn
sudo chmod 0640 /etc/karmo/worker-gateway/core-ticket-v1.key /etc/karmo/worker-gateway/postgres.dsn
'
```

If that DSN does not authenticate, STOP and use the existing approved PostgreSQL credential without echoing it into terminal history or Git.

## 9. Install reviewed configs and validate startup before enrollment

```sh
cd ~/KARMO-DEV
git show "$DEPLOY_SHA:core-service/deploy/worker-gateway.json.example" > /tmp/worker-gateway.json
git show "$DEPLOY_SHA:worker-runtime/deploy/worker01.json.example" > /tmp/worker01.json
git show "$DEPLOY_SHA:worker-runtime/deploy/karmo-worker01.service" > /tmp/karmo-worker01.service
scp /tmp/worker-gateway.json lofason@192.168.1.235:/tmp/
scp -i ~/.ssh/karmo_admin_ed25519 /tmp/worker01.json /tmp/karmo-worker01.service karmo@192.168.1.251:/tmp/
```

AI01:

```sh
ssh -t lofason@192.168.1.235 '
sudo install -o root -g karmo-gateway -m 0640 /tmp/worker-gateway.json /etc/karmo/worker-gateway.json
sudo -u karmo-gateway /usr/bin/env PYTHONPATH=/opt/karmo/core-service:/opt/karmo/worker-runtime/app /usr/bin/python3 -m core_service.worker_gateway_runtime --check-config /etc/karmo/worker-gateway.json
'
```

Worker01:

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 '
sudo install -o root -g karmo -m 0640 /tmp/worker01.json /etc/karmo/worker01.json
sudo install -o root -g root -m 0644 /tmp/karmo-worker01.service /etc/systemd/system/karmo-worker01.service
sudo systemctl daemon-reload
sudo -u karmo /usr/bin/env PYTHONPATH=/opt/karmo/worker-runtime/app /usr/bin/python3 -m remote_worker_runtime --config /etc/karmo/worker01.json --check-config
'
```

Both commands must exit 0.

## 10. Register Worker01 through the reviewed store API

This uses the durable coordinator store API; it does not insert SQL manually.

```sh
ssh -t lofason@192.168.1.235 '
sudo -u karmo-gateway /usr/bin/env PYTHONPATH=/opt/karmo/core-service:/opt/karmo/worker-runtime/app /usr/bin/python3 - <<"PY"
from core_service.worker_gateway_runtime import load_gateway_config, validate_gateway_startup, build_backend
cfg = load_gateway_config("/etc/karmo/worker-gateway.json", production_permissions=True)
validate_gateway_startup(cfg, expected_worker_id="KARMO-WORKER01")
backend = build_backend(cfg)
backend.store.register_worker(
    worker_id="KARMO-WORKER01",
    key_id="worker01-v1",
    capabilities=["local_model_probe"],
    metadata={"transport":"ssh_stdio","inbound_listener":False,"host":"192.168.1.251"},
)
print("WORKER01_REGISTERED")
PY
'
```

A duplicate registration is a refusal, not an update.

## 11. Start Worker01 and verify authenticated heartbeat

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 'sudo systemctl enable --now karmo-worker01.service; systemctl is-active karmo-worker01.service; ss -lntup'
```

Then on AI01:

```sh
ssh lofason@192.168.1.235 'docker exec karmo-postgres psql -U karmo -d karmo -x -c "SELECT worker_id,key_id,status,last_seen_at,lease_expires_at,capabilities FROM public.karmo_workers WHERE worker_id='"'"'KARMO-WORKER01'"'"';"'
```

Pass only if:
- Worker01 is ACTIVE with key id `worker01-v1`;
- `last_seen_at` is non-null and recent;
- `lease_expires_at` is in the future;
- capabilities contain only `local_model_probe`;
- Worker01 exposes no new KARMO listener;
- AI01 exposes no new KARMO application listener.

Do not touch Worker02 until these checks pass and one bounded READ proof job is completed with durable ticket/result/event evidence.

## Rollback Worker01

Stop the worker first:

```sh
ssh -i ~/.ssh/karmo_admin_ed25519 karmo@192.168.1.251 'sudo systemctl disable --now karmo-worker01.service || true'
```

Revoke the durable identity through the store API:

```sh
ssh -t lofason@192.168.1.235 '
sudo -u karmo-gateway /usr/bin/env PYTHONPATH=/opt/karmo/core-service:/opt/karmo/worker-runtime/app /usr/bin/python3 - <<"PY"
from core_service.worker_gateway_runtime import load_gateway_config, build_backend
cfg = load_gateway_config("/etc/karmo/worker-gateway.json", production_permissions=True)
backend = build_backend(cfg)
backend.store.revoke_worker("KARMO-WORKER01")
print("WORKER01_REVOKED")
PY
sudo rm -f /var/lib/karmo-gateway/.ssh/authorized_keys
'
```

Preserve durable worker events, tickets, results, and recovery evidence.

If Core code itself must roll back:

```sh
ssh -t lofason@192.168.1.235 '
set -eu
B=$(ls -1dt /opt/karmo/backups/worker-deploy-* | head -1)
sudo systemctl stop karmo-core.service
sudo rm -rf /opt/karmo/core-service
sudo cp -a "$B/core-service-before" /opt/karmo/core-service
sudo systemctl start karmo-core.service
systemctl is-active karmo-core.service
/usr/local/bin/karmo status
'
```

The additive PR42 durable tables are retained during ordinary rollback for audit and recovery evidence.
