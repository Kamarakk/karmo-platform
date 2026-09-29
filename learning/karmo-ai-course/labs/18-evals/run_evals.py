"""Module 18: evals. A fixed set of questions with checkable answers.

Run this after ANY change (new model, new prompt, new code) and compare the
score with the last run. If it drops, the change made KARMO worse.

Ground truth for plant numbers comes from your data, not from the model.
Usage: python3 run_evals.py            (uses KARMO_MODEL or llama3.2:3b)
       KARMO_MODEL=qwen3:8b python3 run_evals.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABS = HERE.parent
for folder in ("common", "11-native-tools", "17-rag"):
    sys.path.insert(0, str(LABS / folder))
from karmo_llm import DEFAULT_MODEL, LLMError  # noqa: E402
from plant_data import cultivar_summary  # noqa: E402
import rag  # noqa: E402
import tools_agent  # noqa: E402

TARGETS = {
    "tools_agent": tools_agent.run,
    "rag": lambda q: rag.answer(q)["answer"],
}


def expected_strings(case: dict) -> list:
    if "must_contain_fields" in case:
        facts = cultivar_summary(case["cultivar"])
        return [str(facts[f]).rstrip("0").rstrip(".") if isinstance(facts[f], float) else str(facts[f])
                for f in case["must_contain_fields"]]
    return []


def check(case: dict, output: str) -> bool:
    text = output.lower()
    required = expected_strings(case)
    if required:  # whole numbers only: "1" must not match inside "10"
        return all(re.search(rf"(?<![\d.]){re.escape(r.lower())}(?![\d])", text) for r in required)
    return any(s.lower() in text for s in case["must_contain_any"])


def main() -> int:
    if not rag.INDEX.exists():
        print("Build the RAG index first: python3 ../17-rag/rag.py index", file=sys.stderr)
        return 1
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    results, passed = [], 0
    for case in cases:
        start = time.perf_counter()
        try:
            output = TARGETS[case["target"]](case["question"])
            ok = check(case, output)
        except (LLMError, FileNotFoundError) as error:
            output, ok = f"ERROR: {error}", False
        seconds = round(time.perf_counter() - start, 1)
        passed += ok
        results.append({"id": case["id"], "pass": ok, "seconds": seconds, "output": output})
        print(f"{'PASS' if ok else 'FAIL'}  {seconds:>5}s  {case['id']}")
    score = f"{passed}/{len(cases)}"
    model = os.environ.get("KARMO_MODEL", DEFAULT_MODEL)
    report = HERE / "reports" / f"{datetime.now():%Y%m%d-%H%M%S}-{model.replace(':', '_')}.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({"model": model, "score": score, "results": results}, indent=2),
                      encoding="utf-8")
    print(f"\nScore {score} with {model}. Report: {report.relative_to(HERE)}")
    return 0 if passed == len(cases) else 2


if __name__ == "__main__":
    raise SystemExit(main())
