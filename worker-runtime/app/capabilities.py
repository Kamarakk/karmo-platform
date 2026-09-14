"""KARMO Worker Runtime -- capability handlers (Phase 9).

Every function here is registered against exactly one capability_id from
capability_manifest.SAFE_CAPABILITIES, via sandbox.register_handler, at
import time. No handler accepts an arbitrary path outside its
allowed_root, no handler shells out to an arbitrary command, no handler
touches production data. All read access to pre-existing files is bounded
to the explicitly-scoped allowed_root workspace via
sandbox.resolve_within_sandbox.
"""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

import resource_discovery
from commander_readonly import bounded_text_read, directory_list, listener_snapshot, service_status, system_snapshot
from sandbox import SandboxError, register_handler, resolve_within_sandbox

# Prefer the worker-runtime's own venv when it exists. GitHub-hosted CI does
# not create that repo-local venv, so fall back only to the interpreter that
# is already executing this trusted KARMO process. The job payload can never
# choose or override this path.
_VENV_PYTHON = Path(__file__).resolve().parent.parent / "venv" / "bin" / "python"

# Only operationally necessary, non-secret process settings may cross into a
# capability subprocess. In particular, PYTHONPATH, tokens, cloud credentials,
# SSH agent variables, and arbitrary user environment are never inherited.
_SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")


def _trusted_python_interpreter():
    """Return a KARMO-controlled Python interpreter path.

    Production/dev prefers the Worker Runtime virtualenv. Portable test/CI
    environments may not have that venv, so the only allowed fallback is the
    current process interpreter (sys.executable), resolved to an absolute path.
    Never accepts a job-supplied path and fails closed if neither interpreter is
    executable.
    """
    candidates = (_VENV_PYTHON, Path(sys.executable).resolve())
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SandboxError("no trusted executable Python interpreter is available -- refused")


def _safe_subprocess_env(source=None):
    source = os.environ if source is None else source
    env = {key: source[key] for key in _SAFE_ENV_KEYS if key in source}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _require_allowed_root(allowed_root):
    if allowed_root is None:
        raise SandboxError("this capability requires an allowed_root workspace to be configured")
    return Path(allowed_root)


# --- A. HASH VERIFY -------------------------------------------------------
def _hash_verify(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload["path"])
    if not path.is_file():
        raise SandboxError(f"file not found within allowed workspace: {payload['path']!r}")

    sha256 = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(block)
    digest = sha256.hexdigest()

    output = {"sha256": digest, "path": payload["path"]}
    summary = f"hash_verify: {payload['path']} -> {digest}"
    return output, summary, []


register_handler("hash_verify", _hash_verify)


