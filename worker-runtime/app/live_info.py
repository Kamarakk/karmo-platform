"""Live info for KARMO's Tools panel and chat: a place on the map, the
weather, a market update and the newest actively exploited
vulnerabilities. Keyless public sources only, each pinned to the fixed
hosts in ALLOWED_HOSTS (redirects included). Read-only; nothing is sent
except the place or ticker Kamara asked about.

- place:   OpenStreetMap Nominatim search
- weather: Nominatim for the place, then Open-Meteo forecast
- market:  Yahoo Finance chart endpoint (unofficial; may rate-limit)
- cyber:   CISA Known Exploited Vulnerabilities catalog
"""

from __future__ import annotations

import json
import re
import urllib.parse
from urllib import error, request

ALLOWED_HOSTS = (
    "nominatim.openstreetmap.org",
    "api.open-meteo.com",
    "query1.finance.yahoo.com",
    "www.cisa.gov",
)
KINDS = ("place", "weather", "market", "cyber")
MAX_QUERY_CHARS = 120
MAX_SYMBOLS = 6
DEFAULT_PLACE = "San Diego, California"
DEFAULT_SYMBOLS = ("^GSPC", "^DJI", "^IXIC", "BTC-USD")
SYMBOL_NAMES = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq", "BTC-USD": "Bitcoin"}
HTTP_TIMEOUT_SECONDS = 12
_USER_AGENT = "KARMO/1.0 (self-hosted personal assistant)"
_SYMBOL = re.compile(r"^[A-Za-z0-9^.=\-]{1,12}$")
_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# WMO weather codes, as Open-Meteo reports them.
_WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


class LiveInfoError(RuntimeError):
    pass


class _PinnedRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname not in ALLOWED_HOSTS:
            raise LiveInfoError(f"redirect to a host that is not allowed: {urllib.parse.urlsplit(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = request.build_opener(_PinnedRedirects)


def _http_get_json(url: str, max_bytes: int = 2_000_000):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise LiveInfoError(f"host not allowed: {parts.hostname}")
    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
    try:
        with _OPENER.open(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read(max_bytes).decode("utf-8"))
    except error.HTTPError as exc:
        raise LiveInfoError(f"{parts.hostname} answered HTTP {exc.code}") from exc
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise LiveInfoError(f"{parts.hostname} failed: {type(exc).__name__}") from exc


def _clean(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def lookup_place(query: str, http_get=_http_get_json) -> dict:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0})
    data = http_get(url)
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise LiveInfoError(f"no place found for {query!r}")
    hit = data[0]
    try:
        lat, lon = float(hit["lat"]), float(hit["lon"])
        bbox = [float(v) for v in hit.get("boundingbox") or []]
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveInfoError("map service returned an unusable place") from exc
    place = {"name": _clean(hit.get("display_name"), 200), "lat": round(lat, 5), "lon": round(lon, 5),
             "type": _clean(hit.get("type"), 40)}
    if len(bbox) == 4:  # south, north, west, east
        place["bbox"] = [round(v, 5) for v in bbox]
    return place


def weather(query: str, http_get=_http_get_json) -> dict:
    place = lookup_place(query, http_get)
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": place["lat"], "longitude": place["lon"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "timezone": "auto", "forecast_days": 3,
    })
    data = http_get(url)
    if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
        raise LiveInfoError("weather service returned no current conditions")
    now = data["current"]
    days = []
    daily = data.get("daily") if isinstance(data.get("daily"), dict) else {}
    for i, day in enumerate((daily.get("time") or [])[:3]):
        def pick(key):
            values = daily.get(key) or []
            return _number(values[i]) if i < len(values) else None
        days.append({"date": _clean(day, 10), "high_f": pick("temperature_2m_max"), "low_f": pick("temperature_2m_min"),
                     "rain_chance": pick("precipitation_probability_max"),
                     "sky": _WEATHER_CODES.get(pick("weather_code"), "")})
    return {"place": place["name"], "lat": place["lat"], "lon": place["lon"],
            "now": {"temp_f": _number(now.get("temperature_2m")), "feels_f": _number(now.get("apparent_temperature")),
                    "humidity": _number(now.get("relative_humidity_2m")), "wind_mph": _number(now.get("wind_speed_10m")),
                    "sky": _WEATHER_CODES.get(_number(now.get("weather_code")), "")},
            "days": days}


