"""Delegate a text question to GPT via the already-installed `codex` CLI,
authenticated through Kamara's existing ChatGPT subscription (never an API
key), per docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md
Section 3.4.

Verified live 2026-09-17 against codex-cli 0.154.0, logged in via
ChatGPT subscription (not an API key): the NDJSON event shape this module
parses (item.completed / agent_message / text) matched real CLI output
exactly on the first try. Live testing did catch two real bugs the
original unverified version had, both fixed here: (1) `codex exec`
refuses to run outside a trusted git repository unless
--skip-git-repo-check is passed, which a freshly created empty temp
directory always needs since it's deliberately never a git repo; (2) the
CLI prints "Reading additional input from stdin..." and reads from
stdin by default, so stdin is now explicitly set to DEVNULL rather than
left to inherit whatever the parent process's stdin happens to be.
OpenAI's own docs still have an open, acknowledged accuracy gap for this
schema across versions, so a future codex CLI upgrade could still change
this shape -- if answers start failing to parse, re-verify live before
assuming the code is still correct.

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
import sys
import tempfile

from .control import CapabilityClass
from .delegation_cache import get_default_cache
from .delegation_runner import DelegationRunnerError, codex_binary, run_kwargs

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
        "idempotency_mechanism": (
            "not guaranteed idempotent; a fresh call is a live model invocation, though an exact "
            "repeat of the same normalized question within the process's in-memory cache TTL "
            "(delegation_cache.py, 1 hour default) returns the prior answer instead of re-calling "
            "the codex CLI"
        ),
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with a trivial question and confirm a non-empty answer",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "the codex CLI, already installed and logged in via subscription",
        "observability": "structured operator response; cache hits logged to stderr",
        "failure_isolation": "a timeout or CLI failure refuses cleanly, never hangs the chat turn",
    }


def _extract_answer_from_ndjson(stdout: str) -> str:
    """codex exec --json prints newline-delimited JSON events, not one
    object (unlike Claude's --output-format json). The answer text lives
    on an `item.completed` event whose `item.type` is `agent_message`, at
    `item.text` -- verified live against a real codex-cli 0.154.0 process
    (see this module's docstring)."""
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
            [codex_binary(), "exec", "--json", "--sandbox", "read-only", "--skip-git-repo-check", question],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
            **run_kwargs(workdir),
        )
    except subprocess.TimeoutExpired as exc:
        raise AskGptCapabilityError(f"codex CLI timed out after {TIMEOUT_SECONDS}s") from exc
    except (OSError, DelegationRunnerError) as exc:
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
    cache = get_default_cache()
    cached_answer = cache.get(ASK_GPT_TOOL, question)
    if cached_answer is not None:
        print("KARMO ask_gpt: exact-match cache hit, skipped a real codex CLI call", file=sys.stderr, flush=True)
        return {"answer": cached_answer}
    answer = _invoke_codex_cli(question)
    cache.set(ASK_GPT_TOOL, question, answer)
    return {"answer": answer}
