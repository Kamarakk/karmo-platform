"""KARMO Worker Runtime -- execution sandbox (Phase 8).

Bounded executor for whitelisted capability handlers only -- never
arbitrary shell access, never an arbitrary executable supplied by a job.
Every job runs inside its own temporary, isolated working directory, in
its own OS process under a hard deadline, with output capped and errors
sanitized before being returned (never leaking a full traceback or an
absolute host path outside the sandbox root).

Timeout enforcement is REAL: the handler runs in a forked child process;
if it has not finished by `timeout_seconds`, the child is terminated
(SIGTERM then SIGKILL) and the call fails closed with SandboxError -- not
a post-return elapsed-time check, which cannot actually stop a
runaway/hung handler. Fixed after independent review found the prior
implementation only measured wall-clock time after the handler had
already returned, meaning a handler that hangs (or simply runs long)
was never actually interrupted.
"""

import json
import multiprocessing
import shutil
import tempfile
import time
from pathlib import Path

MAX_OUTPUT_BYTES = 64 * 1024  # 64KB cap on stdout_summary (free text -- truncated, not refused)
MAX_RESULT_BYTES = 64 * 1024  # 64KB cap on the serialized `output` dict -- structured, so refused, not truncated
MAX_EVIDENCE_FILES = 20  # cap on the number of evidence file references a handler may return

_TERMINATE_GRACE_SECONDS = 2  # time given to a terminated child before escalating to kill()


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


def _sanitize_message(message: str, sandbox_root: Path) -> str:
    """Never return a raw traceback (could leak absolute host paths,
    environment details, or internals) -- a short, safe message, with the
    sandbox root's own absolute path stripped out."""
    message = message.replace(str(sandbox_root), "<sandbox>")
    return message[:2000]


def _handler_worker(handler, payload, sandbox_root, allowed_root, timeout_seconds, conn):
    """Runs INSIDE the spawned child process. Sends ("ok", (output,
    stdout_summary, evidence_files)) or ("error", exception_instance) back
    to the parent over the pipe, then exits. The child is a fresh
    interpreter (not a fork), so `handler` must be picklable by reference
    (a module-level function, as every handler in capabilities.py already
    is) -- it re-imports its own module state rather than inheriting the
    parent's in-memory objects."""
    try:
        result = handler(payload, sandbox_root=sandbox_root, allowed_root=allowed_root, timeout_seconds=timeout_seconds)
        conn.send(("ok", result))
    except BaseException as exc:  # noqa: BLE001 -- must report every failure mode back to the parent, then exit
        conn.send(("error", exc))
    finally:
        conn.close()


