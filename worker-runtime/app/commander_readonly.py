"""Bounded READ-only Commander capability handlers.

This module is intentionally not wired into production registration yet. It is
review material for Commander READ Pack v1. Every operation is fixed or rooted
inside the configured allowed_root; no arbitrary command execution, network
access, secrets access, or writes are permitted.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

from sandbox import SandboxError, resolve_within_sandbox

_MAX_TEXT_BYTES = 32 * 1024
_MAX_DIR_ENTRIES = 200
_ALLOWED_SERVICES = frozenset({
    "karmo-core.service",
    "karmo-worker.service",
    "karmo-worker01.service",
    "karmo-worker02.service",
})


def _require_allowed_root(allowed_root):
    if allowed_root is None:
        raise SandboxError("Commander capability requires configured allowed_root")
    return Path(allowed_root)


def system_snapshot(payload, *, sandbox_root, allowed_root, timeout_seconds):
    del payload, sandbox_root, allowed_root, timeout_seconds
    total, used, free = shutil.disk_usage("/")
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                mem[key] = value.strip()
    except OSError:
        mem = {"available": False}
    output = {
        "hostname": socket.gethostname(),
        "cpu_count": os.cpu_count(),
        "loadavg": list(os.getloadavg()),
        "memory": mem,
        "root_disk": {"total": total, "used": used, "free": free},
    }
    return output, "commander.system_snapshot: bounded host resource read", []


def service_status(payload, *, sandbox_root, allowed_root, timeout_seconds):
    del sandbox_root, allowed_root
    service = payload.get("service")
    if service not in _ALLOWED_SERVICES:
        raise SandboxError("service is not in the Commander fixed allowlist")
    result = subprocess.run(
        ["/usr/bin/systemctl", "is-active", service],
        capture_output=True,
        text=True,
        timeout=min(timeout_seconds, 5),
        shell=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    state = result.stdout.strip() or "unknown"
    output = {"service": service, "state": state, "exit_code": result.returncode}
    return output, f"commander.service_status: {service}={state}", []


def listener_snapshot(payload, *, sandbox_root, allowed_root, timeout_seconds):
    del payload, sandbox_root, allowed_root
    result = subprocess.run(
        ["/usr/bin/ss", "-H", "-lntu"],
        capture_output=True,
        text=True,
        timeout=min(timeout_seconds, 5),
        shell=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    if result.returncode != 0:
        raise SandboxError("listener inspection failed")
    lines = [line[:512] for line in result.stdout.splitlines()[:200]]
    output = {"listeners": lines, "count": len(lines)}
    return output, f"commander.listener_snapshot: {len(lines)} listener(s)", []


def bounded_text_read(payload, *, sandbox_root, allowed_root, timeout_seconds):
    del sandbox_root, timeout_seconds
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload.get("path", ""))
    if not path.is_file():
        raise SandboxError("requested path is not a file in allowed_root")
    raw = path.read_bytes()
    if len(raw) > _MAX_TEXT_BYTES:
        raise SandboxError("requested text file exceeds 32 KiB Commander cap")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandboxError("requested file is not UTF-8 text") from exc
    output = {"path": payload["path"], "text": text, "bytes": len(raw)}
    return output, f"commander.bounded_text_read: {payload['path']} ({len(raw)} bytes)", []


def directory_list(payload, *, sandbox_root, allowed_root, timeout_seconds):
    del sandbox_root, timeout_seconds
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload.get("path", "."))
    if not path.is_dir():
        raise SandboxError("requested path is not a directory in allowed_root")
    entries = []
    for entry in sorted(path.iterdir(), key=lambda item: item.name)[:_MAX_DIR_ENTRIES]:
        entries.append({"name": entry.name, "kind": "dir" if entry.is_dir() else "file"})
    output = {"path": payload.get("path", "."), "entries": entries, "count": len(entries)}
    return output, f"commander.directory_list: {len(entries)} entrie(s)", []
