"""Core side of KARMO's code sandbox (item 5 of the five Kamara approved in
writing, 2026-10-03). "Write and run a script that ...", "calculate ...
with Python" or a pasted ```python block becomes: get the code (from the
message, or written by Claude when hand-off is on, else KARMO's local
coder), run it on Worker02 in a throwaway no-network container
(worker-runtime/app/code_sandbox.py), and if it fails, send the error
back for a fix -- at most MAX_ATTEMPTS runs. The answer shows the code
and its output.

KARMO never runs code on AI01, and nothing here can change KARMO itself.
"""

from __future__ import annotations

import re

CODE_RUN_TOOL_ID = "code_run"
CODE_RUN_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER02"
_DEADLINE_SECONDS = 130.0
MAX_ATTEMPTS = 3

_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_RUN_REQUEST = re.compile(
    r"\b(?:write\s+and\s+run|run\s+(?:this|it|the\s+code|a\s+script|a\s+program|python)"
    r"|(?:calculate|compute|work\s+out|figure\s+out|simulate)\b.*\b(?:with|using|in)\s+(?:python|code|a\s+script)"
    r"|use\s+(?:python|code)\s+to|python\s+script\s+(?:to|that)\b.*\brun)\b",
    re.IGNORECASE | re.DOTALL,
)

WRITE_PROMPT = (
    "Write one self-contained Python 3 program for this task. Standard library only. "
    "It has no network and no keyboard input; it must print its result. "
    "Reply with only the program in a single ```python code block.\n\nTask: {task}"
)
FIX_PROMPT = (
    "This Python 3 program failed. Fix it (standard library only, no network, no input, "
    "print the result). Reply with only the fixed program in a single ```python code block.\n\n"
    "Task: {task}\n\nProgram:\n```python\n{code}\n```\n\nError:\n{error}"
)


class CodeSandboxCapabilityError(RuntimeError):
    pass


def is_run_request(text: str) -> bool:
    text = text or ""
    return bool(_CODE_BLOCK.search(text) and re.search(r"\brun\b", text, re.IGNORECASE)) or bool(
        _RUN_REQUEST.search(text))


def code_in(text: str) -> str | None:
    match = _CODE_BLOCK.search(text or "")
    return match.group(1).strip() if match and match.group(1).strip() else None


def manifest() -> dict:
    return {
        "tool_id": CODE_RUN_TOOL_ID,
        "domain": "sandbox",
        "version": CODE_RUN_TOOL_VERSION,
        "description": (
            "Run one short Python program on Worker02 in a throwaway container with no network, "
            "512 MB memory and a 60-second limit. Returns the exit code and output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "maxLength": 20000}, "files": {"type": "object"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"stdout": {"type": "string"}}},
        "capability_class": "READ",
        "read_scope": "only the files sent with the job",
        "write_scope": "none on Core; the job folder and container on Worker02 are deleted afterwards",
        "external_side_effects": "one dispatched job to a worker; no network inside the container",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none",
        "secret_requirements": "none beyond the existing worker-dispatch DSN",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": int(_DEADLINE_SECONDS),
        "retry_policy": "none (fix attempts are new runs)",
        "idempotent": False,
        "idempotency_mechanism": "not idempotent; each run is a fresh container",
        "rollback_or_compensation": "not applicable",
        "health_check": "run print(1) and confirm the output is 1",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available; karmo-sandbox-runner on Worker02",
        "observability": "structured operator response",
        "failure_isolation": "a failed run is reported with its error, never hangs the chat turn",
    }


def dispatch_code_run(worker_dispatch_client, *, worker_id: str, code: str, files: dict | None = None) -> dict:
    if not isinstance(code, str) or not code.strip():
        raise CodeSandboxCapabilityError("code must be non-empty text")
    if not worker_dispatch_client.available:
        raise CodeSandboxCapabilityError("worker dispatch is not activated -- no worker-dispatch DSN configured")
    arguments = {"code": code}
    if files:
        arguments["files"] = files
    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=CODE_RUN_TOOL_ID,
        tool_version=CODE_RUN_TOOL_VERSION,
        arguments=arguments,
        total_deadline_seconds=_DEADLINE_SECONDS,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise CodeSandboxCapabilityError(f"{outcome.outcome}: {outcome.error}")
    return outcome.result


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    def _handler(arguments: dict) -> dict:
        return dispatch_code_run(worker_dispatch_client, worker_id=worker_id,
                                 code=arguments.get("code"), files=arguments.get("files"))
    return _handler


def run_failed(result: dict) -> str | None:
    """The error to send back for a fix, or None when the run worked."""
    if result.get("timed_out"):
        return f"It ran out of time ({result.get('stderr', '')})."
    if result.get("exit_code") != 0:
        return (result.get("stderr") or "").strip()[-3000:] or f"exit code {result.get('exit_code')}"
    return None


def format_run(code: str, result: dict | None, *, attempts: int, author: str, error: str | None = None) -> str:
    lines = [f"Ran it in the sandbox on Worker02 (no network), code by {author}"
             + (f", {attempts} tries" if attempts > 1 else "") + ":",
             "```python", code.strip(), "```"]
    if result is None:
        lines.append(f"It didn't run: {error}")
        return "\n".join(lines)
    output = (result.get("stdout") or "").strip()
    lines += ["Output:", "```", output or "(no output)", "```"]
    failure = run_failed(result)
    if failure:
        lines.append(f"It still failed: {failure[-500:]}")
    return "\n".join(lines)
