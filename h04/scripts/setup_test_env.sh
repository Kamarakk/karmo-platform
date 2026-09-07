#!/usr/bin/env bash
# Bring up the isolated H0.4 integrity/reconciliation test stack: local
# Docker PostgreSQL + Qdrant, a Python virtualenv, and the frozen H0.4
# document_registry migration. Synthetic data only. No production host,
# credential, or data is touched.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PG_HOST="127.0.0.1"
PG_PORT="57432"
PG_DB="karmo_h04_test"
PG_USER="karmo_h04_test"
PG_PASSWORD="karmo_h04_test_synthetic_local_only"
QDRANT_URL="http://127.0.0.1:58333"

echo "== starting isolated docker compose stack =="
docker compose -f docker-compose.yml up -d

echo "== waiting for postgres =="
for _ in $(seq 1 60); do
  if docker exec karmo-h04-test-postgres pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec karmo-h04-test-postgres pg_isready -U "$PG_USER" -d "$PG_DB"

echo "== waiting for qdrant =="
for _ in $(seq 1 60); do
  if curl -fsS "$QDRANT_URL/readyz" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "$QDRANT_URL/readyz" >/dev/null

echo "== creating python virtualenv =="
if [ ! -d venv ]; then
  python3 -m venv venv
fi
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

echo "== applying frozen H0.4 document_registry migration =="
export PGPASSWORD="$PG_PASSWORD"
psql_docker() {
  docker exec -i -e PGPASSWORD="$PG_PASSWORD" karmo-h04-test-postgres \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB" "$@"
}
psql_docker -c "DROP TABLE IF EXISTS public.document_registry;"
psql_docker -f - < app/migrations/001_h04_document_registry.sql

echo "H0.4 isolated test environment ready."
echo "postgres=$PG_HOST:$PG_PORT/$PG_DB"
echo "qdrant=$QDRANT_URL"
