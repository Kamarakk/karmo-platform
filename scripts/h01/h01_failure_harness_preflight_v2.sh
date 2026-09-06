#!/usr/bin/env bash
set -euo pipefail
umask 077

H="/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z"
BUILD="$H/h01-build-v1"
T="$H/h01-failure-harness-v1"
MANIFEST="$T/MANIFEST-H01-FAILURE-PREFLIGHT.sha256"
TMP="$(mktemp "$H/.MANIFEST-H01-FAILURE-PREFLIGHT.tmp.XXXXXX")"
trap 'rm -f -- "$TMP"' EXIT

case "$H" in
  /home/lofason/karmo-ai/hardening/h0.1/implementation-*) ;;
  *) printf 'STOP: unexpected implementation path.\n'; exit 1 ;;
esac

test -d "$BUILD"
test -f "$BUILD/MANIFEST-H01-ISOLATED-BUILD.sha256"

# Recover only the known incomplete harness from the failed preflight attempt.
rm -rf -- "$T"

(
  cd "$H"
  sha256sum -c h01-build-v1/MANIFEST-H01-ISOLATED-BUILD.sha256 >/dev/null
)

docker exec karmo-postgres pg_isready -U karmo -d karmo >/dev/null
test "$(docker exec karmo-postgres psql -U karmo -d karmo -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'karmo_outbox';")" = "0"

check_points() {
  curl -fsS "http://127.0.0.1:6333/collections/$1" |
    tr -d '[:space:]' |
    grep -q "\"points_count\":$2"
}
check_points karmo_semantic_memory 4
check_points karmo_documents 8
check_points karmo_h00_dense_baseline 8

mkdir -p -- "$T/reports" "$T/runner"
printf '%s\n' \
  'phase=H0.1 Transactional Outbox' \
  'activity=isolated failure-matrix preflight' \
  'workspace_only=YES' \
  'production_public_outbox=ABSENT' \
  'production_qdrant_baseline=semantic_memory:4,documents:8,h00_dense_baseline:8' \
  'production_database_writes=0' \
  'production_schema_changes=0' \
  'production_qdrant_writes=0' \
  'live_application_changes=0' \
  'container_restarts=0' \
  'service_installations=0' \
  'next=build isolated H01-T01 through H01-T18 runner' > "$T/SCOPE.txt"

printf 'h01_failure_harness_preflight=PASS\nh01_build_manifest=PASS\nproduction_public_outbox=ABSENT\nproduction_qdrant_baseline=semantic_memory:4,documents:8,h00_dense_baseline:8\nharness_directory=%s\nproduction_database_writes=0\nproduction_schema_changes=0\nproduction_qdrant_writes=0\nlive_application_changes=0\ncontainer_restarts=0\nservice_installations=0\n' "$T" > "$T/reports/preflight-summary.txt"

(
  cd "$T"
  find . -type f -print0 | sort -z | xargs -0 sha256sum
) > "$TMP"
mv -- "$TMP" "$MANIFEST"
chmod 0444 "$T/SCOPE.txt" "$T/reports/preflight-summary.txt" "$MANIFEST"
(
  cd "$T"
  sha256sum -c MANIFEST-H01-FAILURE-PREFLIGHT.sha256 >/dev/null
)

printf 'H0.1 FAILURE-HARNESS PREFLIGHT COMPLETE\n'
cat "$T/reports/preflight-summary.txt"
printf 'manifest=%s\nmanifest_check=PASS\nSTOP HERE FOR H0.1 TEST-HARNESS BUILD\n' "$MANIFEST"
trap - EXIT
