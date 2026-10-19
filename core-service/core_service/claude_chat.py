"""The Claude tab: a direct conversation with Claude inside KARMO.

Kamara asked (2026-10-19) to use Claude only through KARMO. This runs the
`claude` CLI on his subscription (never an API key) as the locked-down
`karmo-ask` account (delegation_runner.py), and keeps each conversation
going with `--resume <session_id>`.

Boundaries, same model as ask_claude_capability.py:
* every turn runs in one fixed folder under karmo-ask's home, so Claude
  can read only what is in it: files Kamara attached in this tab;
* only WebSearch and WebFetch are pre-approved; Bash, Edit and Write are
  refused, so it cannot run commands or change anything;
* karmo-ask cannot read /etc/karmo/core, so KARMO's secrets stay out of reach;
* nothing from KARMO's own memory is sent: only what he types or attaches.
Attachments are kept for ATTACHMENT_KEEP_DAYS so follow-up questions can
refer to them, then removed.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time

from .delegation_runner import DelegationRunnerError, claude_binary, cli_user, run_kwargs

MAX_MESSAGE_CHARS = 20_000
MAX_FILES = 4
MAX_FILE_BYTES = 10_000_000
TIMEOUT_SECONDS = 300
ATTACHMENT_KEEP_DAYS = 7
ALLOWED_TOOLS = "WebSearch,WebFetch"
DENIED_TOOLS = "Bash,Edit,Write,NotebookEdit"
ALLOWED_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp", "gif", "pdf", "txt", "md", "csv", "json"})
_SESSION_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class ClaudeChatError(RuntimeError):
    pass


def chat_dir() -> str:
    """The one folder every Claude-tab turn runs in (also what --resume keys on)."""
    entry = cli_user()
    base = entry.pw_dir if entry is not None else tempfile.gettempdir()
    return os.path.join(base, "karmo-claude-tab")


def _own(path: str) -> None:
    entry = cli_user()
    if entry is not None:
        os.chown(path, entry.pw_uid, entry.pw_gid)


def _safe_name(name: str) -> str:
    base = _SAFE_NAME.sub("_", os.path.basename(name or "")).strip("._") or "file"
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ClaudeChatError(f"file type not allowed: {name!r} (allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))})")
    return base[-120:]


def _prune(files_root: str, now: float) -> None:
    if not os.path.isdir(files_root):
        return
    cutoff = now - ATTACHMENT_KEEP_DAYS * 86400
    for entry in os.scandir(files_root):
        if entry.is_dir(follow_symlinks=False) and entry.stat(follow_symlinks=False).st_mtime < cutoff:
            shutil.rmtree(entry.path, ignore_errors=True)


def _save_files(workdir: str, files: list) -> list[str]:
    """Writes attachments into a fresh files/<id>/ folder; returns paths relative to workdir."""
    if not files:
        return []
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise ClaudeChatError(f"at most {MAX_FILES} files per message")
    decoded = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("data_base64"), str):
            raise ClaudeChatError("each file needs a name and data_base64")
        name = _safe_name(item["name"])
        try:
            data = base64.b64decode(item["data_base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ClaudeChatError(f"{name}: not valid base64") from exc
        if not data:
            raise ClaudeChatError(f"{name}: empty file")
        if len(data) > MAX_FILE_BYTES:
            raise ClaudeChatError(f"{name}: larger than {MAX_FILE_BYTES // 1_000_000} MB")
        decoded.append((name, data))

    files_root = os.path.join(workdir, "files")
    os.makedirs(files_root, exist_ok=True)
    _own(files_root)
    folder = os.path.join(files_root, time.strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3))
    os.mkdir(folder)
    _own(folder)
    saved = []
    for name, data in decoded:
        path = os.path.join(folder, name)
        with open(path, "wb") as fh:
            fh.write(data)
        _own(path)
        saved.append(os.path.relpath(path, workdir))
    return saved


def _build_command(prompt: str, session_id: str | None) -> list[str]:
    cmd = [claude_binary(), "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
           "--allowedTools", ALLOWED_TOOLS, "--disallowedTools", DENIED_TOOLS]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd


def ask(message: str, *, session_id: str | None = None, files: list | None = None, runner=subprocess.run) -> dict:
    """One Claude-tab turn. Returns {"answer", "session_id"}; raises ClaudeChatError."""
    if not isinstance(message, str) or not message.strip():
        if not files:
            raise ClaudeChatError("message must be non-empty text")
        message = "Please look at the attached file(s)."
    if len(message) > MAX_MESSAGE_CHARS:
        raise ClaudeChatError(f"message exceeds {MAX_MESSAGE_CHARS} characters")
    if session_id is not None and (not isinstance(session_id, str) or not _SESSION_ID.match(session_id)):
        raise ClaudeChatError("invalid session_id")

    try:
        workdir = chat_dir()
        os.makedirs(workdir, mode=0o700, exist_ok=True)
        _prune(os.path.join(workdir, "files"), time.time())
        saved = _save_files(workdir, files or [])
        extra = run_kwargs(workdir)  # chowns workdir to karmo-ask and drops to it
    except DelegationRunnerError as exc:
        raise ClaudeChatError(f"Claude is not set up on this server: {exc}") from exc
    except OSError as exc:
        raise ClaudeChatError(f"could not prepare the Claude folder: {exc}") from exc

    prompt = message
    if saved:
        prompt += "\n\n(Attached file(s), in your current directory: " + ", ".join("./" + p for p in saved) + ")"
    try:
        result = runner(_build_command(prompt, session_id), cwd=workdir, capture_output=True,
                        text=True, timeout=TIMEOUT_SECONDS, **extra)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeChatError(f"Claude took longer than {TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise ClaudeChatError(f"claude CLI could not be started: {exc}") from exc

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        detail = (result.stderr or result.stdout or "").strip()[:400]
        if "login" in detail.lower() or "auth" in detail.lower():
            raise ClaudeChatError("Claude is not logged in on AI01 yet")
        raise ClaudeChatError(f"claude CLI exited {result.returncode}: {detail}")
    answer = payload.get("result")
    if payload.get("is_error") or not isinstance(answer, str):
        raise ClaudeChatError(str(answer or payload.get("subtype") or "Claude returned an error")[:400])
    new_session = payload.get("session_id")
    return {"answer": answer, "session_id": new_session if isinstance(new_session, str) and _SESSION_ID.match(new_session) else session_id}
