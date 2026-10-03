"""BloomBoss price suggestions (item 4 of the five Kamara approved in
writing, 2026-10-03). "What should I price the Ninja Albo at?" combines:

- his own imported sales of that plant (average sale price, unit cost
  where known), and
- current public prices for it from web search (the $ amounts in the top
  results' titles and snippets),

into one suggestion with its reasons and sources. Every figure comes from
those two inputs; no model is asked, so nothing is invented.
"""

from __future__ import annotations

import re
import statistics

_PRICING = re.compile(
    r"\b(?:what\s+(?:should|do|would|can)\s+i\s+(?:price|charge|sell|list|ask)"
    r"|how\s+much\s+(?:should|do|would|can)\s+i\s+(?:price|charge|sell|list|ask)"
    r"|price\s+(?:suggestion|check|recommendation)|suggest\s+a\s+price|pricing\s+for|what(?:'s|\s+is)\s+.+\s+worth)\b",
    re.IGNORECASE,
)
_FILLER = re.compile(
    r"\b(?:karmo|what|whats|what's|should|would|could|can|do|does|i|me|my|the|a|an|at|for|how|much|price|prices"
    r"|pricing|priced|charge|sell|selling|list|listing|ask|asking|it|its|is|are|worth|suggest|suggestion"
    r"|recommendation|check|plant|plants|one|ones|these|those|this|that|now|today|on|to|of|please)\b",
    re.IGNORECASE,
)
_DOLLARS = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})?(?:\.\d{2})?)")
MIN_PRICE, MAX_PRICE = 1.0, 2000.0


def is_pricing_question(text: str) -> bool:
    return bool(_PRICING.search(text or ""))


def plant_name(text: str, known_cultivars) -> str:
    """The cultivar the question names, else the question minus filler."""
    lowered = (text or "").lower()
    named = sorted((c for c in known_cultivars if c and c.lower() in lowered), key=len, reverse=True)
    if named:
        start = lowered.index(named[0].lower())
        return text[start:start + len(named[0])]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", _FILLER.sub(" ", text or ""))
    return " ".join(words[:5])


def _number(value):
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def own_sales(report_result: dict, name: str) -> dict | None:
    """Sold count, average sale price and unit cost (when known) for one
    cultivar, summed across the imported reports."""
    sold = revenue = profit = 0.0
    found = False
    for report in (report_result or {}).get("reports", []):
        for cultivar, row in (report.get("cultivar_summary") or {}).items():
            if cultivar.lower() != name.lower():
                continue
            found = True
            sold += _number(row.get("sold")) or 0
            revenue += _number(row.get("revenue")) or 0
            profit += _number(row.get("realized_profit_on_known_costs")) or 0
    if not found:
        return None
    result = {"sold": int(sold)}
    if sold:
        result["average_price"] = round(revenue / sold, 2)
        if profit:
            result["unit_cost"] = round((revenue - profit) / sold, 2)
    return result


def market_prices(search_result: dict) -> list[float]:
    prices = []
    for item in (search_result or {}).get("results") or []:
        for text in (item.get("title", ""), item.get("snippet", "")):
            for match in _DOLLARS.findall(text or ""):
                value = _number(match)
                if value is not None and MIN_PRICE <= value <= MAX_PRICE:
                    prices.append(value)
    return prices


def suggest(own: dict | None, prices: list[float]) -> dict:
    """The suggested price and why. Market median when there are prices,
    kept at least 1.5x his unit cost when that is known; otherwise his own
    average sale price."""
    reasons = []
    price = None
    if prices:
        median = statistics.median(prices)
        price = median
        reasons.append(f"Online now: ${min(prices):.0f}-${max(prices):.0f}, middle ${median:.0f} "
                       f"({len(prices)} prices found).")
    if own and own.get("average_price"):
        reasons.append(f"Your {own['sold']} sold went for ${own['average_price']:.2f} on average.")
        if price is None:
            price = own["average_price"]
    if own and own.get("unit_cost"):
        floor = own["unit_cost"] * 1.5
        reasons.append(f"Your cost is about ${own['unit_cost']:.2f} each.")
        if price is not None and price < floor:
            price = floor
            reasons.append("Raised to keep at least a 1.5x markup on your cost.")
    if own is not None and not own.get("sold"):
        reasons.append("You haven't sold this one yet.")
    return {"price": None if price is None else round(price), "reasons": reasons}


def format_suggestion(name: str, suggestion: dict, sources: str) -> str:
    if suggestion["price"] is None:
        lines = [f"I couldn't find enough to price {name}: none of your imported sales match it, "
                 "and the web results showed no prices."]
    else:
        lines = [f"Suggested price for {name}: ${suggestion['price']}."]
    lines += suggestion["reasons"]
    if sources:
        lines.append(sources)
    return "\n".join(lines)
