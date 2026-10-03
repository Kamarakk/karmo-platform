"""Score KARMO's answers against a question set, through the real web UI.

    python3 core-service/evals/know_karmo_eval.py URL QUESTIONS.jsonl [...]

URL is the web UI base, e.g. https://karmo-ai01.tail2d74d7.ts.net:8787.
Each JSONL line: {"q": "...", "expect_any": ["..."], "forbid": ["..."]}.
A question passes when the answer contains at least one expect_any string
(if any are given) and none of the forbid strings, case-insensitively.

Questions go through the same /chat path Kamara uses, so they are also
saved to KARMO's conversation memory like any other chat turn.
"""

from __future__ import annotations

import json
import ssl
import sys
import time
from urllib import request

TIMEOUT_SECONDS = 330


def load_questions(paths: list[str]) -> list[dict]:
    questions = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                item = json.loads(line)
                if not isinstance(item.get("q"), str) or not item["q"].strip():
                    raise ValueError(f"{path}:{number}: missing question text")
                questions.append(item)
    return questions


def score(answer: str, item: dict) -> tuple[bool, str]:
    lowered = answer.lower()
    expect = [text.lower() for text in item.get("expect_any", [])]
    forbid = [text.lower() for text in item.get("forbid", [])]
    hit = [text for text in forbid if text in lowered]
    if hit:
        return False, f"said {hit[0]!r}"
    if expect and not any(text in lowered for text in expect):
        return False, "missing expected answer"
    return True, ""


def ask(base_url: str, question: str) -> dict:
    body = json.dumps({"text": question}).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + "/chat", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with request.urlopen(req, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__.strip())
        return 2
    base_url, paths = argv[1], argv[2:]
    questions = load_questions(paths)
    passed = 0
    for number, item in enumerate(questions, 1):
        start = time.monotonic()
        try:
            answer = str(ask(base_url, item["q"]).get("message", ""))
        except Exception as exc:  # noqa: BLE001 -- one failed question must not stop the run
            answer, ok, why = "", False, f"request failed: {type(exc).__name__}"
        else:
            ok, why = score(answer, item)
        passed += ok
        seconds = time.monotonic() - start
        print(f"{'PASS' if ok else 'FAIL'} {number:>2} {seconds:5.1f}s  {item['q']}")
        if not ok:
            print(f"        {why}; answer: {answer[:200]!r}")
    print(f"\nScore: {passed}/{len(questions)}")
    return 0 if passed == len(questions) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
