"""How ask_claude/ask_gpt spawn their CLIs: which binary, as which user.

Why this exists (live finding, 2026-10-11): karmo-webui runs as root, so
``subprocess.run(["claude", ...])`` resolved against root's systemd PATH.
The claude CLI was only ever installed under one login user's
``~/.local/bin``, so every hand-off failed with "No such file or
directory: 'claude'" (journal, 2026-10-06). codex *did* resolve, from
``/usr/local/bin``, which meant it ran as root and could read anything,
including ``/etc/karmo/core/*``.

Fix, in one place for both capabilities:

* the binary is configurable (``KARMO_CLAUDE_BIN`` / ``KARMO_CODEX_BIN``),
  defaulting to the bare name so dev/test behaviour is unchanged;
* when ``KARMO_DELEGATE_CLI_USER`` names a dedicated (non-root) account,
  the CLI runs as that user with that user's HOME, a minimal environment,
  and no inherited supplementary groups. ``/etc/karmo/core`` is mode 700
  root, so the dedicated user cannot read it. The per-call temp workdir
  is handed to that user so the CLI can ``cd`` into it and read the one
  caller-supplied image file.

Dropping privileges this way only works while the parent is root; if the
web UI is ever moved to its own non-root user, the hand-off must switch
to a sudoers rule instead -- ``run_kwargs`` raises clearly rather than
silently running the CLI as the service user.
"""

from __future__ import annotations

import os
import pwd
from typing import Any

CLI_USER_ENV = "KARMO_DELEGATE_CLI_USER"
CLAUDE_BIN_ENV = "KARMO_CLAUDE_BIN"
CODEX_BIN_ENV = "KARMO_CODEX_BIN"

_BASE_PATH = "/usr/local/bin:/usr/bin:/bin"


class DelegationRunnerError(RuntimeError):
    pass


def claude_binary() -> str:
    return os.environ.get(CLAUDE_BIN_ENV, "").strip() or "claude"


def codex_binary() -> str:
    return os.environ.get(CODEX_BIN_ENV, "").strip() or "codex"


def _dedicated_user() -> pwd.struct_passwd | None:
    name = os.environ.get(CLI_USER_ENV, "").strip()
    if not name:
        return None
    try:
        entry = pwd.getpwnam(name)
    except KeyError as exc:
        raise DelegationRunnerError(f"{CLI_USER_ENV}={name!r} is not an existing user") from exc
    if entry.pw_uid == 0:
        raise DelegationRunnerError(f"{CLI_USER_ENV} must not be root")
    return entry


def run_kwargs(workdir: str) -> dict[str, Any]:
    """Extra keyword arguments for ``subprocess.run`` of a delegation CLI.

    With no dedicated user configured this is empty, so the call inherits
    the parent's environment exactly as before. With one configured, the
    workdir is chowned to that user and the call drops to it.
    """
    entry = _dedicated_user()
    if entry is None:
        return {}
    if os.geteuid() != 0:
        raise DelegationRunnerError(
            f"{CLI_USER_ENV} is set but this process is not root, so it cannot switch user"
        )
    os.chown(workdir, entry.pw_uid, entry.pw_gid)
    env = {
        "HOME": entry.pw_dir,
        "USER": entry.pw_name,
        "LOGNAME": entry.pw_name,
        "PATH": f"{entry.pw_dir}/.local/bin:{_BASE_PATH}",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": "dumb",
    }
    return {
        "user": entry.pw_uid,
        "group": entry.pw_gid,
        "extra_groups": [],
        "env": env,
    }