# --- B. PYTEST JOB ----------------------------------------------------------
def _pytest_job(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    test_dir = resolve_within_sandbox(root, payload["test_dir"])
    if not test_dir.is_dir():
        raise SandboxError(f"test_dir not found within allowed workspace: {payload['test_dir']!r}")

    result = subprocess.run(
        [str(_trusted_python_interpreter()), "-m", "pytest", "-v", str(test_dir)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=str(sandbox_root),
        env=_safe_subprocess_env(),
    )
    summary_lines = result.stdout.strip().splitlines()[-15:]
    output = {"exit_code": result.returncode, "summary": "\n".join(summary_lines)}
    return output, "\n".join(summary_lines), []


register_handler("pytest", _pytest_job)


# --- C. STATIC PYTHON VALIDATION --------------------------------------------
def _static_analysis(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    errors = []
    checked = []

    for rel_path in payload["files"]:
        path = resolve_within_sandbox(root, rel_path)
        if not path.is_file():
            errors.append(f"{rel_path}: not found")
            continue
        result = subprocess.run(
            [str(_trusted_python_interpreter()), "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=_safe_subprocess_env(),
        )
        checked.append(rel_path)
        if result.returncode != 0:
            errors.append(f"{rel_path}: {result.stderr.strip()[:200]}")

    output = {"ok": len(errors) == 0, "errors": errors, "checked": checked}
    summary = f"static_analysis: {len(checked)} file(s) checked, {len(errors)} error(s)"
    return output, summary, []


register_handler("static_analysis", _static_analysis)


# --- D. REPOSITORY ANALYSIS -------------------------------------------------
def _repository_analysis(payload, *, sandbox_root, allowed_root, timeout_seconds):
    root = _require_allowed_root(allowed_root)
    repo_path = resolve_within_sandbox(root, payload["repo_path"])
    if not repo_path.is_dir():
        raise SandboxError(f"repo_path not found within allowed workspace: {payload['repo_path']!r}")

    file_count = 0
    total_bytes = 0
    max_files = 10_000

    for entry in repo_path.rglob("*"):
        if entry.is_file():
            file_count += 1
            total_bytes += entry.stat().st_size
            if file_count >= max_files:
                break

    output = {"file_count": file_count, "total_bytes": total_bytes}
    summary = f"repository_analysis: {file_count} file(s), {total_bytes} byte(s)"
    return output, summary, []


register_handler("repository_analysis", _repository_analysis)


# --- E. RESOURCE BENCHMARK --------------------------------------------------
def _resource_benchmark(payload, *, sandbox_root, allowed_root, timeout_seconds):
    iterations = min(int(payload.get("iterations", 100_000)), 5_000_000)

    start = time.monotonic()
    total = 0
    for i in range(iterations):
        total += hash(i) & 0xFFFF
    elapsed = time.monotonic() - start

    output = {"elapsed_seconds": round(elapsed, 4), "iterations": iterations, "checksum": total}
    summary = f"resource_benchmark: {iterations} iterations in {elapsed:.4f}s"
    return output, summary, []


register_handler("resource_benchmark", _resource_benchmark)


# --- Optional probes ---------------------------------------------------
def _media_probe_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    acceleration = resource_discovery.discover_acceleration()
    output = {
        "metal_available": acceleration["metal_status"] == "VERIFIED",
        "metal_support": acceleration.get("metal_support"),
    }
    return output, f"media_probe_test: metal_status={acceleration['metal_status']}", []


register_handler("media_probe_test", _media_probe_test)


def _local_model_probe(payload, *, sandbox_root, allowed_root, timeout_seconds):
    acceleration = resource_discovery.discover_acceleration()
    output = {
        "mlx_installed": acceleration["mlx_installed"],
        "ollama_installed": acceleration["ollama_installed"],
    }
    return output, (
        f"local_model_probe: mlx={acceleration['mlx_status']}, ollama={acceleration['ollama_status']}"
    ), []


register_handler("local_model_probe", _local_model_probe)


def _document_processing_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    """Synthetic chunking simulation for the bounded document job path."""
    root = _require_allowed_root(allowed_root)
    path = resolve_within_sandbox(root, payload["path"])
    if not path.is_file():
        raise SandboxError(f"file not found within allowed workspace: {payload['path']!r}")

    text = path.read_text(encoding="utf-8")
    chunk_size = 200
    chunk_count = max(1, (len(text) + chunk_size - 1) // chunk_size)

    output = {"chunk_count": chunk_count, "char_count": len(text)}
    return output, f"document_processing_test: {chunk_count} synthetic chunk(s)", []


register_handler("document_processing_test", _document_processing_test)


def _embedding_benchmark_test(payload, *, sandbox_root, allowed_root, timeout_seconds):
    """Synthetic bounded vector-op benchmark; no model weights are downloaded."""
    vector_count = min(int(payload.get("vector_count", 100)), 10_000)
    dim = 64

    start = time.monotonic()
    vectors = [
        [((hashlib.sha256(f"{i}:{j}".encode()).digest()[0]) / 255.0) for j in range(dim)]
        for i in range(vector_count)
    ]
    _ = sum(sum(a * b for a, b in zip(vectors[0], v)) for v in vectors[1:])
    elapsed = time.monotonic() - start

    output = {"elapsed_seconds": round(elapsed, 4), "vector_count": vector_count, "dim": dim}
    return output, f"embedding_benchmark_test: {vector_count} synthetic vectors in {elapsed:.4f}s", []


register_handler("embedding_benchmark_test", _embedding_benchmark_test)

# Commander READ Pack v1 -- fixed handlers only; no arbitrary command dispatch.
register_handler("commander.system_snapshot", system_snapshot)
register_handler("commander.service_status", service_status)
register_handler("commander.listener_snapshot", listener_snapshot)
register_handler("commander.bounded_text_read", bounded_text_read)
register_handler("commander.directory_list", directory_list)
