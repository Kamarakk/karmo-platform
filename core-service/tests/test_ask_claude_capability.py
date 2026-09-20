"""Tests for the ask_claude chat capability -- Phase 3 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

_invoke_claude_cli is monkeypatched throughout (matching the isolation
pattern worker-runtime's _call_ollama_generate already uses) so these
tests never spawn a real, network-dependent, subscription-billed claude
process -- that live proof is done manually, once, outside the suite.
"""

from __future__ import annotations

import base64
import os
import subprocess

import pytest

from core_service import ask_claude_capability
from core_service.ask_claude_capability import (
    AskClaudeCapabilityError,
    MAX_QUESTION_CHARS,
    handler,
    manifest,
)
from core_service.control import ApprovalRequirement, CapabilityClass
from core_service.delegation_cache import get_default_cache
from core_service.operator import _CHAT_EXPOSED_TOOLS, KarmoOperator


@pytest.fixture(autouse=True)
def _clear_delegation_cache():
    """The delegation cache is a process-wide singleton (shared with
    ask_gpt) -- clear it before every test so no test's cached answer
    can leak into another test's assertions, regardless of run order."""
    get_default_cache().clear()
    yield
    get_default_cache().clear()


def test_manifest_is_read_class_with_none_approval():
    assert manifest()["capability_class"] == CapabilityClass.READ.value


def test_capability_is_wired_into_the_exposed_tool_list_as_read_only():
    entry = _CHAT_EXPOSED_TOOLS["ask_claude"]
    operator = KarmoOperator(model_client=object(), task_store=None)
    record = operator.registry.get(entry["tool_id"], entry["version"])
    assert record is not None
    assert record.computed_approval_requirement == ApprovalRequirement.NONE


def test_successful_delegation_returns_the_answer(monkeypatch):
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", lambda question: "the answer is 4")

    result = handler({"question": "what is 2+2?"})

    assert result == {"answer": "the answer is 4"}


def test_empty_question_is_refused_without_invoking_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", lambda q: calls.append(q))

    with pytest.raises(AskClaudeCapabilityError, match="non-empty"):
        handler({"question": "   "})

    assert calls == []


def test_oversized_question_is_refused_without_invoking_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", lambda q: calls.append(q))
    huge = "x" * (MAX_QUESTION_CHARS + 1)

    with pytest.raises(AskClaudeCapabilityError, match="exceeds"):
        handler({"question": huge})

    assert calls == []


