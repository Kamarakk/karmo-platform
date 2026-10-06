"""KARMO decides on its own when to hand a question to Claude or GPT
(item 2 of the five Kamara approved in writing, 2026-10-03).

Both go through the existing ask_claude / ask_gpt capabilities -- the
`claude` and `codex` CLIs logged in with Kamara's regular subscriptions,
no API key, no extra cost. Only the question text is sent: no profile,
facts, memory or files.

Two cases hand off:
- the question is a heavy writing or reasoning job the local CPU model
  does slowly and poorly (draft an email, write a plan, compare options,
  explain step by step, or any long message);
- the local model failed to answer at all (timeout, unavailable).

Claude is asked first and GPT only if Claude fails. Every handed-off
answer says who wrote it. It runs only while HANDOFF_ENABLED_FILE exists
(same on/off pattern as D2's enable file), so tests and dev machines never
call the real CLIs by accident; deleting the file switches it off.
"""

from __future__ import annotations

import os
import re

HANDOFF_ENABLED_FILE = "/etc/karmo/core/handoff.enabled"
LONG_MESSAGE_CHARS = 400

_HEAVY_TASK = re.compile(
    r"\b(?:write|draft|compose|create|make)\s+(?:me\s+)?(?:a|an|the|my|some)?\s*"
    r"(?:[\w'-]+\s+){0,3}(?:email|letter|message|post|caption|captions|essay|plan|proposal|story|poem|speech"
    r"|report|summary|description|listing|bio|ad|outline|cover\s+letter|resume)\b"
    r"|\b(?:business|marketing|study|budget|training|content)\s+plan\b"
    r"|\b(?:compare|pros\s+and\s+cons|step[\s-]+by[\s-]+step|in\s+detail|explain\s+(?:how|why)"
    r"|help\s+me\s+(?:plan|decide|think|write|figure)|summari[sz]e|translate|brainstorm)\b",
    re.IGNORECASE,
)


def handoff_enabled(enabled_file: str = HANDOFF_ENABLED_FILE) -> bool:
    return os.path.exists(enabled_file)


def is_heavy_task(text: str) -> bool:
    text = (text or "").strip()
    return len(text) >= LONG_MESSAGE_CHARS or bool(_HEAVY_TASK.search(text))


def tagged(answer: str, who: str) -> str:
    return f"{answer.strip()}\n(asked {who})"