def _quote(symbol: str, http_get) -> dict:
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol, safe="")
           + "?" + urllib.parse.urlencode({"range": "1d", "interval": "1d"}))
    data = http_get(url)
    try:
        meta = data["chart"]["result"][0]["meta"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LiveInfoError(f"no quote for {symbol}") from exc
    price = _number(meta.get("regularMarketPrice"))
    previous = _number(meta.get("chartPreviousClose")) or _number(meta.get("previousClose"))
    if price is None:
        raise LiveInfoError(f"no quote for {symbol}")
    change = round(price - previous, 2) if previous else None
    return {"symbol": symbol, "name": SYMBOL_NAMES.get(symbol) or _clean(meta.get("shortName") or symbol, 40),
            "price": round(price, 2), "change": change,
            "change_pct": round(change / previous * 100, 2) if previous and change is not None else None,
            "currency": _clean(meta.get("currency"), 8), "as_of": _number(meta.get("regularMarketTime"))}


def market(symbols, http_get=_http_get_json) -> dict:
    quotes, missing = [], []
    for symbol in symbols:
        try:
            quotes.append(_quote(symbol, http_get))
        except LiveInfoError:
            missing.append(symbol)
    if not quotes:
        raise LiveInfoError("no market quotes came back (the quote service may be rate-limiting)")
    return {"quotes": quotes, "missing": missing}


def cyber(http_get=_http_get_json, limit: int = 5) -> dict:
    data = http_get(_KEV_URL, max_bytes=12_000_000)
    rows = data.get("vulnerabilities") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise LiveInfoError("CISA catalog returned no vulnerabilities")
    rows = [r for r in rows if isinstance(r, dict)]
    rows.sort(key=lambda r: (str(r.get("dateAdded") or ""), str(r.get("cveID") or "")), reverse=True)
    items = [{
        "cve": _clean(r.get("cveID"), 30), "vendor": _clean(r.get("vendorProject"), 60),
        "product": _clean(r.get("product"), 80), "name": _clean(r.get("vulnerabilityName"), 160),
        "added": _clean(r.get("dateAdded"), 10), "due": _clean(r.get("dueDate"), 10),
        "ransomware": _clean(r.get("knownRansomwareCampaignUse"), 10) == "Known",
        "summary": _clean(r.get("shortDescription"), 300),
    } for r in rows[:limit]]
    return {"source": "CISA Known Exploited Vulnerabilities", "catalog_date": _clean(data.get("dateReleased"), 25),
            "total": len(rows), "items": items}


def _symbols(raw) -> list[str]:
    if raw in (None, "", []):
        return list(DEFAULT_SYMBOLS)
    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw.strip())
    if not isinstance(raw, list):
        raise LiveInfoError("symbols must be a list of tickers")
    picked = []
    for item in raw:
        item = str(item).strip().lstrip("$").upper()
        if not item:
            continue
        if not _SYMBOL.match(item):
            raise LiveInfoError(f"not a ticker: {item[:20]!r}")
        if item not in picked:
            picked.append(item)
    if not picked:
        return list(DEFAULT_SYMBOLS)
    return picked[:MAX_SYMBOLS]


def live_info(payload: dict, http_get=_http_get_json) -> dict:
    kind = payload.get("kind")
    if kind not in KINDS:
        raise LiveInfoError(f"kind must be one of {', '.join(KINDS)}")
    query = payload.get("query") or ""
    if not isinstance(query, str) or len(query) > MAX_QUERY_CHARS:
        raise LiveInfoError(f"query must be text up to {MAX_QUERY_CHARS} characters")
    query = query.strip()
    if kind == "place":
        if not query:
            raise LiveInfoError("say which place to look up")
        return {"kind": kind, "place": lookup_place(query, http_get)}
    if kind == "weather":
        return {"kind": kind, "weather": weather(query or DEFAULT_PLACE, http_get)}
    if kind == "market":
        return {"kind": kind, "market": market(_symbols(payload.get("symbols") or query), http_get)}
    return {"kind": kind, "cyber": cyber(http_get)}
