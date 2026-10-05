"""Tests for BloomBoss price suggestions: own sales + web prices, no model."""

from __future__ import annotations

import pytest

from core_service.operator import KarmoOperator
from core_service.pricing import is_pricing_question, market_prices, own_sales, plant_name, suggest
from core_service.worker_dispatch import DispatchOutcome

WEB = {"results": [
    {"title": "Alocasia Ninja Albo - $280", "url": "https://shop.example.com/albo", "snippet": "Sold out at $320"},
    {"title": "Ninja Albo rare", "url": "https://plants.example.org/x", "snippet": "Starts at $299.99, ship $15"},
    {"title": "Giant lot", "url": "https://bulk.example.net/y", "snippet": "$9,999 wholesale"},
]}


class NoModel:
    def chat_with_tools(self, **kwargs):
        raise AssertionError("pricing uses no model")


class Dispatch:
    def __init__(self, result=WEB, available=True):
        self.available = available
        self.calls = []
        self._result = result

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        return DispatchOutcome(outcome="SUCCEEDED", job_id="j", elapsed_seconds=1, poll_count=1, result=self._result)


@pytest.mark.parametrize("text", [
    "what should I price the Ninja Albo at?", "how much should I sell my begonia maculata for",
    "price suggestion for Melo Albo", "what's a Pink Nobilis worth",
])
def test_pricing_questions_are_recognised(text):
    assert is_pricing_question(text)


@pytest.mark.parametrize("text", ["how are the Ninja Albos doing", "what's the price of bitcoin", "hello"])
def test_other_questions_are_not(text):
    assert not is_pricing_question(text)


def test_plant_name_prefers_a_known_cultivar():
    assert plant_name("what should I price the Ninja Albo at?", {"ninja albo", "albo"}) == "Ninja Albo"
    assert plant_name("how much should I sell my begonia maculata for", set()) == "begonia maculata"


def test_market_prices_ignore_outliers():
    assert sorted(market_prices(WEB)) == [15.0, 280.0, 299.99, 320.0]


def test_suggestion_keeps_a_markup_over_cost():
    low = suggest({"sold": 2, "average_price": 30.0, "unit_cost": 40.0}, [20.0, 25.0])
    assert low["price"] == 60 and any("1.5x" in r for r in low["reasons"])
    assert suggest(None, [])["price"] is None
    assert suggest({"sold": 1, "average_price": 350.0}, [])["price"] == 350


def test_own_sales_reads_the_cultivar_figures():
    result = {"reports": [{"cultivar_summary": {"Ninja Albo": {"sold": 1, "revenue": "350",
                                                               "realized_profit_on_known_costs": "250.91"}}}]}
    assert own_sales(result, "ninja albo") == {"sold": 1, "average_price": 350.0, "unit_cost": 99.09}
    assert own_sales(result, "melo albo") is None


def test_a_price_question_combines_his_sales_and_the_web():
    dispatch = Dispatch()
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=dispatch).handle(
        "what should I price the Ninja Albo at?")

    assert dispatch.calls[0]["tool_id"] == "web_search"
    assert dispatch.calls[0]["arguments"] == {"query": "Ninja Albo plant price"}
    message = response["message"]
    assert message.startswith("Suggested price for Ninja Albo: $290.")
    assert "Your 1 sold went for $350.00 on average." in message
    assert "Sources: shop.example.com, plants.example.org, bulk.example.net" in message


def test_without_web_search_it_prices_from_his_own_sales():
    response = KarmoOperator(model_client=NoModel(), worker_dispatch_client=Dispatch(available=False)).handle(
        "what should I price the Ninja Albo at?")
    assert response["message"].startswith("Suggested price for Ninja Albo: $350.")
    assert "couldn't search the web" in response["message"]
