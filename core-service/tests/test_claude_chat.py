from __future__ import annotations

import base64
import json
import os
import subprocess
import time

import pytest

from core_service import claude_chat

SID = "0b6f7d1e-2c3a-4b5c-8d9e-0f1a2b3c4d5e"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("KARMO_DELEGATE_CLI_USER", raising=False)
    monkeypatch.setattr(claude_chat.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


class Runner:
    def __init__(self, stdout=None, returncode=0, stderr=""):
        self.calls = []
        self.stdout = stdout if stdout is not None else json.dumps(
            {"type": "result", "is_error": False, "result": "Monrovia.", "session_id": SID})
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_first_turn_returns_answer_and_session():
    runner = Runner()
    out = claude_chat.ask("Capital of Liberia?", runner=runner)
    assert out == {"answer": "Monrovia.", "session_id": SID}
    cmd, kwargs = runner.calls[0]
    assert cmd[1:3] == ["-p", "Capital of Liberia?"]
    assert "--resume" not in cmd
    assert cmd[cmd.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert "Bash" in cmd[cmd.index("--disallowedTools") + 1]
    assert kwargs["cwd"] == claude_chat.chat_dir()
    assert kwargs["timeout"] == claude_chat.TIMEOUT_SECONDS


def test_follow_up_resumes_the_session():
    runner = Runner()
    claude_chat.ask("And its population?", session_id=SID, runner=runner)
    cmd = runner.calls[0][0]
    assert cmd[cmd.index("--resume") + 1] == SID


@pytest.mark.parametrize("bad", ["--dangerously-skip-permissions", "x; rm -rf /", "1234"])
def test_rejects_session_ids_that_are_not_uuids(bad):
    with pytest.raises(claude_chat.ClaudeChatError):
        claude_chat.ask("hi", session_id=bad, runner=Runner())


def test_attachment_is_saved_in_the_chat_folder_and_named_in_the_prompt():
    runner = Runner()
    claude_chat.ask("What plant is this?", files=[{"name": "../../etc/leaf photo.png", "data_base64": _b64(b"png")}],
                    runner=runner)
    prompt = runner.calls[0][0][2]
    assert "./files/" in prompt and prompt.endswith("leaf_photo.png)")
    rel = prompt.split("./", 1)[1].rstrip(")")
    path = os.path.join(claude_chat.chat_dir(), rel)
    assert os.path.realpath(path).startswith(os.path.realpath(claude_chat.chat_dir()))
    with open(path, "rb") as fh:
        assert fh.read() == b"png"


def test_file_only_message_gets_a_default_question():
    runner = Runner()
    claude_chat.ask("", files=[{"name": "notes.txt", "data_base64": _b64(b"hi")}], runner=runner)
    assert runner.calls[0][0][2].startswith("Please look at the attached file(s).")


@pytest.mark.parametrize("files, why", [
    ([{"name": "run.sh", "data_base64": _b64(b"x")}], "type"),
    ([{"name": "a.txt", "data_base64": "not base64!!"}], "base64"),
    ([{"name": "a.txt", "data_base64": ""}], "empty"),
    ([{"name": f"{i}.txt", "data_base64": _b64(b"x")} for i in range(5)], "at most"),
])
def test_bad_attachments_are_refused_before_claude_runs(files, why):
    runner = Runner()
    with pytest.raises(claude_chat.ClaudeChatError):
        claude_chat.ask("look", files=files, runner=runner)
    assert runner.calls == []


def test_old_attachment_folders_are_pruned():
    root = os.path.join(claude_chat.chat_dir(), "files")
    old = os.path.join(root, "old")
    os.makedirs(old)
    stale = time.time() - (claude_chat.ATTACHMENT_KEEP_DAYS + 1) * 86400
    os.utime(old, (stale, stale))
    claude_chat.ask("hi", runner=Runner())
    assert not os.path.exists(old)


def test_error_result_is_raised():
    runner = Runner(stdout=json.dumps({"is_error": True, "result": "Usage limit reached"}))
    with pytest.raises(claude_chat.ClaudeChatError, match="Usage limit"):
        claude_chat.ask("hi", runner=runner)


def test_not_logged_in_is_explained():
    runner = Runner(stdout="", returncode=1, stderr="Invalid API key · Please run /login")
    with pytest.raises(claude_chat.ClaudeChatError, match="not logged in"):
        claude_chat.ask("hi", runner=runner)


def test_timeout_is_explained():
    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)
    with pytest.raises(claude_chat.ClaudeChatError, match="longer than"):
        claude_chat.ask("hi", runner=slow)


def test_missing_dedicated_user_is_a_clean_error(monkeypatch):
    monkeypatch.setenv("KARMO_DELEGATE_CLI_USER", "no-such-user-karmo")
    with pytest.raises(claude_chat.ClaudeChatError, match="not set up"):
        claude_chat.ask("hi", runner=Runner())
