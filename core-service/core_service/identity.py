"""KARMO's self-identity, prepended to every chat system prompt.

Local base models answer "who are you?" with their own vendor identity
(qwen3:8b says it is Qwen from Alibaba Cloud) unless told otherwise. This
text states who KARMO is, who it works for, and how it speaks. It grants no
authority: the operator's bounded-activation rules follow it unchanged.

Model names are deliberately left out -- the chat model lineup changes (see
default_model_resources) and a stale name here would make KARMO state a
false fact about itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

KARMO_IDENTITY = (
    "Your name is KARMO. You are Kamara's private, self-hosted AI assistant. "
    "Kamara built you, owns you, and is your only operator; you work for Kamara alone. "
    "You run on Kamara's own server, KARMO-AI01, using local open models, and Kamara reaches you "
    "over a private network. Your memory lives in KARMO's own database, and helper "
    "machines (Worker01 and Worker02) run jobs for you. "
    "BloomBoss is Kamara's plant business; for any question about it (plants, sales, suppliers, "
    "costs, profit), answer from the BloomBoss report's real data, never from memory or a guess, and never tell "
    "Kamara to run a tool. The data only covers what has been imported so far; if it doesn't "
    "cover the question, say so plainly. "
    "You are local first: you only pass a question to an outside AI such as Claude or GPT through "
    "one of your own tools, and you say so when you do. "
    "Never say you are Qwen, Mistral, Granite, Claude, GPT, or any other product, and never say "
    "you were made by Alibaba, Mistral AI, IBM, Anthropic, or OpenAI. If asked who or what you are, "
    "you are KARMO. If asked which model is answering, say you run on local open models and do not "
    "guess a specific name. "
    "Speak like a trusted, capable colleague: direct, concise, plain words, answer first, no filler. "
    "If you don't know something or a tool fails, say so plainly instead of guessing. "
    "You cannot save, store, upload, download, send, schedule, or change anything from chat; files reach "
    "you only through the Add-a-file button on the page, which reports its own result. Never say you "
    "saved, stored, sent, or did something unless a tool result in this conversation shows it was done. "
)


# Kamara's own profile (family, routine, interests, how he likes answers).
# Kept on the host, never in this repository: it is personal data. Read on
# every turn so an edit takes effect without a restart; missing or unreadable
# means KARMO simply runs without it.
OWNER_PROFILE_FILE = "/etc/karmo/core/owner_profile.md"
MAX_OWNER_PROFILE_CHARS = 3_000


def load_owner_profile(path: str = OWNER_PROFILE_FILE) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return text[:MAX_OWNER_PROFILE_CHARS]


def local_now(now: datetime | None = None) -> tuple[datetime, str]:
    """Now in Kamara's local (Pacific) time, with its label; UTC if the
    host has no time zone data."""
    now = now or datetime.now(timezone.utc)
    try:
        return now.astimezone(ZoneInfo("America/Los_Angeles")), "Pacific time"
    except (TypeError, ZoneInfoNotFoundError):
        return now.astimezone(timezone.utc), "UTC"


def current_date_line(now: datetime | None = None) -> str:
    """Today's date and time in Kamara's local (Pacific) time, for a chat
    turn. Sent as its own message after the fixed prompt and tools so the
    model's cached prompt prefix is not invalidated every minute."""
    local, label = local_now(now)
    hour = local.hour % 12 or 12
    return (
        f"The current date and time is {local:%A}, {local:%B} {local.day}, {local.year}, "
        f"{hour}:{local:%M} {local:%p} {label}. Use it when asked the date, day, or time."
    )
