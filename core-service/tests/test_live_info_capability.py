"""Tests for live info: which chat asks it answers, the answer text, the
Tools panel endpoint, and the panel on the page."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request

import pytest

from core_service import webui
from core_service.live_info_capability import chat_ask, format_answer
from core_service.operator import KarmoOperator
from core_service.worker_dispatch import DispatchOutcome

WEATHER = {"kind": "weather", "weather": {
    "place": "Chula Vista, San Diego County, California", "lat": 32.64, "lon": -117.08,
    "now": {"temp_f": 71.4, "feels_f": 70.9, "humidity": 60, "wind_mph": 8.2, "sky": "partly cloudy"},
    "days": [{"date": "2026-10-18", "high_f": 74, "low_f": 60, "rain_chance": 0, "sky": "clear"},
             {"date": "2026-10-19", "high_f": 70, "low_f": 59, "rain_chance": 40, "sky": "light rain"}]}}


class FakeDispatch:
    def __init__(self, outcome):
        self.available = True
        self.outcome = outcome
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return self.outcome


class NoModel:
    def __init__(self):
        self.requests = []

    def chat_with_tools(self, **kwargs):
        self.requests.append(kwargs)
        return {"content": "model answer", "tool_calls": None}


@pytest.mark.parametrize("text,kind,query", [
    ("weather", "weather", ""),
    ("What's the weather like in Chula Vista?", "weather", "Chula Vista"),
    ("forecast for Monrovia, Liberia", "weather", "Monrovia, Liberia"),
    ("market update", "market", None),
    ("how are the markets doing today?", "market", None),
    ("Karmo, give me the latest cybersecurity update", "cyber", None),
    ("any new actively exploited vulnerabilities?", "cyber", None),
    ("map of Monrovia", "place", "Monrovia"),
    ("show me Balboa Park on the map", "place", "Balboa Park"),
    ("god's eye view of Petco Park", "place", "Petco Park"),
])
def test_clear_asks_are_recognised(text, kind, query):
    got = chat_ask(text)
    assert got is not None and got[0] == kind
    if query is not None:
        assert got[1]["query"] == query


@pytest.mark.parametrize("text", [
    "how much is the Ninja Albo", "what is the price of bitcoin", "whether I should repot",
    "tell me about the weather patterns in El Nino years and how they affect plants", "locate my invoices",
])
def test_other_questions_are_left_alone(text):
    assert chat_ask(text) is None


def test_weather_is_answered_on_worker02_without_a_model():
    dispatch = FakeDispatch(DispatchOutcome(outcome="SUCCEEDED", job_id="j", elapsed_seconds=1.0, poll_count=1, result=WEATHER))
    model = NoModel()
    response = KarmoOperator(model_client=model, worker_dispatch_client=dispatch).handle("weather in Chula Vista")
    assert dispatch.calls[0]["tool_id"] == "live_info" and dispatch.calls[0]["worker_id"] == "KARMO-WORKER02"
    assert dispatch.calls[0]["arguments"] == {"kind": "weather", "query": "Chula Vista"}
    assert model.requests == []
    assert response["message"].startswith("**Chula Vista** now: 71°F, partly cloudy")
    assert "Tomorrow: 70°F / 59°F, light rain, 40% rain" in response["message"]


def test_a_failed_lookup_falls_back_to_normal_chat():
    dispatch = FakeDispatch(DispatchOutcome(outcome="FAILED", job_id="j", elapsed_seconds=1.0, poll_count=1, error="down"))
    operator = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch)
    assert operator._live_info_chat("market update") is None
    assert operator._live_info_chat("hello there") is None


def test_answers_for_each_kind_name_their_source():
    place = format_answer({"kind": "place", "place": {"name": "Balboa Park", "lat": 32.73, "lon": -117.15}})
    assert "maps.apple.com/?ll=32.73,-117.15" in place and "&t=k" in place and "OpenStreetMap" in place
    market = format_answer({"kind": "market", "market": {"quotes": [
        {"name": "S&P 500", "price": 6000.5, "change": -12.25, "change_pct": -0.2}], "missing": ["BTC-USD"]}})
    assert "S&P 500: 6,000.50 (−12.25, −0.20%)" in market and "No quote for BTC-USD" in market
    cyber = format_answer({"kind": "cyber", "cyber": {"items": [
        {"cve": "CVE-2026-1", "vendor": "Cisco", "product": "IOS XE", "added": "2026-10-17", "due": "2026-11-07", "ransomware": True}]}})
    assert "CVE-2026-1 Cisco IOS XE: added 2026-10-17, fix by 2026-11-07 · ransomware" in cyber


class ToolsOperator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def dispatch_live_info(self, *, arguments):
        self.calls.append(arguments)
        return self.result


def _post(server, body):
    req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/tools", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, (json.loads(exc.read() or b"{}"))


@pytest.fixture
def tools_server():
    import threading
    from http.server import HTTPServer

    def start(result):
        fake = ToolsOperator(result)
        webui._Handler.operator = fake
        server = HTTPServer(("127.0.0.1", 0), webui._Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server, fake

    servers = []
    yield start
    for server in servers:
        server.shutdown()


def test_tools_endpoint_passes_kind_and_query(tools_server):
    server, fake = tools_server(WEATHER)
    assert _post(server, {"kind": "weather", "query": "Chula Vista", "extra": 1}) == (200, WEATHER)
    assert fake.calls == [{"kind": "weather", "query": "Chula Vista"}]
    assert _post(server, {"query": "x"})[0] == 400


def test_tools_endpoint_reports_errors_as_400(tools_server):
    server, _ = tools_server({"error": "worker dispatch is not activated"})
    assert _post(server, {"kind": "cyber"}) == (400, {"error": "worker dispatch is not activated"})


def test_page_has_the_tools_panel_and_its_script_parses(tmp_path):
    page = webui._PAGE.decode("utf-8")
    assert 'id="opentools"' in page and 'id="tools"' in page
    for tool in ("place", "weather", "market", "cyber"):
        assert f'data-tool="{tool}"' in page
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    script = tmp_path / "page.js"
    script.write_text(re.search(r"<script>(.*)</script>", page, re.S).group(1), encoding="utf-8")
    subprocess.run(["node", "--check", str(script)], check=True)
