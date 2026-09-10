"""KARMO Worker Runtime -- resource discovery (Phase 4).

Safe, unprivileged, stdlib-only. Every field is labeled VERIFIED (actually
queried on this run) or AVAILABLE-IN-PRINCIPLE (true of the hardware/OS
class in general, not confirmed installed/usable here) -- never silently
conflated, per explicit instruction. No model weights downloaded, no
large installs performed, no elevated privileges required.
"""

import os
import platform
import shutil
import subprocess
import time
from importlib import util as importlib_util


def _run(cmd, timeout=5):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def discover_cpu():
    """VERIFIED: architecture and logical core count, via stdlib +
    macOS/Linux-portable subprocess calls (no elevated privileges)."""
    info = {
        "machine": platform.machine(),  # e.g. "arm64"
        "logical_cpu_count": os.cpu_count(),
        "status": "VERIFIED",
    }
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])  # macOS-specific, best-effort
    if brand:
        info["brand"] = brand
        info["brand_status"] = "VERIFIED"
    else:
        info["brand"] = None
        info["brand_status"] = "NOT_AVAILABLE"
    return info


def discover_memory():
    """VERIFIED on macOS via sysctl (no elevated privileges); falls back
    to NOT_AVAILABLE elsewhere rather than guessing."""
    raw = _run(["sysctl", "-n", "hw.memsize"])
    if raw and raw.isdigit():
        total_bytes = int(raw)
        return {
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / (1024 ** 3), 2),
            "status": "VERIFIED",
        }
    return {"total_bytes": None, "total_gb": None, "status": "NOT_AVAILABLE"}


def discover_disk(path="/"):
    """VERIFIED via shutil.disk_usage -- stdlib, no subprocess needed."""
    usage = shutil.disk_usage(path)
    return {
        "path": path,
        "total_gb": round(usage.total / (1024 ** 3), 2),
        "used_gb": round(usage.used / (1024 ** 3), 2),
        "free_gb": round(usage.free / (1024 ** 3), 2),
        "status": "VERIFIED",
    }


def discover_os():
    """VERIFIED via stdlib platform module."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "mac_version": platform.mac_ver()[0] or None,
        "status": "VERIFIED",
    }


def discover_runtime():
    """VERIFIED -- the Python actually running this process."""
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "status": "VERIFIED",
    }


def discover_uptime():
    """VERIFIED on macOS via sysctl boottime; NOT_AVAILABLE elsewhere
    rather than a portable-but-inaccurate guess."""
    raw = _run(["sysctl", "-n", "kern.boottime"])
    if raw and "sec = " in raw:
        try:
            sec = int(raw.split("sec = ")[1].split(",")[0])
            uptime_seconds = time.time() - sec
            return {"uptime_seconds": round(uptime_seconds), "status": "VERIFIED"}
        except Exception:
            pass
    return {"uptime_seconds": None, "status": "NOT_AVAILABLE"}


def discover_acceleration():
    """Apple Silicon acceleration surface -- strictly VERIFIED (actually
    importable/queryable this run) vs. AVAILABLE-IN-PRINCIPLE (true of
    this chip class per public specs, not confirmed usable here). Never
    assumes Neural Engine support where the software stack cannot
    actually use it -- explicit instruction."""
    machine = platform.machine()
    is_apple_silicon = platform.system() == "Darwin" and machine == "arm64"

    result = {
        "apple_silicon": is_apple_silicon,
        "apple_silicon_status": "VERIFIED",
    }

    # Metal: query via system_profiler (unprivileged, slow-ish but safe).
    metal_output = _run(["system_profiler", "SPDisplaysDataType"], timeout=15)
    if metal_output and "Metal" in metal_output:
        metal_line = next((l.strip() for l in metal_output.splitlines() if "Metal" in l), None)
        result["metal_support"] = metal_line
        result["metal_status"] = "VERIFIED"
    else:
        result["metal_support"] = None
        result["metal_status"] = "NOT_AVAILABLE"

    # Neural Engine: no unprivileged, install-free stdlib/system_profiler
    # path confirms actual ANE availability to a Python process -- report
    # AVAILABLE-IN-PRINCIPLE only, never claim VERIFIED.
    result["neural_engine"] = "AVAILABLE-IN-PRINCIPLE" if is_apple_silicon else "NOT_APPLICABLE"

    # MLX: only VERIFIED if actually importable right now -- never
    # installed by this discovery step.
    mlx_spec = importlib_util.find_spec("mlx")
    result["mlx_installed"] = mlx_spec is not None
    result["mlx_status"] = "VERIFIED" if mlx_spec is not None else "NOT_INSTALLED"

    # Ollama: only VERIFIED if the binary is actually on PATH right now.
    ollama_path = shutil.which("ollama")
    result["ollama_installed"] = ollama_path is not None
    result["ollama_status"] = "VERIFIED" if ollama_path is not None else "NOT_INSTALLED"

    return result


def full_report():
    return {
        "cpu": discover_cpu(),
        "memory": discover_memory(),
        "disk": discover_disk(),
        "os": discover_os(),
        "runtime": discover_runtime(),
        "uptime": discover_uptime(),
        "acceleration": discover_acceleration(),
    }
