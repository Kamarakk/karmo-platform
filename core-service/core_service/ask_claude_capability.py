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
call runs inside a freshly created, single-use temp directory containing
nothing except, when the caller supplies one, exactly one caller-provided
image file -- so there is never anything of KARMO's own to read, image
requests included. --permission-prompts none reliably denies writes (also
verified live) and stops Claude from retrying a denied action.

Image support (Phase V0 of docs/plans/KARMO_VOICE_VISION_EARS_ROADMAP.md,
verified live 2026-09-20): `claude -p`, run non-interactively with
--permission-prompts none, correctly read and described a real PNG placed
in its cwd (600x400, correct dominant color) in ~10 seconds -- it also
tried to shell out to `sips` for pixel dimensions and was cleanly denied,
then still answered correctly by reading the image directly, confirming
the no-shell-access boundary holds even with a real file present. This is
the ONLY channel through which KARMO can gain any image-understanding
capability today without adding a new local vision model, which would
directly compete with qwen3:8b for RAM this hardware doesn't have to
spare (see the roadmap doc). No KARMO client surface can send an image
yet (see the roadmap's Phase V3) -- this capability is real and tested,
but not yet reachable from a live conversation.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import shutil
import subprocess
import sys
import tempfile

from .control import CapabilityClass
from .delegation_cache import get_default_cache

ASK_CLAUDE_TOOL = "karmo.delegate.ask_claude"
TOOL_VERSION = "1.0.0"

MAX_QUESTION_CHARS = 4000
TIMEOUT_SECONDS = 90

# 5MB is generous for a real photo/screenshot while keeping a bound on how
# much a single tool call can push through this path -- not benchmarked
# against a real image corpus, just a sane starting ceiling.
MAX_IMAGE_BYTES = 5_000_000
# A fixed, closed allow-list rather than trusting a caller-supplied
# extension string directly -- the format also becomes part of a
# filename we construct ourselves, so this also rules out any path-
# traversal/injection surface in that filename.
_ALLOWED_IMAGE_FORMATS = frozenset({"png", "jpg", "jpeg", "webp", "gif"})


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
            "knowledge, more careful reasoning, or understanding an image (KARMO has no "
            "local vision model). Runs through Kamara's existing Claude subscription at "
            "no extra cost. Pure question-and-answer only: the delegated call has no "
            "shell access and cannot act on KARMO's behalf, only answer in text -- it "
            "can read exactly one caller-provided image when one is given, nothing else."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "maxLength": MAX_QUESTION_CHARS},
                "image_base64": {
                    "type": "string",
                    "description": "Optional base64-encoded image content, max 5MB decoded.",
                },
                "image_format": {
                    "type": "string",
                    "enum": sorted(_ALLOWED_IMAGE_FORMATS),
                    "description": "Required when image_base64 is given.",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        "capability_class": CapabilityClass.READ.value,
        "read_scope": (
            "none -- the delegated call has no access to any KARMO data; when an image is "
            "supplied, it can read exactly that one caller-provided file, written into its "
            "own single-use temp directory, nothing else"
        ),
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
        "idempotency_mechanism": (
            "not guaranteed idempotent; a fresh call is a live model invocation, though an exact "
            "repeat of the same normalized question within the process's in-memory cache TTL "
            "(delegation_cache.py, 1 hour default) returns the prior answer instead of re-calling "
            "the claude CLI"
        ),
        "rollback_or_compensation": "not applicable",
        "health_check": "invoke with a trivial question and confirm a non-empty answer",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "the claude CLI, already installed and logged in via subscription",
        "observability": "structured operator response; cache hits logged to stderr",
        "failure_isolation": "a timeout or CLI failure refuses cleanly, never hangs the chat turn",
    }


def _invoke_claude_cli(question: str, *, image_bytes: bytes | None = None, image_format: str | None = None) -> str:
    """Isolated so tests can monkeypatch this one function rather than
    spawning a real (billed-against-usage, network-dependent) claude
    process, matching the shape of the actual call.

    When image_bytes is given, it's written into this call's own fresh
    temp directory as the ONLY file present, and the prompt tells Claude
    where to find it -- verified live 2026-09-20 (see module docstring)
    that claude -p actually reads and correctly describes a real image
    placed this way."""
    workdir = tempfile.mkdtemp(prefix="karmo-ask-claude-")
    try:
        prompt = question
        if image_bytes is not None:
            image_filename = f"image.{image_format}"
            with open(os.path.join(workdir, image_filename), "wb") as image_file:
                image_file.write(image_bytes)
            prompt = f"{question}\n\n(The relevant image is at ./{image_filename} in your current directory.)"
        result = subprocess.run(
            ["claude", "-p", prompt, "--permission-prompts", "none", "--output-format", "json"],
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


def _parse_optional_image(arguments: dict) -> tuple[bytes, str] | None:
    image_base64 = arguments.get("image_base64")
    if image_base64 is None:
        return None
    if not isinstance(image_base64, str):
        raise AskClaudeCapabilityError("image_base64 must be a string")
    image_format = arguments.get("image_format")
    if not isinstance(image_format, str) or image_format.lower() not in _ALLOWED_IMAGE_FORMATS:
        raise AskClaudeCapabilityError(f"image_format must be one of {sorted(_ALLOWED_IMAGE_FORMATS)}")
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AskClaudeCapabilityError("image_base64 is not valid base64") from exc
    if not image_bytes:
        raise AskClaudeCapabilityError("image_base64 decoded to empty content")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise AskClaudeCapabilityError(f"image exceeds {MAX_IMAGE_BYTES} bytes")
    return image_bytes, image_format.lower()


def handler(arguments: dict) -> dict:
    question = arguments.get("question")
    if not isinstance(question, str) or not question.strip():
        raise AskClaudeCapabilityError("question must be non-empty text")
    if len(question) > MAX_QUESTION_CHARS:
        raise AskClaudeCapabilityError(f"question exceeds {MAX_QUESTION_CHARS} characters")
    image = _parse_optional_image(arguments)

    # Caching only applies to pure text questions -- an image-bearing
    # question is unlikely to repeat verbatim, and caching by image
    # content isn't worth the complexity for this first slice.
    if image is None:
        cache = get_default_cache()
        cached_answer = cache.get(ASK_CLAUDE_TOOL, question)
        if cached_answer is not None:
            print("KARMO ask_claude: exact-match cache hit, skipped a real claude CLI call", file=sys.stderr, flush=True)
            return {"answer": cached_answer}
        answer = _invoke_claude_cli(question)
        cache.set(ASK_CLAUDE_TOOL, question, answer)
        return {"answer": answer}

    image_bytes, image_format = image
    answer = _invoke_claude_cli(question, image_bytes=image_bytes, image_format=image_format)
    return {"answer": answer}
