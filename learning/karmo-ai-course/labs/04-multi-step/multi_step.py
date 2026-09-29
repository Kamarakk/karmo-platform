"""Module 4: a multi-step, multi-model workflow.

Step 1 (code):        download a web page
Step 2 (code):        strip the HTML down to text, no model needed
Step 3 (small model): summarize the text
Step 4 (large model): write a listing-style post from the summary

Course version: code/02-ai-workflows/04-multi-step-multi-model/main.py
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from karmo_llm import LLMError, ask  # noqa: E402


class _TextOnly(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def fetch_text(url: str, limit: int = 6000) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 karmo-course"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    parser = _TextOnly()
    parser.feed(html)
    return " ".join(parser.parts)[:limit]


def step(name: str, func, *args, **kwargs):
    start = time.perf_counter()
    result = func(*args, **kwargs)
    print(f"[{time.perf_counter() - start:6.1f}s] {name}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--small", default="llama3.2:1b")
    parser.add_argument("--large", default="llama3.2:3b")
    args = parser.parse_args()
    try:
        text = step("fetch + strip HTML (code)", fetch_text, args.url)
        summary = step(f"summarize ({args.small})", ask,
                       f"Summarize the key facts in 3-5 bullets. Text:\n<text>\n{text}\n</text>",
                       model=args.small)
        post = step(f"write post ({args.large})", ask,
                    "Write a short, friendly social post (under 80 words, no hashtags) "
                    f"based only on these facts:\n{summary}", model=args.large)
    except LLMError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Error fetching page: {error}", file=sys.stderr)
        return 1
    print(f"\n--- SUMMARY ---\n{summary}\n\n--- POST ---\n{post}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