def test_cli_timeout_is_refused_cleanly_not_hung(monkeypatch):
    def _raise_timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 90))

    monkeypatch.setattr(ask_claude_capability.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(ask_claude_capability.shutil, "rmtree", lambda *a, **k: None)

    with pytest.raises(AskClaudeCapabilityError, match="timed out"):
        handler({"question": "anything"})


def test_cli_nonzero_exit_is_refused_cleanly(monkeypatch):
    class _Result:
        returncode = 1
        stdout = ""
        stderr = "not logged in"

    monkeypatch.setattr(ask_claude_capability.subprocess, "run", lambda *a, **k: _Result())
    monkeypatch.setattr(ask_claude_capability.shutil, "rmtree", lambda *a, **k: None)

    with pytest.raises(AskClaudeCapabilityError, match="claude CLI exited 1"):
        handler({"question": "anything"})


def test_malformed_cli_output_is_refused_cleanly(monkeypatch):
    class _Result:
        returncode = 0
        stdout = "not valid json"
        stderr = ""

    monkeypatch.setattr(ask_claude_capability.subprocess, "run", lambda *a, **k: _Result())
    monkeypatch.setattr(ask_claude_capability.shutil, "rmtree", lambda *a, **k: None)

    with pytest.raises(AskClaudeCapabilityError, match="invalid claude CLI response"):
        handler({"question": "anything"})


def test_repeat_question_hits_the_cache_and_never_calls_the_cli_again(monkeypatch):
    calls = []

    def _invoke(question):
        calls.append(question)
        return "the answer is 4"

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", _invoke)

    first = handler({"question": "what is 2+2?"})
    second = handler({"question": "  WHAT IS 2+2?  "})

    assert first == {"answer": "the answer is 4"}
    assert second == {"answer": "the answer is 4"}
    assert calls == ["what is 2+2?"], "second call must be served from cache, not a fresh CLI call"


def test_a_different_question_still_calls_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", lambda q: calls.append(q) or f"answer to {q}")

    handler({"question": "first question"})
    handler({"question": "second question"})

    assert calls == ["first question", "second question"]


def test_a_failed_call_is_not_cached_and_retries_hit_the_cli_again(monkeypatch):
    calls = []

    def _always_fail(question):
        calls.append(question)
        raise AskClaudeCapabilityError("simulated failure")

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", _always_fail)

    with pytest.raises(AskClaudeCapabilityError):
        handler({"question": "anything"})
    with pytest.raises(AskClaudeCapabilityError):
        handler({"question": "anything"})

    assert calls == ["anything", "anything"], "a failed call must never be cached"


def test_image_is_decoded_and_passed_through_to_invoke(monkeypatch):
    captured = {}
    raw_bytes = b"fake-png-bytes"

    def _invoke(question, *, image_bytes=None, image_format=None):
        captured["question"] = question
        captured["image_bytes"] = image_bytes
        captured["image_format"] = image_format
        return "a red square"

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", _invoke)

    result = handler({
        "question": "what color is this?",
        "image_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "image_format": "PNG",
    })

    assert result == {"answer": "a red square"}
    assert captured["image_bytes"] == raw_bytes
    assert captured["image_format"] == "png"


def test_image_request_bypasses_the_cache(monkeypatch):
    calls = []

    def _invoke(question, *, image_bytes=None, image_format=None):
        calls.append(question)
        return "an answer"

    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", _invoke)
    args = {
        "question": "what is this?",
        "image_base64": base64.b64encode(b"bytes").decode("ascii"),
        "image_format": "png",
    }

    handler(args)
    handler(dict(args))

    assert calls == ["what is this?", "what is this?"], "image requests must never be served from cache"


def test_image_without_a_format_is_refused(monkeypatch):
    monkeypatch.setattr(ask_claude_capability, "_invoke_claude_cli", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not be called")))

    with pytest.raises(AskClaudeCapabilityError, match="image_format"):
        handler({"question": "what is this?", "image_base64": base64.b64encode(b"x").decode("ascii")})


def test_unsupported_image_format_is_refused():
    with pytest.raises(AskClaudeCapabilityError, match="image_format"):
        handler({
            "question": "what is this?",
            "image_base64": base64.b64encode(b"x").decode("ascii"),
            "image_format": "bmp",
        })


def test_invalid_base64_is_refused():
    with pytest.raises(AskClaudeCapabilityError, match="not valid base64"):
        handler({"question": "what is this?", "image_base64": "not-valid-base64!!!", "image_format": "png"})


def test_empty_decoded_image_is_refused():
    with pytest.raises(AskClaudeCapabilityError, match="empty"):
        handler({"question": "what is this?", "image_base64": "", "image_format": "png"})


def test_oversized_image_is_refused():
    huge = base64.b64encode(b"x" * (ask_claude_capability.MAX_IMAGE_BYTES + 1)).decode("ascii")
    with pytest.raises(AskClaudeCapabilityError, match="exceeds"):
        handler({"question": "what is this?", "image_base64": huge, "image_format": "png"})


def test_image_is_actually_written_to_the_temp_directory_and_referenced_in_the_prompt(monkeypatch):
    """Direct proof, not just a mocked _invoke_claude_cli, that the real
    _invoke_claude_cli implementation writes exactly one file (the
    caller's image, nothing else) into the fresh temp directory before
    invoking the CLI, and mentions it in the prompt text."""
    seen = {}
    raw_bytes = b"\x89PNG-fake-bytes"

    class _Result:
        returncode = 0
        stdout = '{"result": "a photo"}'
        stderr = ""

    def _fake_run(argv, *, cwd, **kwargs):
        seen["cwd"] = cwd
        seen["prompt"] = argv[argv.index("-p") + 1]
        seen["dir_listing"] = os.listdir(cwd)
        with open(os.path.join(cwd, "image.jpg"), "rb") as f:
            seen["written_bytes"] = f.read()
        return _Result()

    monkeypatch.setattr(ask_claude_capability.subprocess, "run", _fake_run)

    result = handler({
        "question": "describe this photo",
        "image_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "image_format": "jpg",
    })

    assert result == {"answer": "a photo"}
    assert seen["dir_listing"] == ["image.jpg"]
    assert seen["written_bytes"] == raw_bytes
    assert "./image.jpg" in seen["prompt"]
    assert not os.path.exists(seen["cwd"]), "temp workdir must still be cleaned up after an image call"


def test_runs_in_a_fresh_temp_directory_and_cleans_up(monkeypatch):
    """The safety property this capability relies on (see module docstring):
    nothing sensitive is readable because the working directory is always
    freshly created and empty. Verifies both halves -- a fresh dir is used,
    and it's removed afterward -- not just that shutil.rmtree was called."""
    seen_workdirs = []

    class _Result:
        returncode = 0
        stdout = '{"result": "ok"}'
        stderr = ""

    def _fake_run(argv, *, cwd, **kwargs):
        seen_workdirs.append(cwd)
        import os
        assert os.path.isdir(cwd)
        assert os.listdir(cwd) == []
        return _Result()

    monkeypatch.setattr(ask_claude_capability.subprocess, "run", _fake_run)

    handler({"question": "anything"})

    import os
    assert len(seen_workdirs) == 1
    assert not os.path.exists(seen_workdirs[0]), "temp workdir must be cleaned up after the call"
