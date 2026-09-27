"""Loopback-only Ollama adapter for KARMO operator chat.

The model is compute, not authority. This client accepts no arbitrary network
endpoint: only loopback Ollama is permitted.
"""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class OllamaClientError(RuntimeError):
    pass


class _RefuseRedirect(HTTPRedirectHandler):
    """Loopback-only means loopback for the entire request, not just the
    configured URL. urllib's default opener follows 3xx redirects to any
    host with no restriction -- if something else is listening on (or has
    hijacked) the configured loopback port, a redirect could otherwise send
    the actual request to an arbitrary destination. This handler refuses
    every redirect outright instead of trying to selectively allow
    loopback-only ones, so there is no redirect chain to get wrong."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(
            newurl, code, "redirect refused: loopback-only Ollama endpoint must not redirect", headers, fp,
        )


class OllamaChatClient:
    # 120s, not the original 45s: verified live on karmo-ai01's real hardware
    # that a single tool-calling round trip against the primary model
    # (qwen3:8b) can take 20s+ even warm, and a full tool-calling turn needs
    # at least two round trips (the tool-call decision, then synthesizing the
    # final answer from a potentially large tool result) -- 45s was silently
    # timing out on every real question that used a tool, falling all the way
    # through to the weakest fallback model with no visible trace of why.
    # 96, not a benchmarked value -- this was the pre-existing hardcoded
    # response-length cap. Flagged 2026-09-20 as a real remaining latency
    # lever on karmo-ai01's CPU-only hardware (~3.5-4 tokens/sec generation
    # measured live), separate from the tool-schema-inflation cost already
    # fixed by selective tool-offering. Made a constructor default instead
    # of a hardcoded literal so a future tuning pass doesn't require
    # touching this file again. Raised 96 -> 300 (2026-09-27, Kamara's
    # approval): 96 cut real BloomBoss answers off mid-list. It is a cap,
    # not a target -- the model stops when its answer is done.
    DEFAULT_NUM_PREDICT = 300

    def __init__(self, base_url: str = "http://127.0.0.1:11434", *, timeout: float = 120.0,
                 num_predict: int = DEFAULT_NUM_PREDICT):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise OllamaClientError("Ollama endpoint must be loopback HTTP")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise OllamaClientError("Ollama base URL must contain only loopback host and optional port")
        if not isinstance(num_predict, int) or isinstance(num_predict, bool) or num_predict <= 0:
            raise OllamaClientError("num_predict must be a positive integer")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.num_predict = num_predict
        self._opener = build_opener(_RefuseRedirect)

    def _request_message(self, *, model: str, messages: list[dict], temperature: float,
                         tools: list[dict] | None, timeout: float | None = None,
                         on_token=None) -> dict:
        if not model or any(ch in model for ch in "\r\n\x00"):
            raise OllamaClientError("invalid model identifier")
        body = {
            "model": model,
            "messages": messages,
            "stream": on_token is not None,
            "think": False,
            "options": {"temperature": temperature, "num_predict": self.num_predict},
        }
        if tools:
            body["tools"] = tools
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + "/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Model Router Section 3.5 -- a single total per-turn deadline,
        # not stacked fixed per-candidate timeouts (the direct cause of a
        # real 379.5-second turn: two sequential fixed 120s timeouts,
        # uncapped in total). An explicit per-call override lets a caller
        # (operator.py's _chat()) pass its own remaining turn budget
        # instead of always using this client's fixed construction-time
        # default; every existing caller that never passes one keeps
        # today's exact behavior unchanged.
        effective_timeout = timeout if timeout is not None else self.timeout
        if on_token is not None:
            return self._stream_message(request, effective_timeout, on_token)
        try:
            with self._opener.open(request, timeout=effective_timeout) as response:
                raw = response.read(1024 * 1024 + 1)
        except Exception as exc:
            raise OllamaClientError(f"local model request failed: {type(exc).__name__}") from exc
        if len(raw) > 1024 * 1024:
            raise OllamaClientError("local model response exceeded 1 MiB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
            message = decoded["message"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise OllamaClientError("invalid Ollama response") from exc
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaClientError("invalid Ollama message content")
        return message

    def _stream_message(self, request: Request, timeout: float, on_token) -> dict:
        """Streamed variant of the read above (2026-09-27): each content piece
        goes to on_token as it arrives, so the web UI can show words while the
        CPU model is still writing (~3.3 tokens/second on karmo-ai01). Same
        1 MiB bound, and timeout is enforced as a total for the whole stream,
        not per read, so it still honors the turn's single deadline."""
        deadline = time.monotonic() + timeout
        content, tool_calls, total = [], [], 0
        try:
            with self._opener.open(request, timeout=timeout) as response:
                for line in response:
                    total += len(line)
                    if total > 1024 * 1024:
                        raise OllamaClientError("local model response exceeded 1 MiB")
                    if time.monotonic() > deadline:
                        raise OllamaClientError("local model request failed: stream deadline exceeded")
                    if not line.strip():
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    message = chunk.get("message") or {}
                    piece = message.get("content")
                    if isinstance(piece, str) and piece:
                        content.append(piece)
                        on_token(piece)
                    if message.get("tool_calls"):
                        tool_calls.extend(message["tool_calls"])
                    if chunk.get("done"):
                        break
        except OllamaClientError:
            raise
        except Exception as exc:
            raise OllamaClientError(f"local model request failed: {type(exc).__name__}") from exc
        return {"content": "".join(content), "tool_calls": tool_calls or None}

    def chat(self, *, model: str, messages: list[dict], temperature: float = 0.2,
             timeout: float | None = None) -> str:
        message = self._request_message(model=model, messages=messages, temperature=temperature, tools=None, timeout=timeout)
        return message["content"].strip()

    def chat_with_tools(self, *, model: str, messages: list[dict], tools: list[dict],
                        temperature: float = 0.2, timeout: float | None = None,
                        on_token=None) -> dict:
        """Like chat(), but returns the full response message (content plus any
        tool_calls the model requested) instead of only the answer text -- the
        caller needs to see a tool-call request to act on it, which a bare
        string return can't represent. tools follows Ollama's native
        function-calling schema; pass an empty list to get a plain completion
        shaped like chat()'s but as the full message dict.

        timeout, when given, overrides this client's fixed construction-time
        default for this one call only (Section 3.5's single total per-turn
        deadline -- see _request_message). on_token, when given, streams the
        answer's text pieces to it as they arrive (see _stream_message)."""
        message = self._request_message(model=model, messages=messages, temperature=temperature, tools=tools,
                                        timeout=timeout, on_token=on_token)
        tool_calls = message.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            raise OllamaClientError("invalid Ollama tool_calls field")
        return {"content": message["content"].strip(), "tool_calls": tool_calls or None}
