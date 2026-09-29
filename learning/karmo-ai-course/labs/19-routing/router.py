"""Module 19: route each question to the cheapest model that can handle it.

Rule 1 (code, instant): plant-number lookups skip the model entirely,
        like KARMO's BloomBoss fast path (about 0.04s on AI01).
Rule 2 (code): short factual questions go to the small model.
Rule 3: everything else (judgment, planning) goes to the large model.

Usage: python3 router.py            (runs the built-in question set)
       python3 router.py "your question"
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, ask  # noqa: E402
from plant_data import cultivar_summary, list_cultivars  # noqa: E402

SMALL = os.environ.get("KARMO_SMALL_MODEL", "llama3.2:1b")
LARGE = os.environ.get("KARMO_LARGE_MODEL", "llama3.2:3b")
JUDGMENT = re.compile(r"\b(should|why|plan|compare|recommend|strategy|best way)\b", re.IGNORECASE)
LOOKUP = re.compile(r"\b(how many|landed cost|units|sold|revenue)\b", re.IGNORECASE)

QUESTIONS = [
    "How many Pink Black Velvet units have sold?",
    "What humidity do Alocasia like?",
    "What does variegated mean?",
    "Should I restock Ninja Albo or Pink Black Velvet first, and why?",
    "Plan a weekly auction schedule for 20 plants.",
]


def route(question: str) -> tuple:
    if LOOKUP.search(question):
        for name in list_cultivars():
            if name.lower() in question.lower():
                return "lookup", name
    if JUDGMENT.search(question) or len(question.split()) > 25:
        return "large", LARGE
    return "small", SMALL


def handle(question: str) -> tuple:
    kind, target = route(question)
    if kind == "lookup":
        facts = cultivar_summary(target)
        return kind, f"{facts['cultivar']}: {facts['units']} units, {facts['units_sold']} sold, revenue ${facts['revenue']}"
    return f"{kind} ({target})", ask(question + " Answer in under 60 words.", model=target)


def main() -> int:
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else QUESTIONS
    try:
        for question in questions:
            start = time.perf_counter()
            route_name, answer = handle(question)
            print(f"\n[{time.perf_counter() - start:5.1f}s] {route_name}: {question}\n{answer}")
    except (LLMError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
