"""KARMO Model Router -- host health signal (Phase A).

Observability only: this module produces a structured health snapshot for
a host's local Ollama. Nothing in KARMO currently reads or acts on its
output -- it is the prerequisite for later routing/capability-enforcement/
fallback decisions (Model Router Phases B onward, see
docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.1), not a
behavior change by itself.

Scope of this increment: karmo-ai01 only. Worker01/Worker02 bind Ollama to
127.0.0.1:11434 with no network listener (verified against
worker-runtime/app/capabilities.py's _DEFAULT_OLLAMA_GENERATE_URL) -- there
is no network path for this module, or anything else, to poll them
directly, and none should be added (KARMO's standing "no new listener"
principle, restated in the plan's Section 4 security requirements as an
explicit worker-address allowlist). Worker health-signal transport remains
an open design decision -- the leading candidate is extending the existing
worker heartbeat payload (worker-runtime/app/worker_registry.py's
WorkerHealth) rather than adding a new capability or a new network path --
deliberately left unimplemented pending sign-off, since it touches a
narrow, previously hardened wire protocol (see that module's own comment
on the WorkerStatus/WorkerHealth confusion it was written to prevent).

/api/ps alone is not a health check -- it only reports which models are
loaded, not whether the host is actually responsive (Section 3.1's core
finding, from GPT's review of the first plan draft). Callers that need a
real health judgment must combine poll_loaded_models with run_timed_probe.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_LOCAL_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_MAX_SAMPLES = 20  # bounded rolling window -- I-05, never unbounded growth


class HostHealthError(RuntimeError):
    pass


def _validate_loopback(base_url: str) -> str:
    """Same loopback-only discipline as OllamaChatClient -- this module
    must never be pointed at a network host, by design. Worker01/Worker02
    have no reachable Ollama endpoint at all (see module docstring); this
    check exists so a future caller cannot silently repurpose this module
    into the network poller the topology doesn't support."""
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_HOSTS:
        raise HostHealthError("host health probing is loopback-only")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise HostHealthError("host health base URL must contain only loopback host and optional port")
    return base_url.rstrip("/")


def _percentile(samples, fraction):
    if not samples:
        return None
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


@dataclass(frozen=True)
class HostHealthSnapshot:
    host_id: str
    checked_at: datetime
    reachable: bool
    loaded_models: tuple = ()
    probe_latency_seconds: float | None = None
    consecutive_failures: int = 0
    recent_latencies_seconds: tuple = ()
    error: str | None = None

    @property
    def p50_latency_seconds(self):
        return _percentile(self.recent_latencies_seconds, 0.50)

    @property
    def p95_latency_seconds(self):
        return _percentile(self.recent_latencies_seconds, 0.95)

    def age_seconds(self, *, now=None) -> float:
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - self.checked_at).total_seconds())

    def is_stale(self, *, max_age_seconds: float, now=None) -> bool:
        """Section 3.9's fail-closed rule ("health data stale -> exclude
        the host") needs this primitive; no caller consumes it yet in
        this increment -- there is no router to call it from."""
        return self.age_seconds(now=now) > max_age_seconds


def poll_loaded_models(base_url: str, *, timeout: float = 5.0) -> list:
    """Calls Ollama's official /api/ps endpoint -- documented by Ollama as
    built "to assist with more intelligent load balancing." Zero new
    infrastructure. NOT a complete health check by itself (see module
    docstring) -- combine with run_timed_probe."""
    url = _validate_loopback(base_url) + "/api/ps"
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise HostHealthError(f"/api/ps unreachable or invalid: {exc}") from exc
    models = body.get("models")
    if not isinstance(models, list):
        raise HostHealthError("/api/ps returned an unexpected shape")
    return [m.get("name") for m in models if isinstance(m, dict) and m.get("name")]


def run_timed_probe(base_url: str, *, model: str, timeout: float = 10.0) -> float:
    """A small, real generate call, timed -- the responsiveness signal
    /api/ps alone cannot provide. Kept minimal (a one-token reply) so the
    probe itself does not become a meaningful load source. This function
    performs exactly one probe; callers control how often it runs."""
    if not model or any(ch in model for ch in "\r\n\x00"):
        raise HostHealthError("invalid model identifier")
    url = _validate_loopback(base_url) + "/api/generate"
    body = json.dumps({
        "model": model,
        "prompt": "ping",
        "stream": False,
        "think": False,
        "options": {"num_predict": 1},
    }).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HostHealthError(f"timed probe failed: {exc}") from exc
    return time.monotonic() - started


class HostHealthTracker:
    """In-memory rolling health state per host. Not durably persisted in
    this increment (I-03: this is a live operational signal, not
    business/audit state -- a durable audit trail for router DECISIONS,
    once a router exists to make them, is Phase E's job, not this
    tracker's). Bounded rolling window per host (I-05: never unbounded
    growth)."""

    def __init__(self, *, max_samples: int = _MAX_SAMPLES, clock=None):
        self._max_samples = max_samples
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._latencies: dict = {}
        self._consecutive_failures: dict = {}
        self._last_snapshot: dict = {}

    def record_success(self, host_id: str, *, loaded_models, latency_seconds: float | None = None):
        samples = self._latencies.setdefault(host_id, deque(maxlen=self._max_samples))
        if latency_seconds is not None:
            samples.append(latency_seconds)
        self._consecutive_failures[host_id] = 0
        snapshot = HostHealthSnapshot(
            host_id=host_id,
            checked_at=self._clock(),
            reachable=True,
            loaded_models=tuple(loaded_models),
            probe_latency_seconds=latency_seconds,
            consecutive_failures=0,
            recent_latencies_seconds=tuple(samples),
        )
        self._last_snapshot[host_id] = snapshot
        return snapshot

    def record_failure(self, host_id: str, *, error: str):
        self._consecutive_failures[host_id] = self._consecutive_failures.get(host_id, 0) + 1
        samples = self._latencies.get(host_id, ())
        snapshot = HostHealthSnapshot(
            host_id=host_id,
            checked_at=self._clock(),
            reachable=False,
            loaded_models=(),
            probe_latency_seconds=None,
            consecutive_failures=self._consecutive_failures[host_id],
            recent_latencies_seconds=tuple(samples),
            error=error,
        )
        self._last_snapshot[host_id] = snapshot
        return snapshot

    def snapshot(self, host_id: str):
        return self._last_snapshot.get(host_id)


def check_host(
    tracker: HostHealthTracker,
    *,
    host_id: str,
    base_url: str,
    probe_model: str | None = None,
    timeout: float = 5.0,
) -> HostHealthSnapshot:
    """One full health check for one host: /api/ps, plus a timed probe
    when a probe_model is given. No scheduling/cadence logic lives here
    by design -- a future poller (not built in this increment) decides
    how often to call this; this function performs exactly one check."""
    try:
        loaded_models = poll_loaded_models(base_url, timeout=timeout)
    except HostHealthError as exc:
        return tracker.record_failure(host_id, error=str(exc))

    if probe_model is None:
        return tracker.record_success(host_id, loaded_models=loaded_models)

    try:
        latency = run_timed_probe(base_url, model=probe_model, timeout=timeout)
    except HostHealthError as exc:
        return tracker.record_failure(host_id, error=str(exc))
    return tracker.record_success(host_id, loaded_models=loaded_models, latency_seconds=latency)
