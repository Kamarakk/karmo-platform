"""KARMO Worker Runtime -- local Ollama health snapshot (Model Router Phase A).

Collects a small, bounded snapshot of this worker's own loopback Ollama
(currently loaded models, via /api/ps) to attach to the existing heartbeat
call. This module never talks to any host but its own loopback Ollama, and
a failure here must never be allowed to block the heartbeat itself --
health reporting is an availability/observability signal, not an authority
boundary, and must not gain the power to affect worker scheduling
eligibility (lease renewal) just by being broken. collect_snapshot()
therefore never raises; it returns None on any failure.

See docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.1. This
is the worker-side half of Phase A's health signal -- karmo-ai01's own
loopback probing lives separately in core-service's host_health.py; the
two packages are deployed independently and deliberately do not share a
dependency for this.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

_DEFAULT_OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"
_MAX_MODELS_REPORTED = 32
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _ollama_ps_url():
    """Same env-var-override-at-call-time pattern as capabilities.py's
    _ollama_generate_url() -- resolved fresh each call so a spawn-context
    test child (which re-imports this module) can still be redirected via
    an environment variable, which spawn does inherit. Production never
    sets this and always talks to the worker's own loopback Ollama."""
    return os.environ.get("KARMO_OLLAMA_PS_URL", _DEFAULT_OLLAMA_PS_URL)


def collect_snapshot(*, timeout_seconds: float = 5.0):
    """Returns a small, bounded, JSON-serializable dict describing this
    worker's currently loaded Ollama models, or None on any failure
    (unreachable, malformed, non-loopback, oversized). Never raises --
    callers (the heartbeat call site) must be able to proceed with no
    snapshot exactly as if this function did not exist."""
    url = _ollama_ps_url()
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_HOSTS:
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None
    models = body.get("models") if isinstance(body, dict) else None
    if not isinstance(models, list):
        return None
    names = [
        m.get("name") for m in models
        if isinstance(m, dict) and isinstance(m.get("name"), str) and m.get("name")
    ]
    return {"loaded_models": names[:_MAX_MODELS_REPORTED]}
