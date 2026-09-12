"""Bounded READ-only KarmoLab host inspection.

No caller-controlled command execution lives here. Every subprocess argv is
fixed in source, shell=False is mandatory, and failures are returned as bounded
status data rather than promoted into write/recovery behavior.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


class KarmoLabReadError(RuntimeError):
    pass


def _run_fixed(argv: tuple[str, ...], *, timeout: float = 3.0) -> dict:
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "status": type(exc).__name__}
    stdout = (completed.stdout or "")[:16384].strip()
    stderr = (completed.stderr or "")[:2048].strip()
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def _memory_status() -> dict:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {"available": False}
    values: dict[str, int] = {}
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            parts = raw.strip().split()
            if parts and parts[0].isdigit():
                values[key] = int(parts[0]) * 1024
    except OSError as exc:
        return {"available": False, "status": type(exc).__name__}
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    return {
        "available": total is not None,
        "total_bytes": total,
        "available_bytes": available,
    }


def _disk_status() -> dict:
    usage = shutil.disk_usage("/")
    return {
        "path": "/",
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def _service_status() -> dict:
    services = {}
    for unit in ("karmo-core.service", "karmo-worker.service"):
        result = _run_fixed(("systemctl", "is-active", unit))
        services[unit] = {
            "available": result.get("available", False),
            "state": result.get("stdout") or result.get("status") or "unknown",
            "returncode": result.get("returncode"),
        }
    return services


def _container_status() -> dict:
    result = _run_fixed(("docker", "ps", "--format", "{{.Names}}\t{{.Status}}"))
    if not result.get("available"):
        return result
    rows = []
    for line in result.get("stdout", "").splitlines()[:32]:
        name, _, status = line.partition("\t")
        rows.append({"name": name[:128], "status": status[:256]})
    return {
        "available": True,
        "returncode": result.get("returncode"),
        "containers": rows,
        "stderr": result.get("stderr", ""),
    }


def read_status(_arguments: dict | None = None) -> dict:
    """Return bounded, non-secret, READ-only KarmoLab runtime status."""
    load = None
    try:
        load = tuple(round(value, 3) for value in os.getloadavg())
    except (AttributeError, OSError):
        pass
    return {
        "host": {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "load_average": load,
        },
        "memory": _memory_status(),
        "disk": _disk_status(),
        "services": _service_status(),
        "containers": _container_status(),
        "mode": "READ_ONLY",
    }
