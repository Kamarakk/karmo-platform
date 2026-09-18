"""Delegate a text question to GPT via the already-installed `codex` CLI,
authenticated through Kamara's existing ChatGPT subscription (never an API
key), per docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md
Section 3.4.

IMPORTANT, unlike ask_claude_capability.py's sibling: this module has NOT
been verified against a real `codex` invocation -- the CLI was not
installed on the machine this was built on. Everything below is built
from OpenAI's own documentation as carefully as possible, but that
documentation has open, acknowledged accuracy gaps for exactly the
feature this relies on (the --json event schema): OpenAI's own GitHub
tracks an open issue that the documented event shape is out of date
relative to actual CLI output, and multiple independent sources report
the schema changing across CLI versions (item_type -> type,
assistant_message -> agent_message). Treat this capability as unverified
until it has actually been run once for real and the output shape
confirmed -- do not assume it works simply because it was written
carefully.

Vendor-posture note (Section 1 of the design doc): OpenAI's own docs
recommend API-key billing for automated/scripted Codex use, unlike
Anthropic which actively endorses subscription-based headless use. This
capability exists because Kamara explicitly chose to build it anyway,
not because that recommendation stopped applying.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile

from .control import CapabilityClass

ASK_GPT_TOOL = "karmo.delegate.ask_gpt"
TOOL_VERSION = "1.0.0"

MAX_QUESTION_CHARS = 4000
TIMEOUT_SECONDS = 90


class AskGptCapabilityError(RuntimeError):
    pass


def manifest() -> dict:
    return {
        "tool_id": ASK_GPT_TOOL,
        "domain": "delegation",
        "version": TOOL_VERSION,
        "description": (
            "Ask GPT (OpenAI's AI) a text question when KARMO's own local models and "
            "Claude can't adequately answer it. Runs through Kamara's existing ChatGPT "
            "subscription at no extra cost. Pure question-and-answer only: the "
            "delegated call runs in OpenAI's most restricted read-only sandbox and has "
            "no shell or write access."
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
        "external_side_effects": "one outbound call via the locally installed codex CLI",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "outbound HTTPS via the codex CLI's own subscription auth",
        "secret_requirements": "none -- uses the operator's own already-logged-in codex CLI session",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": TIMEOUT_SECONDS,
        "retry_policy": "none",
        "idempotent": False,
        "idempotency_mechanism": "not idempotent; each call is a live model invocation",
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with a trivial question and confirm a non-empty answer",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "the codex CLI, already installed and logged in via subscription",
        "observability": "structured operator response",
        "failure_isolation": "a timeout or CLI failure refuses cleanly, never hangs the chat turn",
    }


def _extract_answer_from_ndjson(stdout: str) -> str:
    """codex exec --json prints newline-delimited JSON events, not one
    object (unlike Claude's --output-format json). The answer text is
    reported to live on an `item.completed` event whose `item.type` is
    `agent_message`, at `item.text` -- per current third-party
    documentation and OpenAI's own (acknowledged incomplete) docs. NOT
    independently verified against a real codex process -- see this
    module's docstring."""
    answer = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                answer = text
    if answer is None:
        raise AskGptCapabilityError("no agent_message event found in codex CLI output")
    return answer


def _invoke_codex_cli(question: str) -> str:
    """Isolated so tests can monkeypatch this one function rather than
    spawning a real (billed-against-usage, network-dependent) codex
    process, matching the shape of the actual call."""
    workdir = tempfile.mkdtemp(prefix="karmo-ask-gpt-")
    try:
        result = subprocess.run(
            ["codex", "exec", "--json", "--sandbox", "read-only", question],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AskGptCapabilityError(f"codex CLI timed out after {TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise AskGptCapabilityError(f"codex CLI could not be started: {exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if result.returncode != 0:
        raise AskGptCapabilityError(f"codex CLI exited {result.returncode}: {result.stderr[:500]}")
    return _extract_answer_from_ndjson(result.stdout)


def handler(arguments: dict) -> dict:
    question = arguments.get("question")
    if not isinstance(question, str) or not question.strip():
        raise AskGptCapabilityError("question must be non-empty text")
    if len(question) > MAX_QUESTION_CHARS:
        raise AskGptCapabilityError(f"question exceeds {MAX_QUESTION_CHARS} characters")
    return {"answer": _invoke_codex_cli(question)}
