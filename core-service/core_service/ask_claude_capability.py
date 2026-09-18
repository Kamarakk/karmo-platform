"""Delegate a text question to Claude via the already-installed `claude` CLI,
authenticated through Kamara's existing subscription (never an API key) --
verified free and vendor-sanctioned for headless use, per
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md
Section 3.3 and Section 1's citation of Anthropic's own cost documentation.

Safety note, verified live against a real `claude` invocation, not assumed:
Claude Code's permission system always allows file reads within the
working directory regardless of --allowedTools or --permission-prompts --
neither flag can fully prevent reads. The actual "pure Q&A, no file or
shell access" guarantee here is therefore structural, not flag-based: every
call runs inside a freshly created, empty, single-use temp directory, so
there is nothing there to read. --permission-prompts none reliably denies
writes (also verified live) and stops Claude from retrying a denied action.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile

from .control import CapabilityClass

ASK_CLAUDE_TOOL = "karmo.delegate.ask_claude"
TOOL_VERSION = "1.0.0"

MAX_QUESTION_CHARS = 4000
TIMEOUT_SECONDS = 90


class AskClaudeCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": ASK_CLAUDE_TOOL,
        "domain": "delegation",
        "version": TOOL_VERSION,
        "description": (
            "Ask Claude (Anthropic's AI) a text question when KARMO's own local models "
            "can't adequately answer it -- e.g. something needing broader general "
            "knowledge or more careful reasoning. Runs through Kamara's existing Claude "
            "subscription at no extra cost. Pure question-and-answer only: the "
            "delegated call has no file or shell access and cannot act on KARMO's "
            "behalf, only answer in text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string", "maxLength": MAX_QUESTION_CHARS}},
            "required": ["question"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        "capability_class": CapabilityClass.READ.value,
        "read_scope": "none -- the delegated call has no access to any KARMO data",
        "write_scope": "none",
        "external_side_effects": "one outbound call via the locally installed claude CLI",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "outbound HTTPS via the claude CLI's own subscription auth",
        "secret_requirements": "none -- uses the operator's own already-logged-in claude CLI session",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": TIMEOUT_SECONDS,
        "retry_policy": "none",
        "idempotent": False,
        "idempotency_mechanism": "not idempotent; each call is a live model invocation",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with a trivial question and confirm a non-empty answer",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "the claude CLI, already installed and logged in via subscription",
        "observability": "structured operator response",
        "failure_isolation": "a timeout or CLI failure refuses cleanly, never hangs the chat turn",
    }


def _invoke_claude_cli(question: str) -> str:
    """Isolated so tests can monkeypatch this one function rather than
    spawning a real (billed-against-usage, network-dependent) claude
    process, matching the shape of the actual call."""
    workdir = tempfile.mkdtemp(prefix="karmo-ask-claude-")
    try:
        result = subprocess.run(
            ["claude", "-p", question, "--permission-prompts", "none", "--output-format", "json"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AskClaudeCapabilityError(f"claude CLI timed out after {TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise AskClaudeCapabilityError(f"claude CLI could not be started: {exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if result.returncode != 0:
        raise AskClaudeCapabilityError(f"claude CLI exited {result.returncode}: {result.stderr[:500]}")
    try:
        payload = json.loads(result.stdout)
        answer = payload["result"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AskClaudeCapabilityError("invalid claude CLI response") from exc
    if not isinstance(answer, str):
        raise AskClaudeCapabilityError("invalid claude CLI answer type")
    return answer


def handler(arguments: dict) -> dict:
    question = arguments.get("question")
    if not isinstance(question, str) or not question.strip():
        raise AskClaudeCapabilityError("question must be non-empty text")
    if len(question) > MAX_QUESTION_CHARS:
        raise AskClaudeCapabilityError(f"question exceeds {MAX_QUESTION_CHARS} characters")
    return {"answer": _invoke_claude_cli(question)}
