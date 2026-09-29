"""Module 0: checks everything the course needs. Run: python3 check_setup.py"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import OLLAMA_URL, LLMError, ask  # noqa: E402
from plant_data import CSV_PATH, list_cultivars  # noqa: E402

NEEDED = ["llama3.2:1b", "llama3.2:3b", "nomic-embed-text"]
ok = True


def report(passed: bool, label: str, fix: str = "") -> None:
    global ok
    ok &= passed
    print(f"{'OK  ' if passed else 'FIX '} {label}" + ("" if passed else f"\n      -> {fix}"))


report(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (need 3.9+)",
       "Install Python 3.12 from https://www.python.org/downloads/")

try:
    with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
        models = {m["name"] for m in json.load(r)["models"]}
    report(True, f"Ollama is running at {OLLAMA_URL}")
    for name in NEEDED:
        present = name in models or f"{name}:latest" in models
        report(present, f"model {name}", f"ollama pull {name}")
except OSError:
    report(False, f"Ollama at {OLLAMA_URL}", "Install from https://ollama.com/download and open the app")
    models = set()

try:
    report(len(list_cultivars()) > 0, f"BloomBoss data at {CSV_PATH}")
except FileNotFoundError:
    report(False, f"BloomBoss data at {CSV_PATH}",
           "cd ~/KARMO-DEV && git pull   (or set BLOOMBOSS_CSV to the file)")

if models:
    try:
        reply = ask("Reply with exactly: ready", model="llama3.2:3b")
        report(bool(reply), f"test answer from llama3.2:3b: {reply[:40]!r}")
    except LLMError as error:
        report(False, "test answer", str(error))

print("\nALL SET. Start Module 1." if ok else "\nFix the lines marked FIX, then run this again.")
raise SystemExit(0 if ok else 1)
