"""Tests for the ask_claude chat capability -- Phase 3 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

_invoke_claude_cli is monkeypatched throughout (matching the isolation
pattern worker-runtime's _call_ollama_generate already uses) so these
tests never spawn a real, network-dependent, subscription-billed claude
process -- that live proof is done manually, once, outside the suite.
"""

from __future__ import annotations

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
from core_service.operator import _CHAT_EXPOSED_TOOLS, KarmoOperator


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
