"""Core-side glue for live info: a place on the map, the weather, a market
update and the newest actively exploited vulnerabilities. Dispatches one
live_info job to a worker (worker-runtime/app/live_info.py), which reads
fixed keyless public sources, so the brain host never talks to them. The
web interface's Tools panel calls it directly; in chat, a clear ask
("weather in Chula Vista", "market update", "cyber update", "map of
Monrovia") is answered from the result without a model, so no figure is
ever made up. Same activation boundary as web_search_capability.py.
"""

from __future__ import annotations

import re
import urllib.parse

LIVE_INFO_TOOL_ID = "live_info"
LIVE_INFO_TOOL_VERSION = "1.0.0"
_DEFAULT_WORKER_ID = "KARMO-WORKER02"
_DEADLINE_SECONDS = 40.0
KINDS = ("place", "weather", "market", "cyber")
MAX_QUERY_CHARS = 120

_LEAD = r"^(?:(?:hey\s+)?(?:karmo|jarvis)[,\s]+)?(?:(?:can|could|would)\s+you\s+|please\s+)?"
_WEATHER = re.compile(
    _LEAD + r"(?:(?:what(?:'s|\s+is)|how(?:'s|\s+is)|show(?:\s+me)?|give\s+me|get(?:\s+me)?|check)\s+)?(?:the\s+)?"
    r"(?:weather|forecast)(?:\s+(?:like|forecast|today|tomorrow|this\s+week|right\s+now|now))*"
    r"(?:\s+(?:in|for|at|near)\s+(?P<place>[^?!.]{2,80}?))?(?:\s+(?:today|tomorrow|this\s+week|right\s+now|now))?\s*[?!.]*$",
    re.IGNORECASE,
)
_MARKET = re.compile(
    _LEAD + r"(?:(?:what(?:'s|\s+is)|how(?:'s|\s+is|\s+are)|show(?:\s+me)?|give\s+me|get(?:\s+me)?|check)\s+)?(?:the\s+|a\s+)?"
    r"(?:market\s+update|markets?\s+(?:today|update|doing|now)|stock\s+market(?:\s+(?:today|update|doing|now))?|markets?"
    r"|stocks?\s+(?:today|update))(?:\s+doing)?(?:\s+today)?\s*[?!.]*$",
    re.IGNORECASE,
)
_CYBER = re.compile(
    _LEAD + r"(?:(?:what(?:'s|\s+is)|show(?:\s+me)?|give\s+me|get(?:\s+me)?|check)\s+)?(?:the\s+|a\s+|my\s+)?(?:latest\s+|today'?s\s+)?"
    r"(?:cyber\s*security|cyber|security|threat)\s+(?:update|news|brief(?:ing)?|alerts?)(?:\s+today)?\s*[?!.]*$"
    r"|" + _LEAD + r".{0,40}\b(?:actively\s+)?exploited\s+vulnerabilit(?:y|ies)\b.{0,40}$"
    r"|" + _LEAD + r".{0,30}\b(?:cisa\s+kev|kev\s+catalog|known\s+exploited)\b.{0,40}$",
    re.IGNORECASE,
)
_MAP = re.compile(
    _LEAD + r"(?:(?:show|pull\s+up|bring\s+up|open)\s+(?:me\s+)?)?(?:a\s+|the\s+)?(?:map|satellite\s+view|god'?s\s+eye(?:\s+view)?)\s+(?:of|for)\s+(?P<a>[^?!]{2,100}?)\s*[?!.]*$"
    r"|" + _LEAD + r"(?:show|find|locate|pin|look\s+up|where\s+is)\s+(?:me\s+)?(?P<b>[^?!]{2,100}?)\s+on\s+(?:a|the)\s+map\s*[?!.]*$",
    re.IGNORECASE,
)


class LiveInfoCapabilityError(RuntimeError):
    pass


def chat_ask(text: str) -> tuple[str, dict] | None:
    """(kind, arguments) for a clear live-info ask, else None."""
    text = (text or "").strip()
    if not text or len(text) > 160:
        return None
    match = _MAP.match(text)
    if match:
        place = match.group("a") or match.group("b")
        return "place", {"kind": "place", "query": place.strip()[:MAX_QUERY_CHARS]}
    match = _WEATHER.match(text)
    if match:
        return "weather", {"kind": "weather", "query": (match.group("place") or "").strip()[:MAX_QUERY_CHARS]}
    if _CYBER.match(text):
        return "cyber", {"kind": "cyber"}
    if _MARKET.match(text):
        return "market", {"kind": "market"}
    return None


def manifest() -> dict:
    return {
        "tool_id": LIVE_INFO_TOOL_ID,
        "domain": "web",
        "version": LIVE_INFO_TOOL_VERSION,
        "description": (
            "Look up a place on the map, the weather, a market update or the newest actively "
            "exploited vulnerabilities, from fixed keyless public sources, through a worker."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(KINDS)},
                "query": {"type": "string", "maxLength": MAX_QUERY_CHARS},
                "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "properties": {"kind": {"type": "string"}}},
        "capability_class": "READ",
        "read_scope": "public map, weather, market quote and CISA vulnerability data",
        "write_scope": "none",
        "external_side_effects": "one dispatched job to a worker; the worker queries the fixed public sources",
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": "none from Core; the worker reaches only live_info.ALLOWED_HOSTS",
        "secret_requirements": "none beyond the existing worker-dispatch DSN",
        "invocation_identity": "karmo-webui",
        "timeout_seconds": int(_DEADLINE_SECONDS),
        "retry_policy": "none",
        "idempotent": True,
        "idempotency_mechanism": "read-only lookup; repeating it changes nothing",
        "rollback_or_compensation": "not applicable",
        "health_check": "weather for the default place returns current conditions",
        "deprecation_policy": "explicit version replacement",
        "dependencies": "worker_dispatch_client.available; outbound HTTPS from the worker",
        "observability": "structured operator response",
        "failure_isolation": "a dispatch failure or timeout is returned as an error, never hangs the request",
    }


