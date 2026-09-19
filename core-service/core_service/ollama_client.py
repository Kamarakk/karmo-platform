"""Loopback-only Ollama adapter for KARMO operator chat.

The model is compute, not authority. This client accepts no arbitrary network
endpoint: only loopback Ollama is permitted.
"""

from __future__ import annotations

import json
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
    def __init__(self, base_url: str = "http://127.0.0.1:11434", *, timeout: float = 120.0):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise OllamaClientError("Ollama endpoint must be loopback HTTP")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise OllamaClientError("Ollama base URL must contain only loopback host and optional port")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = build_opener(_RefuseRedirect)

    def _request_message(self, *, model: str, messages: list[dict], temperature: float,
                         tools: list[dict] | None, timeout: float | None = None) -> dict:
        if not model or any(ch in model for ch in "\r\n\x00"):
            raise OllamaClientError("invalid model identifier")
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": 96},
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

    def chat(self, *, model: str, messages: list[dict], temperature: float = 0.2,
             timeout: float | None = None) -> str:
        message = self._request_message(model=model, messages=messages, temperature=temperature, tools=None, timeout=timeout)
        return message["content"].strip()

    def chat_with_tools(self, *, model: str, messages: list[dict], tools: list[dict],
                        temperature: float = 0.2, timeout: float | None = None) -> dict:
        """Like chat(), but returns the full response message (content plus any
        tool_calls the model requested) instead of only the answer text -- the
        caller needs to see a tool-call request to act on it, which a bare
        string return can't represent. tools follows Ollama's native
        function-calling schema; pass an empty list to get a plain completion
        shaped like chat()'s but as the full message dict.

        timeout, when given, overrides this client's fixed construction-time
        default for this one call only (Section 3.5's single total per-turn
        deadline -- see _request_message)."""
        message = self._request_message(model=model, messages=messages, temperature=temperature, tools=tools, timeout=timeout)
        tool_calls = message.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            raise OllamaClientError("invalid Ollama tool_calls field")
        return {"content": message["content"].strip(), "tool_calls": tool_calls or None}