def run_capability(capability_id, payload, *, timeout_seconds, allowed_root=None):
    """The single, bounded entry point every job execution goes through.
    Returns (output: dict, stdout_summary: str, duration_seconds: float,
    evidence_files: list[str]) on success; raises SandboxError (already
    sanitized) on failure -- including a real, enforced timeout, never
    merely a post-hoc elapsed-time check."""
    if capability_id not in _HANDLERS:
        raise SandboxError(f"capability_id {capability_id!r} has no registered handler -- refused")

    handler = _HANDLERS[capability_id]
    sandbox_dir = tempfile.mkdtemp(prefix=f"karmo-worker-{capability_id}-")
    sandbox_root = Path(sandbox_dir).resolve()

    # "spawn", not "fork": a long-lived worker process makes thousands of
    # subprocess/SSH round trips between jobs, and CPython's subprocess
    # implementation can leave short-lived reader threads in flight. fork()
    # only clones the calling thread -- if another thread held a lock at the
    # instant of the fork, the child inherits that lock permanently held with
    # no thread left alive to release it, and can deadlock forever with no
    # exception anywhere (the child never gets far enough to hit its own
    # error handling). spawn starts a clean interpreter with no inherited
    # thread/lock state, eliminating that class of hang. The cost: the
    # handler, payload, and sandbox_root must be picklable (module-level
    # functions and plain data -- true of every handler in capabilities.py)
    # and the child re-imports everything itself rather than inheriting the
    # parent's in-memory state.
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_handler_worker,
        args=(handler, payload, sandbox_root, allowed_root, timeout_seconds, child_conn),
    )

    try:
        start = time.monotonic()
        try:
            process.start()
        except (TypeError, ValueError, AttributeError) as exc:
            # pickle failures surface as one of these from multiprocessing's
            # spawn path (e.g. a locally-defined/closure handler) -- report
            # them the same way every other refusal in this module is
            # reported, never as a raw pickling traceback.
            raise SandboxError(
                f"capability {capability_id!r} handler or payload could not be "
                f"started under the sandbox's spawn context: {type(exc).__name__}: {exc}"
            ) from exc
        child_conn.close()  # parent's copy of the child's write end -- must close so EOF is detectable

        # Wait on the CONNECTION, not process.join(), as the primary
        # deadline gate. A pipe's kernel buffer is small (commonly ~64KB);
        # a handler returning a larger result blocks mid-write until the
        # parent reads. join()-first would leave the parent not reading
        # at all while the child is blocked writing -- a real deadlock
        # (documented multiprocessing pitfall), which surfaced here as
        # every oversized-result adversarial test spuriously "timing
        # out" instead of exercising the size check below. poll() reports
        # readable as soon as the child starts writing, and the
        # subsequent recv() actively drains the pipe (unblocking the
        # child) while still being bounded by the poll() deadline for the
        # "handler never even started responding" case.
        data_ready = parent_conn.poll(timeout_seconds)

        if not data_ready:
            duration = time.monotonic() - start
            if process.is_alive():
                # Real, enforced deadline: terminate the OS process, not
                # a cooperative flag a hung/CPU-bound handler could
                # ignore. Fail closed -- no partial/late result is ever
                # trusted.
                process.terminate()
                process.join(_TERMINATE_GRACE_SECONDS)
                if process.is_alive():
                    process.kill()
                    process.join(_TERMINATE_GRACE_SECONDS)
                raise SandboxError(
                    f"capability {capability_id!r} exceeded its {timeout_seconds}s timeout -- terminated"
                )
            raise SandboxError(
                f"capability {capability_id!r} produced no result (child exit code {process.exitcode}) -- refused"
            )

        # poll() reports "ready" both when data has arrived and when the
        # child closed its end without writing anything (e.g. a hard
        # os._exit() before reaching conn.send()) -- EOF is "ready" too.
        # recv() on that EOF case raises EOFError, which must be refused
        # the same clean way as the no-data-within-deadline case above,
        # never leaked as a raw EOFError.
        try:
            status, result = parent_conn.recv()
        except EOFError:
            duration = time.monotonic() - start
            process.join(_TERMINATE_GRACE_SECONDS)
            raise SandboxError(
                f"capability {capability_id!r} produced no result (child exit code {process.exitcode}) -- refused"
            )
        duration = time.monotonic() - start
        process.join(_TERMINATE_GRACE_SECONDS)
        if process.is_alive():
            process.terminate()
            process.join(_TERMINATE_GRACE_SECONDS)

        if status == "error":
            exc = result
            if isinstance(exc, SandboxError):
                raise type(exc)(_sanitize_message(str(exc), sandbox_root))
            raise SandboxError(_sanitize_message(f"{type(exc).__name__}: {exc}", sandbox_root))

        output, stdout_summary, evidence_files = result

        # Bound the STRUCTURED result -- refuse (never silently truncate
        # a dict, which would corrupt it), distinct from stdout_summary
        # below, which is free text and safe to truncate.
        serialized = json.dumps(output, sort_keys=True, separators=(",", ":"), default=str)
        serialized_bytes = len(serialized.encode("utf-8"))
        if serialized_bytes > MAX_RESULT_BYTES:
            raise SandboxError(
                f"capability {capability_id!r} returned an oversized result "
                f"({serialized_bytes} bytes > {MAX_RESULT_BYTES} cap) -- refused"
            )

        if len(evidence_files) > MAX_EVIDENCE_FILES:
            raise SandboxError(
                f"capability {capability_id!r} returned too many evidence files "
                f"({len(evidence_files)} > {MAX_EVIDENCE_FILES} cap) -- refused"
            )

        summary_bytes = stdout_summary.encode("utf-8")
        if len(summary_bytes) > MAX_OUTPUT_BYTES:
            stdout_summary = summary_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "...<truncated>"

        return output, stdout_summary, duration, evidence_files
    finally:
        parent_conn.close()
        shutil.rmtree(sandbox_dir, ignore_errors=True)
