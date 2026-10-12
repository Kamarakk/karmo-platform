#!/usr/bin/env bash
# Deploys core-service from origin/main to AI01 in one command, so what is
# merged is what runs (2026-10-11: a merged fix was found never deployed).
#
#   scripts/deploy_core.sh            # deploy origin/main
#   scripts/deploy_core.sh --dry-run  # tests + package only
#
# Steps: fetch main -> tests must pass -> package core-service -> copy to AI01
# -> back up the running copy -> install -> write DEPLOY_SHA -> restart ->
# /health must report the new commit. Database migrations are NOT applied:
# any new migration file is listed and the deploy stops for a human to run it.
# Undo: the BACKUP path printed below (cp -a it back and restart).
set -euo pipefail

HOST="${KARMO_AI01:-karmo-ai01}"
HEALTH_URL="${KARMO_HEALTH_URL:-https://karmo-ai01.tail2d74d7.ts.net:8787/health}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

cd "$REPO"
git fetch -q origin main
SHA="$(git rev-parse origin/main)"
SHORT="${SHA:0:7}"
echo "== deploying origin/main $SHORT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git archive origin/main | tar -x -C "$WORK"   
echo "== tests"
(cd "$WORK/core-service" && python3 -m pytest -q tests/ >"$WORK/tests.log" 2>&1) \
  || { tail -20 "$WORK/tests.log"; echo "TESTS FAILED: not deploying"; exit 1; }
tail -1 "$WORK/tests.log"

echo "$SHA" >"$WORK/core-service/DEPLOY_SHA"
COPYFILE_DISABLE=1 tar -czf "$WORK/core.tar.gz" -C "$WORK/core-service" .   # no macOS ._ files on AI01

echo "== migrations"
LIVE_MIGRATIONS="$(ssh -n -o BatchMode=yes "$HOST" 'ls /opt/karmo/core-service/core_service/migrations 2>/dev/null' || true)"
NEW_MIGRATIONS="$(comm -13 <(echo "$LIVE_MIGRATIONS" | sort) <(ls "$WORK/core-service/core_service/migrations" | sort))"
if [ -n "$NEW_MIGRATIONS" ]; then
  echo "New migration(s) not yet on AI01:"; echo "$NEW_MIGRATIONS"
  if [ "${KARMO_MIGRATIONS_APPLIED:-0}" != "1" ]; then
    echo "Apply them first, then rerun with KARMO_MIGRATIONS_APPLIED=1."; exit 1
  fi
fi

[ "$DRY_RUN" = 1 ] && { echo "== dry run done"; exit 0; }

echo "== install on $HOST"
scp -q -o BatchMode=yes "$WORK/core.tar.gz" "$HOST:/tmp/karmo-core-$SHORT.tar.gz"
ssh -n -o BatchMode=yes "$HOST" "set -e
TS=\$(date -u +%Y%m%dT%H%M%SZ); B=/opt/karmo/backups/core-deploy-$SHORT-\$TS
sudo -n mkdir -p \$B && sudo -n cp -a /opt/karmo/core-service \$B/core-service-before && echo BACKUP=\$B
rm -rf /tmp/kcs-$SHORT && mkdir /tmp/kcs-$SHORT && tar -xzf /tmp/karmo-core-$SHORT.tar.gz -C /tmp/kcs-$SHORT
sudo -n cp -a /tmp/kcs-$SHORT/. /opt/karmo/core-service/
rm -rf /tmp/kcs-$SHORT /tmp/karmo-core-$SHORT.tar.gz
sudo -n systemctl restart karmo-core.service karmo-webui.service
sleep 5; systemctl is-active karmo-core.service karmo-webui.service"

echo "== health"
for _ in 1 2 3 4 5 6; do
  if curl -fsS -m 10 "$HEALTH_URL" >"$WORK/health.json" 2>/dev/null; then break; fi
  sleep 5
done
cat "$WORK/health.json"; echo
grep -q "\"deployed_sha\": \"$SHA\"" "$WORK/health.json" \
  && echo "== OK: AI01 runs $SHORT" \
  || { echo "HEALTH CHECK FAILED: AI01 is not reporting $SHORT"; exit 1; }
