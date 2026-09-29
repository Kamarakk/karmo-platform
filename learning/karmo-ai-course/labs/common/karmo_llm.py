"""Tiny Ollama client used by every lab. Standard library only.

Change the model for any lab without editing code:
    export KARMO_MODEL=qwen3:8b
Point at another Ollama server (for example a worker):
    export OLLAMA_URL=http://127.0.0.1:11434
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("KARMO_MODEL", "llama3.2:3b")
EMBED_MODEL = os.environ.get("KARMO_EMBED_MODEL", "nomic-embed-text")

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMError(Exception):
    """A clear, user-facing problem talking to Ollama."""


def _post(path: str, payload: dict, timeout: float = 300) -> dict:
    request = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        if error.code == 404:
            raise LLMError(
                f"Model not found. Run: ollama pull {payload.get('model')}"
            ) from error
        raise LLMError(f"Ollama returned HTTP {error.code}: {detail[:200]}") from error
    except urllib.error.URLError as error:
        raise LLMError(
            f"Could not reach Ollama at {OLLAMA_URL}. Open the Ollama app and try again."
        ) from error


def chat(
    messages: list,
    model: str | None = None,
    tools: list | None = None,
    schema: dict | None = None,
    temperature: float | None = None,
    timeout: float = 300,
) -> dict:
    """Send one chat request. Returns Ollama's full response body.

    body["message"]["content"]     the text answer
    body["message"]["tool_calls"]  tool requests, when tools were offered
    """
    payload = {"model": model or DEFAULT_MODEL, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    if schema:
        payload["format"] = schema
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    body = _post("/api/chat", payload, timeout)
    message = body.setdefault("message", {})
    message["content"] = _THINK.sub("", message.get("content") or "").strip()
    return body


def ask(prompt: str, system: str | None = None, model: str | None = None,
        temperature: float | None = None) -> str:
    """One question in, one text answer out."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, model=model, temperature=temperature)["message"]["content"]


def ask_json(prompt: str, schema: dict, system: str | None = None,
             model: str | None = None) -> dict:
    """Ask for an answer that must match a JSON schema. Returns the parsed object."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    text = chat(messages, model=model, schema=schema, temperature=0)["message"]["content"]
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LLMError(f"Model did not return valid JSON: {text[:200]}") from error


def embed(texts: list, model: str | None = None) -> list:
    """Turn texts into vectors (lists of floats)."""
    body = _post("/api/embed", {"model": model or EMBED_MODEL, "input": texts})
    return body["embeddings"]


def timed_ask(prompt: str, model: str | None = None) -> dict:
    """Ask and measure. Returns text, seconds, tokens and tokens per second."""
    start = time.perf_counter()
    body = chat([{"role": "user", "content": prompt}], model=model)
    seconds = time.perf_counter() - start
    tokens = body.get("eval_count", 0)
    gen_ns = body.get("eval_duration", 0)
    return {
        "model": model or DEFAULT_MODEL,
        "text": body["message"]["content"],
        "seconds": round(seconds, 2),
        "tokens": tokens,
        "tokens_per_second": round(tokens / (gen_ns / 1e9), 1) if gen_ns else 0.0,
        "load_seconds": round(body.get("load_duration", 0) / 1e9, 2),
    }
