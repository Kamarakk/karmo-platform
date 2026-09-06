#!/usr/bin/env bash
# Bring up the isolated H0.1 failure-matrix test stack: local Docker
# PostgreSQL + Qdrant, a Python virtualenv, the frozen H0.1 migrations,
# and the isolated Qdrant test collection. Synthetic data only. No
# production host, credential, or data is touched.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PG_HOST="127.0.0.1"
PG_PORT="55432"
PG_DB="karmo_h01_test"
PG_USER="karmo_h01_test"
PG_PASSWORD="karmo_h01_test_synthetic_local_only"
QDRANT_URL="http://127.0.0.1:56333"
COLLECTION="karmo_semantic_memory"
VECTOR_SIZE=768

echo "== starting isolated docker compose stack =="
docker compose -f docker-compose.yml up -d

echo "== waiting for postgres =="
for _ in $(seq 1 60); do
  if docker exec karmo-h01-test-postgres pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec karmo-h01-test-postgres pg_isready -U "$PG_USER" -d "$PG_DB"

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

echo "== applying frozen H0.1 migrations (isolated schema, synthetic data only) =="
export PGPASSWORD="$PG_PASSWORD"
psql_docker() {
  docker exec -i -e PGPASSWORD="$PG_PASSWORD" karmo-h01-test-postgres \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB" "$@"
}
psql_docker -c "DROP TABLE IF EXISTS public.karmo_outbox;"
psql_docker -c "DROP TABLE IF EXISTS public.conversation_memory;"
psql_docker -f - < app/migrations/000_synthetic_conversation_memory.sql
psql_docker -f - < app/migrations/001_h01_karmo_outbox.sql

echo "== creating isolated qdrant test collection =="
curl -fsS -X DELETE "$QDRANT_URL/collections/$COLLECTION" >/dev/null 2>&1 || true
curl -fsS -X PUT "$QDRANT_URL/collections/$COLLECTION" \
  -H 'Content-Type: application/json' \
  -d "{\"vectors\": {\"size\": $VECTOR_SIZE, \"distance\": \"Cosine\"}}" >/dev/null

echo "H0.1 isolated test environment ready."
echo "postgres=$PG_HOST:$PG_PORT/$PG_DB"
echo "qdrant=$QDRANT_URL collection=$COLLECTION"
