#!/bin/sh
set -eu

CORE_DIR="${KARMO_CORE_DIR:-/opt/karmo/core-service}"
PYTHON_BIN="${KARMO_PYTHON_BIN:-/usr/bin/python3}"

cd "$CORE_DIR"
exec "$PYTHON_BIN" -m core_service chat
