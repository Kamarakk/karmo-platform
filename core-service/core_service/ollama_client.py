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
    def __init__(self, base_url: str = "http://127.0.0.1:11434", *, timeout: float = 45.0):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise OllamaClientError("Ollama endpoint must be loopback HTTP")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise OllamaClientError("Ollama base URL must contain only loopback host and optional port")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = build_opener(_RefuseRedirect)

    def chat(self, *, model: str, messages: list[dict], temperature: float = 0.2) -> str:
        if not model or any(ch in model for ch in "\r\n\x00"):
            raise OllamaClientError("invalid model identifier")
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature, "num_predict": 96},
        }).encode("utf-8")
        request = Request(
            self.base_url + "/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024 + 1)
        except Exception as exc:
            raise OllamaClientError(f"local model request failed: {type(exc).__name__}") from exc
        if len(raw) > 1024 * 1024:
            raise OllamaClientError("local model response exceeded 1 MiB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
            content = decoded["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise OllamaClientError("invalid Ollama response") from exc
        if not isinstance(content, str):
            raise OllamaClientError("invalid Ollama message content")
        return content.strip()
