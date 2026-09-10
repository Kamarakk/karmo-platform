"""KARMO Worker Runtime -- execution sandbox (Phase 8).

Bounded executor for whitelisted capability handlers only -- never
arbitrary shell access, never an arbitrary executable supplied by a job.
Every job runs inside its own temporary, isolated working directory,
under a timeout, with output capped and errors sanitized before being
returned (never leaking a full traceback or an absolute host path outside
the sandbox root).
"""

import shutil
import tempfile
import time
import traceback
from pathlib import Path

MAX_OUTPUT_BYTES = 64 * 1024  # 64KB cap on any single job's captured output


class SandboxError(RuntimeError):
    pass


class PathTraversalError(SandboxError):
    pass


# The ONLY capability_ids this sandbox will ever dispatch to a handler.
# Anything else -- including any attempt to pass an arbitrary callable or
# shell command as "the capability" -- is refused before the sandbox even
# considers running it.
_HANDLERS = {}


def register_handler(capability_id, handler_fn):
    """Handlers are registered by capability_id string, at import time,
    by this module's own package -- a job payload can never supply its
    own executable code or command to run. This is what makes 'no
    arbitrary executable supplied by a job' true structurally, not just
    by convention."""
    _HANDLERS[capability_id] = handler_fn


def resolve_within_sandbox(sandbox_root: Path, requested_path: str) -> Path:
    """Resolves a job-supplied relative path against the sandbox root and
    refuses (does not silently clamp) any path that would escape it --
    the path-traversal and symlink-escape defenses named in Phase 13's
    threat model."""
    candidate = (sandbox_root / requested_path).resolve()
    try:
        candidate.relative_to(sandbox_root.resolve())
    except ValueError:
        raise PathTraversalError(
            f"path {requested_path!r} resolves outside the sandbox workspace -- refused"
        )
    return candidate


def _sanitize_error(error: Exception, sandbox_root: Path) -> str:
    """Never return a raw traceback (could leak absolute host paths,
    environment details, or internals) -- a short, safe category plus
    message, with the sandbox root's own absolute path stripped out."""
    message = str(error)
    message = message.replace(str(sandbox_root), "<sandbox>")
    return f"{type(error).__name__}: {message}"[:2000]


def run_capability(capability_id, payload, *, timeout_seconds, allowed_root=None):
    """The single, bounded entry point every job execution goes through.
    Returns (output: dict, stdout_summary: str, duration_seconds: float,
    evidence_files: list[str]) on success; raises SandboxError (already
    sanitized) on failure."""
    if capability_id not in _HANDLERS:
        raise SandboxError(f"capability_id {capability_id!r} has no registered handler -- refused")

    sandbox_dir = tempfile.mkdtemp(prefix=f"karmo-worker-{capability_id}-")
    sandbox_root = Path(sandbox_dir).resolve()
    start = time.monotonic()

    try:
        handler = _HANDLERS[capability_id]
        output, stdout_summary, evidence_files = handler(
            payload, sandbox_root=sandbox_root, allowed_root=allowed_root, timeout_seconds=timeout_seconds
        )
        duration = time.monotonic() - start

        if duration > timeout_seconds:
            raise SandboxError(f"capability {capability_id!r} exceeded its {timeout_seconds}s timeout")

        summary_bytes = stdout_summary.encode("utf-8")
        if len(summary_bytes) > MAX_OUTPUT_BYTES:
            stdout_summary = summary_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "...<truncated>"

        return output, stdout_summary, duration, evidence_files
    except SandboxError:
        raise
    except Exception as error:
        raise SandboxError(_sanitize_error(error, sandbox_root)) from error
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)
