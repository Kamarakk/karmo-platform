"""Module 12: two agents with different jobs, coordinated by plain code.

Researcher agent: has tools, gathers facts from your BloomBoss data.
Writer agent:     has NO tools, turns the facts into a restock memo.
The orchestrator (this file) decides the order. That is still a workflow
around two agents, the same idea as KARMO Commander handing jobs to workers.

Course version: code/03-ai-agents/05-multi-agent/main.py
Usage: python3 multi_agent.py "Pink Black Velvet"
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
sys.path.insert(0, str(HERE.parent / "11-native-tools"))
from karmo_llm import LLMError, ask  # noqa: E402
import tools_agent  # noqa: E402

WRITER_SYSTEM = """You write one-paragraph restock memos for the owner of a rare-plant shop.
Use only the facts you are given. If a fact is missing, say it is missing.
End with a clear recommendation: restock, hold, or skip."""


def researcher(cultivar: str) -> str:
    return tools_agent.run(
        f"Gather these facts about {cultivar}: units on hand by status, landed cost per unit, "
        "units sold, revenue, and revenue minus landed cost of sold units. "
        "Report them as a short bullet list of numbers."
    )


def writer(cultivar: str, facts: str) -> str:
    return ask(f"Cultivar: {cultivar}\n\nFacts from the researcher:\n{facts}",
               system=WRITER_SYSTEM)


def main() -> int:
    cultivar = " ".join(sys.argv[1:]) or input("Cultivar: ")
    try:
        print("== Researcher agent ==")
        facts = researcher(cultivar)
        print(facts)
        print("\n== Writer agent ==")
        print(writer(cultivar, facts))
    except (LLMError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
