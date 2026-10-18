import pytest

import live_info
from capability_manifest import NETWORK_CAPABILITY_HOSTS, SAFE_CAPABILITIES
from live_info import ALLOWED_HOSTS, LiveInfoError
from sandbox import SandboxError

NOMINATIM = [{"display_name": "Chula Vista, San Diego County, California, United States", "lat": "32.6400541",
              "lon": "-117.0841955", "type": "city", "boundingbox": ["32.57", "32.68", "-117.13", "-116.92"]}]
METEO = {"current": {"temperature_2m": 71.4, "apparent_temperature": 70.9, "relative_humidity_2m": 60,
                     "weather_code": 2, "wind_speed_10m": 8.2},
         "daily": {"time": ["2026-10-18", "2026-10-19", "2026-10-20"], "weather_code": [0, 61, 3],
                   "temperature_2m_max": [74, 70, 69], "temperature_2m_min": [60, 59, 58],
                   "precipitation_probability_max": [0, 40, 10]}}


def chart(price, previous, name="Apple Inc."):
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "chartPreviousClose": previous,
                                           "currency": "USD", "shortName": name, "regularMarketTime": 1790000000}}]}}


def fake(routes, seen=None):
    def get(url, max_bytes=2_000_000):
        if seen is not None:
            seen.append(url)
        for prefix, value in routes.items():
            if url.startswith(prefix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(url)
    return get


def test_place_lookup():
    out = live_info.live_info({"kind": "place", "query": "Chula Vista"},
                              fake({"https://nominatim.openstreetmap.org/": NOMINATIM}))
    assert out["place"]["lat"] == 32.64005 and out["place"]["bbox"][0] == 32.57
    with pytest.raises(LiveInfoError):
        live_info.live_info({"kind": "place", "query": ""}, fake({}))
    with pytest.raises(LiveInfoError, match="no place"):
        live_info.live_info({"kind": "place", "query": "zzz"}, fake({"https://nominatim": []}))


def test_weather_defaults_to_san_diego():
    seen = []
    out = live_info.live_info({"kind": "weather"}, fake({"https://nominatim": NOMINATIM, "https://api.open-meteo.com/": METEO}, seen))
    assert "San+Diego" in seen[0]
    w = out["weather"]
    assert w["now"]["temp_f"] == 71.4 and w["now"]["sky"] == "partly cloudy"
    assert [d["rain_chance"] for d in w["days"]] == [0, 40, 10] and w["days"][1]["sky"] == "light rain"


def test_market_keeps_good_quotes_and_names_missing_ones():
    def get(url, max_bytes=0):
        if "AAPL" in url:
            return chart(200.0, 190.0)
        raise LiveInfoError("HTTP 429")
    out = live_info.live_info({"kind": "market", "query": "aapl, $msft"}, get)
    assert out["market"]["quotes"][0] == {"symbol": "AAPL", "name": "Apple Inc.", "price": 200.0, "change": 10.0,
                                          "change_pct": 5.26, "currency": "USD", "as_of": 1790000000}
    assert out["market"]["missing"] == ["MSFT"]
    with pytest.raises(LiveInfoError, match="no market quotes"):
        live_info.live_info({"kind": "market"}, lambda url, max_bytes=0: (_ for _ in ()).throw(LiveInfoError("x")))


def test_market_defaults_and_rejects_junk_tickers():
    seen = []
    live_info.live_info({"kind": "market"}, fake({"https://query1.finance.yahoo.com/": chart(1, 1)}, seen))
    assert len(seen) == 4 and "%5EGSPC" in seen[0]
    with pytest.raises(LiveInfoError, match="not a ticker"):
        live_info.live_info({"kind": "market", "symbols": ["../etc"]}, fake({}))


def test_cyber_returns_the_newest_five():
    rows = [{"cveID": f"CVE-2026-{i:04d}", "vendorProject": "V", "product": "P", "dateAdded": f"2026-10-{i:02d}",
             "dueDate": "2026-11-01", "knownRansomwareCampaignUse": "Known" if i == 9 else "Unknown"} for i in range(1, 10)]
    out = live_info.live_info({"kind": "cyber"}, fake({"https://www.cisa.gov/": {"vulnerabilities": rows, "dateReleased": "x"}}))
    items = out["cyber"]["items"]
    assert [i["cve"] for i in items] == [f"CVE-2026-{i:04d}" for i in (9, 8, 7, 6, 5)]
    assert items[0]["ransomware"] and not items[1]["ransomware"] and out["cyber"]["total"] == 9


def test_bad_kind_and_long_query_are_refused():
    with pytest.raises(LiveInfoError):
        live_info.live_info({"kind": "shell"}, fake({}))
    with pytest.raises(LiveInfoError):
        live_info.live_info({"kind": "place", "query": "x" * 200}, fake({}))


def test_only_pinned_https_hosts_are_reachable():
    with pytest.raises(LiveInfoError, match="host not allowed"):
        live_info._http_get_json("https://evil.example/x")
    with pytest.raises(LiveInfoError, match="host not allowed"):
        live_info._http_get_json("http://api.open-meteo.com/v1/forecast")
    with pytest.raises(LiveInfoError, match="redirect"):
        live_info._PinnedRedirects().redirect_request(None, None, 302, "", {}, "https://evil.example/")


def test_manifest_pins_the_same_hosts_and_handler_is_registered(monkeypatch):
    assert NETWORK_CAPABILITY_HOSTS["live_info"] == ALLOWED_HOSTS
    assert SAFE_CAPABILITIES["live_info"]["network_required"] is True
    import capabilities
    monkeypatch.setattr(capabilities, "live_info", lambda payload: (_ for _ in ()).throw(LiveInfoError("down")))
    with pytest.raises(SandboxError, match="live_info: down"):
        capabilities._live_info({"kind": "cyber"}, sandbox_root=None, allowed_root=None, timeout_seconds=30)
