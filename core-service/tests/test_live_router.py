from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core_service.live_router import compute_live_routing_decision

NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
REGISTRY = {
    "qwen3:8b": frozenset({"tool_calling"}),
    "ministral-3:8b": frozenset({"tool_calling"}),
    "granite3.3:2b": frozenset({"chat"}),  # not tool-capable
}


def _fresh_snapshot(models, age_seconds=5):
    return {
        "ollama_snapshot": {"loaded_models": models},
        "ollama_snapshot_at": NOW - timedelta(seconds=age_seconds),
    }


def test_prefers_an_idle_tool_capable_worker_over_contended_karmo_ai01():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": False},
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER01"
    assert decision.chosen_model == "qwen3:8b"
    assert decision.is_worker is True
    assert decision.reason == "worker_preferred_over_contended_karmo_ai01"


def test_busy_worker_is_excluded_and_falls_back_to_karmo_ai01():
    """The real, measured design requirement: a worker mid-processing
    another job must never be chosen -- queueing behind it was measured
    at 25-40+ seconds under real load."""
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": True},
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"
    assert decision.reason == "only_karmo_ai01_eligible"
    worker_candidate = next(c for c in decision.candidates_considered if c["host"] == "KARMO-WORKER01")
    assert worker_candidate["eligible"] is False
    assert worker_candidate["reason"] == "worker_busy"


def test_missing_busy_status_is_treated_as_busy_fail_closed():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={},  # no data at all for this worker
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"


def test_stale_worker_snapshot_is_excluded():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"], age_seconds=999)},
        worker_busy={"KARMO-WORKER01": False},
        max_staleness_seconds=120,
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"
    worker_candidate = next(c for c in decision.candidates_considered if c["host"] == "KARMO-WORKER01")
    assert worker_candidate["reason"] == "stale_snapshot"


def test_missing_worker_snapshot_is_excluded():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": None},
        worker_busy={"KARMO-WORKER01": False},
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"


def test_open_circuit_breaker_excludes_karmo_ai01_and_worker_is_chosen_instead():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": False},
        breaker_states={("karmo-ai01", "qwen3:8b"): "OPEN"},
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER01"
    ai01_candidate = next(c for c in decision.candidates_considered if c["host"] == "karmo-ai01")
    assert ai01_candidate["eligible"] is False
    assert ai01_candidate["reason"] == "circuit_breaker_open"


def test_open_circuit_breaker_excludes_a_worker_and_karmo_ai01_is_chosen_instead():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": False},
        breaker_states={("KARMO-WORKER01", "qwen3:8b"): "OPEN"},
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"


def test_half_open_breaker_state_remains_eligible():
    """Section 3.5: HALF_OPEN must still allow exactly one trial -- the
    real mutating gate (allow_request()) belongs at the caller's actual
    dispatch site, not here, but the decision function itself must not
    pre-emptively exclude a HALF_OPEN candidate."""
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": False},
        breaker_states={("KARMO-WORKER01", "qwen3:8b"): "HALF_OPEN"},
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER01"


def test_unreachable_karmo_ai01_is_excluded_regardless_of_breaker():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={"KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"])},
        worker_busy={"KARMO-WORKER01": False},
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER01"
    ai01_candidate = next(c for c in decision.candidates_considered if c["host"] == "karmo-ai01")
    assert ai01_candidate["reason"] == "unreachable"


def test_no_eligible_host_returns_none_not_a_guess():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={"KARMO-WORKER01": None, "KARMO-WORKER02": None},
        worker_busy={"KARMO-WORKER01": True, "KARMO-WORKER02": False},
        now=NOW,
    )
    assert decision.chosen_host is None
    assert decision.chosen_model is None
    assert decision.reason == "no_eligible_host"


def test_only_a_non_tool_capable_model_loaded_excludes_the_host():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["granite3.3:2b"],
        worker_snapshots={},
        worker_busy={},
        now=NOW,
    )
    assert decision.chosen_host is None
    assert decision.reason == "no_eligible_host"
    ai01_candidate = decision.candidates_considered[0]
    assert ai01_candidate["reason"] == "no_tool_capable_model_loaded"


def test_two_workers_one_busy_one_idle_prefers_the_idle_one():
    decision = compute_live_routing_decision(
        capability_registry=REGISTRY,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={
            "KARMO-WORKER01": _fresh_snapshot(["qwen3:8b"]),
            "KARMO-WORKER02": _fresh_snapshot(["ministral-3:8b"]),
        },
        worker_busy={"KARMO-WORKER01": True, "KARMO-WORKER02": False},
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER02"
    assert decision.chosen_model == "ministral-3:8b"
