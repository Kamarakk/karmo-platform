"""SSH forced-command guard for the KARMO worker stdio gateway.

Deployment must bind one SSH public key to one fixed worker_id in a root-owned
``authorized_keys`` entry, with forwarding, PTY, agent, and user-rc disabled.
This module additionally refuses any client-supplied SSH command before serving
the single stdio request.
"""

from __future__ import annotations

import os

from .worker_stdio_gateway import serve_one


class ForcedCommandError(RuntimeError):
    pass


def serve_forced_command(*, backend, expected_worker_id: str, environ=None,
                         stdin=None, stdout=None) -> int:
    environ = os.environ if environ is None else environ
    original = environ.get("SSH_ORIGINAL_COMMAND", "")
    if original:
        raise ForcedCommandError("client-supplied SSH commands are forbidden")
    if not isinstance(expected_worker_id, str) or not expected_worker_id:
        raise ForcedCommandError("expected worker identity is required")
    return serve_one(
        backend=backend,
        expected_worker_id=expected_worker_id,
        stdin=stdin,
        stdout=stdout,
    )


def authorized_keys_options(*, forced_command_path: str, expected_worker_id: str) -> str:
    """Return the exact restriction prefix to place before a worker public key.

    The caller supplies a root-owned absolute wrapper path. Worker identity is a
    server-side constant, not data supplied by the SSH client.
    """
    if not isinstance(forced_command_path, str) or not forced_command_path.startswith("/"):
        raise ForcedCommandError("forced command path must be absolute")
    if any(char in forced_command_path for char in ('"', "\n", "\r")):
        raise ForcedCommandError("invalid forced command path")
    if not isinstance(expected_worker_id, str) or not expected_worker_id:
        raise ForcedCommandError("expected worker identity is required")
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in expected_worker_id):
        raise ForcedCommandError("invalid worker identity")
    command = f'{forced_command_path} {expected_worker_id}'
    return (
        f'command="{command}",restrict,no-agent-forwarding,no-port-forwarding,'
        'no-X11-forwarding,no-pty,no-user-rc'
    )
