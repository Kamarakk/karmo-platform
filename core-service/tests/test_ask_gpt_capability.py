"""Tests for the ask_gpt chat capability -- Phase 4 of
docs/architecture/KARMO_CHAT_TOOL_CALLING_AND_EXTERNAL_DELEGATION.md.

IMPORTANT: unlike test_ask_claude_capability.py's sibling, this capability
has NOT been verified against a real codex CLI invocation (not installed
on the machine this was built on). These tests prove the code behaves
correctly against the NDJSON shape OpenAI's own (acknowledged incomplete)
documentation describes -- they cannot prove that shape is what a real
codex process actually emits. See ask_gpt_capability.py's module
docstring. _invoke_codex_cli/subprocess.run are monkeypatched throughout,
same isolation pattern as the ask_claude tests.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from core_service import ask_gpt_capability
from core_service.ask_gpt_capability import (
    AskGptCapabilityError,
    MAX_QUESTION_CHARS,
    _extract_answer_from_ndjson,
    handler,
    manifest,
)
from core_service.control import ApprovalRequirement, CapabilityClass
from core_service.operator import _CHAT_EXPOSED_TOOLS, KarmoOperator


def test_manifest_is_read_class_with_none_approval():
    assert manifest()["capability_class"] == CapabilityClass.READ.value


def test_capability_is_wired_into_the_exposed_tool_list_as_read_only():
    entry = _CHAT_EXPOSED_TOOLS["ask_gpt"]
    operator = KarmoOperator(model_client=object(), task_store=None)
    record = operator.registry.get(entry["tool_id"], entry["version"])
    assert record is not None
    assert record.computed_approval_requirement == ApprovalRequirement.NONE


def test_extracts_the_last_agent_message_from_ndjson_stream():
    stream = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({"type": "item.completed", "item": {"id": "item_0", "type": "reasoning", "text": "thinking..."}}),
        json.dumps({"type": "item.completed", "item": {"id": "item_1", "type": "agent_message", "text": "the answer is 4"}}),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}),
    ])

    assert _extract_answer_from_ndjson(stream) == "the answer is 4"


def test_ignores_blank_lines_and_non_json_noise():
    stream = "\n".join([
        "",
        "   ",
        "not json at all",
        json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
    ])

    assert _extract_answer_from_ndjson(stream) == "ok"


def test_no_agent_message_event_is_refused_cleanly():
    stream = json.dumps({"type": "turn.completed", "usage": {}})

    with pytest.raises(AskGptCapabilityError, match="no agent_message event"):
        _extract_answer_from_ndjson(stream)


def test_successful_delegation_returns_the_answer(monkeypatch):
    monkeypatch.setattr(ask_gpt_capability, "_invoke_codex_cli", lambda question: "the answer is 4")

    result = handler({"question": "what is 2+2?"})

    assert result == {"answer": "the answer is 4"}


def test_empty_question_is_refused_without_invoking_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(ask_gpt_capability, "_invoke_codex_cli", lambda q: calls.append(q))

    with pytest.raises(AskGptCapabilityError, match="non-empty"):
        handler({"question": "   "})

    assert calls == []


def test_oversized_question_is_refused_without_invoking_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(ask_gpt_capability, "_invoke_codex_cli", lambda q: calls.append(q))
    huge = "x" * (MAX_QUESTION_CHARS + 1)

    with pytest.raises(AskGptCapabilityError, match="exceeds"):
        handler({"question": huge})

    assert calls == []


def test_cli_timeout_is_refused_cleanly_not_hung(monkeypatch):
    def _raise_timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 90))

    monkeypatch.setattr(ask_gpt_capability.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(ask_gpt_capability.shutil, "rmtree", lambda *a, **k: None)

    with pytest.raises(AskGptCapabilityError, match="timed out"):
        handler({"question": "anything"})


def test_cli_nonzero_exit_is_refused_cleanly(monkeypatch):
    class _Result:
        returncode = 1
        stdout = ""
        stderr = "not logged in"

    monkeypatch.setattr(ask_gpt_capability.subprocess, "run", lambda *a, **k: _Result())
    monkeypatch.setattr(ask_gpt_capability.shutil, "rmtree", lambda *a, **k: None)

    with pytest.raises(AskGptCapabilityError, match="codex CLI exited 1"):
        handler({"question": "anything"})


def test_uses_the_read_only_sandbox_flag(monkeypatch):
    """Locks in the one explicit safety flag this capability relies on --
    unlike ask_claude, where flags don't prevent reads, Codex's own docs
    describe --sandbox read-only as blocking both writes and shell
    execution -- verified live 2026-09-17 against codex-cli 0.154.0.
    --skip-git-repo-check is also required (verified live: codex exec
    refuses to run at all outside a trusted git repo without it, which a
    freshly created empty temp directory always is)."""
    seen_argv = []
    seen_kwargs = []

    class _Result:
        returncode = 0
        stdout = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}})
        stderr = ""

    def _fake_run(argv, **kwargs):
        seen_argv.append(argv)
        seen_kwargs.append(kwargs)
        return _Result()

    monkeypatch.setattr(ask_gpt_capability.subprocess, "run", _fake_run)

    handler({"question": "anything"})

    assert "--sandbox" in seen_argv[0]
    assert "read-only" in seen_argv[0]
    assert "--skip-git-repo-check" in seen_argv[0]
    assert seen_kwargs[0]["stdin"] == subprocess.DEVNULL


def test_runs_in_a_fresh_temp_directory_and_cleans_up(monkeypatch):
    seen_workdirs = []

    class _Result:
        returncode = 0
        stdout = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}})
        stderr = ""

    def _fake_run(argv, *, cwd, **kwargs):
        import os
        seen_workdirs.append(cwd)
        assert os.path.isdir(cwd)
        assert os.listdir(cwd) == []
        return _Result()

    monkeypatch.setattr(ask_gpt_capability.subprocess, "run", _fake_run)

    handler({"question": "anything"})

    import os
    assert len(seen_workdirs) == 1
    assert not os.path.exists(seen_workdirs[0]), "temp workdir must be cleaned up after the call"
