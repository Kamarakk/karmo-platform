"""Core-side glue for web search: a question about anything current
("latest", "price of", "news", "search for ...") dispatches one web_search
job to a worker (worker-runtime/app/capabilities.py), which asks its own
loopback SearXNG. KARMO answers from the returned titles, links and
snippets and names its sources. Result pages are never fetched.

Runs on KARMO-WORKER02 by default (Kamara's written go-ahead, 2026-10-03),
so the brain host never talks to search engines. Same activation boundary
as repo_intake_capability.py: needs worker_dispatch_client.available.
"""

from __future__ import annotations

import json
import re

WEB_SEARCH_TOOL_ID = "web_search"
WEB_SEARCH_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER02"
_DEADLINE_SECONDS = 45.0
MAX_QUERY_CHARS = 300

# Explicit asks to go online, and words that mean the answer is about now.
SEARCH_WORDS = re.compile(
    r"\b(search|google|look\s+up|look\s+online|online|on\s+the\s+(?:web|internet)|web|internet"
    r"|latest|news|headlines?|weather|forecast"
    r"|price\s+of|cost\s+of|how\s+much\s+(?:is|are)|going\s+rate|release\s+date)\b",
    re.IGNORECASE,
)
# Words that say Kamara wants the web, even about his own business.
EXPLICIT_WEB_WORDS = re.compile(
    r"\b(search|google|look\s+up|look\s+online|online|on\s+the\s+(?:web|internet)|web|internet)\b",
    re.IGNORECASE,
)
_LEADING_ASK = re.compile(
    r"^(?:(?:hey\s+)?(?:karmo|jarvis)[,\s]+)?(?:(?:can|could|would)\s+you\s+|please\s+)?"
    r"(?:search\s+(?:the\s+(?:web|internet)\s+|online\s+)?(?:for\s+)?|google\s+|look\s+up\s+|find\s+out\s+)?",
    re.IGNORECASE,
)


class WebSearchCapabilityError(RuntimeError):
    pass


def is_search_question(text: str) -> bool:
    return bool(SEARCH_WORDS.search(text or ""))


def wants_the_web(text: str) -> bool:
    return bool(EXPLICIT_WEB_WORDS.search(text or ""))


def search_query(text: str) -> str:
    """Kamara's message minus the "karmo, can you search for" lead-in."""
    query = _LEADING_ASK.sub("", (text or "").strip(), count=1).strip(" ?!.") or (text or "").strip()
    return query[:MAX_QUERY_CHARS]


def manifest() -> dict:
    return {
        "tool_id": WEB_SEARCH_TOOL_ID,
        "domain": "web",
        "version": WEB_SEARCH_TOOL_VERSION,
        "description": (
            "Search the web for anything current (prices, news, how-tos) through KARMO's own "
            "SearXNG on a worker. Returns titles, links and snippets; never opens the pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "maxLength": MAX_QUERY_CHARS}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"results": {"type": "array"}}},
        "capability_class": "READ",
        "read_scope": "public web search results",
        "write_scope": "none",
        "external_side_effects": "one dispatched job to a worker; the worker's SearXNG queries public search engines",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core; the worker's SearXNG container reaches search engines",
        "secret_requirements": "none beyond the existing worker-dispatch DSN",
        "invocation_identity": "karmo-chat-model",
        "timeout_seconds": int(_DEADLINE_SECONDS),
        "retry_policy": "none",
        "idempotent": True,
        "idempotency_mechanism": "read-only search; repeating it changes nothing",
        "rollback_or_compensation": "not applicable",
        "health_check": "search for a common word and confirm at least one result",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available; SearXNG on the worker at 127.0.0.1:8888",
        "observability": "structured operator response",
        "failure_isolation": "a dispatch failure or timeout is reported to the model as data, never hangs the turn",
    }


def dispatch_web_search(worker_dispatch_client, *, worker_id: str, query: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        raise WebSearchCapabilityError("query must be non-empty text")
    if not worker_dispatch_client.available:
        raise WebSearchCapabilityError("worker dispatch is not activated -- no worker-dispatch DSN configured")
    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=WEB_SEARCH_TOOL_ID,
        tool_version=WEB_SEARCH_TOOL_VERSION,
        arguments={"query": query.strip()[:MAX_QUERY_CHARS]},
        total_deadline_seconds=_DEADLINE_SECONDS,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise WebSearchCapabilityError(f"{outcome.outcome}: {outcome.error}")
    if not isinstance(outcome.result.get("results"), list):
        raise WebSearchCapabilityError("worker returned an invalid web_search result")
    return outcome.result


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    def _handler(arguments: dict) -> dict:
        return dispatch_web_search(worker_dispatch_client, worker_id=worker_id, query=arguments.get("query"))
    return _handler


def web_results_digest(result) -> str:
    """The tool-result text the chat model reads: numbered results, short,
    with each link so the answer can name its sources."""
    if not isinstance(result, dict):
        return json.dumps({"error": "no web results"})
    results = result.get("results") or []
    if not results:
        return "WEB SEARCH: no results found."
    lines = ["WEB SEARCH RESULTS (public web, may be wrong or out of date):"]
    for number, item in enumerate(results, 1):
        lines.append(f"[{number}] {item.get('title', '')} -- {item.get('url', '')}")
        if item.get("snippet"):
            lines.append(f"    {item['snippet']}")
    return "\n".join(lines)


def sources_line(result) -> str:
    """'Sources: example.com, other.org' for the end of an answer."""
    if not isinstance(result, dict):
        return ""
    hosts = []
    for item in result.get("results") or []:
        match = re.match(r"https?://(?:www\.)?([^/:?#]+)", str(item.get("url", "")))
        if match and match.group(1) not in hosts:
            hosts.append(match.group(1))
    return ("Sources: " + ", ".join(hosts[:3])) if hosts else ""
