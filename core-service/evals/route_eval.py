"""Score the model router (core_service/intent_router.py) on a question set.

    PYTHONPATH=core-service python3 core-service/evals/route_eval.py [--url URL] [--model M] [QUESTIONS.jsonl]

URL is a loopback Ollama, default http://127.0.0.1:11434 (on a dev Mac, an
SSH forward to the iMac). Only the routing call is made: no tool runs, nothing
is sent to KARMO, nothing is saved. Each JSONL line: {"q", "route", "also"?}.
Also prints what the keyword rules pick when core_service.operator imports.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from core_service.intent_router import ROUTER_MODEL, classify
from core_service.ollama_client import OllamaChatClient

DEFAULT_QUESTIONS = os.path.join(os.path.dirname(__file__), "route_questions.jsonl")


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip() and not line.startswith("#")]


def keyword_route(text: str) -> str:
    """The route today's keyword rules (iMac down) would take, for comparison."""
    from core_service import operator as op
    from core_service.bloomboss_capability import is_lookup_question
    from core_service.code_sandbox_capability import is_run_request
    from core_service.handoff import is_heavy_task
    from core_service.pricing import is_pricing_question
    from core_service.web_search_capability import is_search_question, wants_the_web

    if op._is_write_request(text):
        return "change"
    if op._is_status_request(text):
        return "status"
    if is_run_request(text):
        return "run_code"
    if is_pricing_question(text):
        return "price"
    web = wants_the_web(text) and is_search_question(text)
    if not web and is_lookup_question(text):
        return "bloomboss"
    bloomboss = op._is_bloomboss_question(text)
    if not bloomboss and not is_search_question(text) and is_heavy_task(text):
        return "heavy"
    if is_search_question(text) and (wants_the_web(text) or not bloomboss):
        return "web"
    if bloomboss:
        return "bloomboss"
    for route, name in (("tasks", "list_tasks"), ("code_help", "ask_local_coder")):
        if op._TOOL_TRIGGER_WORDS[name].search(text):
            return route
    return "chat"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="?", default=DEFAULT_QUESTIONS)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default=ROUTER_MODEL)
    args = parser.parse_args()

    client = OllamaChatClient(args.url, timeout=60.0)
    items = load(args.questions)
    try:
        keyword_route("warm up")
        compare = True
    except Exception:  # noqa: BLE001 -- comparison is optional
        compare = False

    passed, keyword_passed, times = 0, 0, []
    for item in items:
        allowed = {item["route"], *item.get("also", [])}
        started = time.monotonic()
        got = classify(client, item["q"], model=args.model, timeout=60.0)
        times.append(time.monotonic() - started)
        ok = got in allowed
        passed += ok
        if compare:
            keyword_passed += keyword_route(item["q"]) in allowed
        if not ok:
            print(f"MISS  want {item['route']:<9} got {got or '(none)':<9} {item['q']}")
    total = len(items)
    print(f"\nModel router: {passed}/{total} right, {sum(times) / total:.1f}s per question on average")
    if compare:
        print(f"Keyword rules: {keyword_passed}/{total} right")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