def dispatch_live_info(worker_dispatch_client, *, worker_id: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict) or arguments.get("kind") not in KINDS:
        raise LiveInfoCapabilityError(f"kind must be one of {', '.join(KINDS)}")
    if not worker_dispatch_client.available:
        raise LiveInfoCapabilityError("worker dispatch is not activated -- no worker-dispatch DSN configured")
    clean = {"kind": arguments["kind"]}
    if isinstance(arguments.get("query"), str) and arguments["query"].strip():
        clean["query"] = arguments["query"].strip()[:MAX_QUERY_CHARS]
    if isinstance(arguments.get("symbols"), list):
        clean["symbols"] = [str(s)[:12] for s in arguments["symbols"][:6]]
    outcome = worker_dispatch_client.dispatch(
        worker_id=worker_id,
        tool_id=LIVE_INFO_TOOL_ID,
        tool_version=LIVE_INFO_TOOL_VERSION,
        arguments=clean,
        total_deadline_seconds=_DEADLINE_SECONDS,
    )
    if outcome.outcome != "SUCCEEDED" or not isinstance(outcome.result, dict):
        raise LiveInfoCapabilityError(f"{outcome.outcome}: {outcome.error}")
    if outcome.result.get("kind") != clean["kind"]:
        raise LiveInfoCapabilityError("worker returned an invalid live_info result")
    return outcome.result


def handler(worker_dispatch_client, *, worker_id: str = _DEFAULT_WORKER_ID):
    def _handler(arguments: dict) -> dict:
        return dispatch_live_info(worker_dispatch_client, worker_id=worker_id, arguments=arguments)
    return _handler


def map_links(lat, lon, name: str = "") -> dict:
    q = urllib.parse.quote(name or f"{lat},{lon}")
    return {
        "map": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}",
        "satellite": f"https://maps.apple.com/?ll={lat},{lon}&q={q}&t=k",
        "google": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
    }


def _deg(value) -> str:
    return f"{round(value)}°F" if isinstance(value, (int, float)) else "?"


def _signed(value, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{'+' if value >= 0 else '−'}{abs(value):,.2f}{suffix}"


def format_answer(result: dict) -> str:
    """A short chat answer from a live_info result, with its source."""
    kind = result.get("kind")
    if kind == "place":
        p = result.get("place") or {}
        links = map_links(p.get("lat"), p.get("lon"), p.get("name", ""))
        return (f"**{p.get('name', 'That place')}**\n{p.get('lat')}, {p.get('lon')}\n"
                f"[Map]({links['map']}) · [Satellite]({links['satellite']}) · [Google Maps]({links['google']})\n"
                "Source: OpenStreetMap")
    if kind == "weather":
        w = result.get("weather") or {}
        now = w.get("now") or {}
        first = (w.get("place") or "").split(",")[0] or "there"
        lines = [f"**{first}** now: {_deg(now.get('temp_f'))}, {now.get('sky') or 'n/a'}, "
                 f"feels like {_deg(now.get('feels_f'))}, wind {round(now.get('wind_mph') or 0)} mph."]
        labels = ["Today", "Tomorrow"]
        for i, day in enumerate(w.get("days") or []):
            label = labels[i] if i < len(labels) else day.get("date", "")
            rain = day.get("rain_chance")
            lines.append(f"- {label}: {_deg(day.get('high_f'))} / {_deg(day.get('low_f'))}, {day.get('sky') or 'n/a'}"
                         + (f", {rain}% rain" if isinstance(rain, (int, float)) else ""))
        lines.append("Source: Open-Meteo")
        return "\n".join(lines)
    if kind == "market":
        m = result.get("market") or {}
        lines = []
        for q in m.get("quotes") or []:
            lines.append(f"- {q.get('name')}: {q.get('price'):,.2f} ({_signed(q.get('change'))}, {_signed(q.get('change_pct'), '%')})"
                         if isinstance(q.get("price"), (int, float)) else f"- {q.get('name')}: n/a")
        if m.get("missing"):
            lines.append(f"No quote for {', '.join(m['missing'])}.")
        lines.append("Source: Yahoo Finance (delayed). Not financial advice.")
        return "**Markets**\n" + "\n".join(lines)
    if kind == "cyber":
        c = result.get("cyber") or {}
        lines = ["**Newest actively exploited vulnerabilities (CISA)**"]
        for item in c.get("items") or []:
            flag = " · ransomware" if item.get("ransomware") else ""
            lines.append(f"- {item.get('cve')} {item.get('vendor')} {item.get('product')}: "
                         f"added {item.get('added')}, fix by {item.get('due')}{flag}")
        lines.append("Source: CISA Known Exploited Vulnerabilities catalog")
        return "\n".join(lines)
    return "I couldn't read that result."
