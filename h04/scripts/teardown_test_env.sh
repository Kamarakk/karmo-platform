#!/usr/bin/env bash
# Tear down the isolated H0.4 test stack only. This targets exclusively the
# containers/volumes defined in h04/docker-compose.yml (name prefix
# "karmo-h04-test"). It never touches production hosts, containers, or data.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

docker compose -f docker-compose.yml down -v
echo "H0.4 isolated test stack removed (containers + volumes)."
