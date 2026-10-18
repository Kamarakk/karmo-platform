#!/usr/bin/env bash
# ONE-TIME on AI01, as root: finish the "Ask Claude" fix (PR 155).
#
# The code that runs the claude CLI as the locked-down karmo-ask account is
# already deployed, but deploy_core.sh never installs unit files, so the live
# karmo-webui.service has no KARMO_DELEGATE_CLI_USER and root cannot find
# `claude`. This script, idempotently:
#   1. creates the system user karmo-ask (home /var/lib/karmo-ask, no sudo)
#   2. installs the claude CLI binary to /usr/local/bin/claude (755)
#   3. adds a karmo-webui drop-in setting KARMO_DELEGATE_CLI_USER (the live
#      unit is left as is) and restarts the web UI
#   4. checks karmo-ask cannot read /etc/karmo/core
# The Claude login itself is interactive and stays with the owner:
#   sudo -u karmo-ask -H /usr/local/bin/claude   ->  /login, approve, /exit
#
#   ask_claude_setup.sh [path-to-claude-binary]
# Default binary: the newest version under /home/*/.local/share/claude/versions/.
set -euo pipefail

USER_NAME=karmo-ask
HOME_DIR=/var/lib/karmo-ask
DROPIN_DIR=/etc/systemd/system/karmo-webui.service.d
DROPIN="$DROPIN_DIR/ask-claude.conf"
SECRETS=/etc/karmo/core

[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }

SRC_BIN="${1:-}"
if [ -z "$SRC_BIN" ]; then
  SRC_BIN="$(find /home/*/.local/share/claude/versions -maxdepth 1 -type f 2>/dev/null | sort -V | tail -1 || true)"
fi
[ -n "$SRC_BIN" ] && [ -f "$SRC_BIN" ] && [ -x "$SRC_BIN" ] || { echo "claude binary not found; pass its path"; exit 1; }
grep -q "CLI_USER_ENV" /opt/karmo/core-service/core_service/delegation_runner.py 2>/dev/null \
  || { echo "deployed core has no delegation_runner; deploy main first"; exit 1; }

echo "== 1. user"
if id "$USER_NAME" >/dev/null 2>&1; then
  echo "exists: $(id "$USER_NAME")"
else
  useradd --system --create-home --home-dir "$HOME_DIR" --shell /bin/bash "$USER_NAME"
  id "$USER_NAME"
fi
chmod 700 "$HOME_DIR"

echo "== 2. claude CLI from $SRC_BIN"
install -m 755 -o root -g root "$SRC_BIN" /usr/local/bin/claude
/usr/local/bin/claude --version || true

echo "== 3. web UI drop-in"
mkdir -p "$DROPIN_DIR"
printf '[Service]\nEnvironment=KARMO_DELEGATE_CLI_USER=%s\n' "$USER_NAME" >"$DROPIN"
chmod 644 "$DROPIN"
systemctl daemon-reload
systemctl restart karmo-webui.service
sleep 3
systemctl is-active karmo-webui.service
systemctl show -p Environment karmo-webui.service | tr ' ' '\n' | grep "KARMO_DELEGATE_CLI_USER=$USER_NAME"
echo "undo: rm $DROPIN && systemctl daemon-reload && systemctl restart karmo-webui"

echo "== 4. secrets stay unreadable"
if sudo -u "$USER_NAME" test -r "$SECRETS" -a -x "$SECRETS"; then
  echo "WARNING: $USER_NAME can read $SECRETS"; exit 1
fi
echo "ok: $USER_NAME cannot read $SECRETS"

if [ -s "$HOME_DIR/.claude/.credentials.json" ] || [ -s "$HOME_DIR/.claude.json" ]; then
  echo "== done (a Claude login already exists for $USER_NAME)"
else
  echo "== done. Next, log Claude in once: sudo -u $USER_NAME -H /usr/local/bin/claude  (/login, then /exit)"
fi
