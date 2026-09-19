from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from core_service.shadow_router import (
    NullWorkerHealthReader,
    ShadowRouterError,
    build_default_worker_health_reader,
    collect_shadow_signals,
    compute_shadow_decision,
    log_shadow_decision,
)

NOW = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
CAPS = {
    "qwen3:8b": frozenset({"chat", "tool_calling"}),
    "ministral-3:8b": frozenset({"chat", "tool_calling"}),
    "granite3.3:2b": frozenset({"chat"}),
}


def _fresh_worker_snapshot(*, loaded_models, age_seconds=1.0):
    return {
        "ollama_snapshot": {"loaded_models": loaded_models},
        "ollama_snapshot_at": NOW - timedelta(seconds=age_seconds),
        "last_seen_at": NOW - timedelta(seconds=age_seconds),
    }


def test_no_eligible_host_when_nothing_reachable_or_reporting():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={"KARMO-WORKER01": None, "KARMO-WORKER02": None},
        now=NOW,
    )
    assert decision.chosen_host is None
    assert decision.chosen_model is None
    assert decision.reason == "no_eligible_host"
    assert len(decision.candidates_considered) == 3


def test_karmo_ai01_chosen_when_it_is_the_only_eligible_host():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={"KARMO-WORKER01": None, "KARMO-WORKER02": None},
        now=NOW,
    )
    assert decision.chosen_host == "karmo-ai01"
    assert decision.chosen_model == "qwen3:8b"
    assert decision.reason == "only_karmo_ai01_eligible"


def test_worker_preferred_over_contended_karmo_ai01_when_both_eligible():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["qwen3:8b"],
        worker_snapshots={
            "KARMO-WORKER01": _fresh_worker_snapshot(loaded_models=["ministral-3:8b"]),
            "KARMO-WORKER02": None,
        },
        now=NOW,
    )
    assert decision.chosen_host == "KARMO-WORKER01"
    assert decision.chosen_model == "ministral-3:8b"
    assert decision.reason == "worker_preferred_over_contended_karmo_ai01"


def test_worker_with_no_snapshot_yet_is_excluded():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={"KARMO-WORKER01": None},
        now=NOW,
    )
    candidate = decision.candidates_considered[1]
    assert candidate["host"] == "KARMO-WORKER01"
    assert candidate["eligible"] is False
    assert candidate["reason"] == "no_snapshot_yet"


def test_stale_worker_snapshot_is_excluded():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={
            "KARMO-WORKER01": _fresh_worker_snapshot(loaded_models=["qwen3:8b"], age_seconds=500),
        },
        max_staleness_seconds=120,
        now=NOW,
    )
    candidate = decision.candidates_considered[1]
    assert candidate["eligible"] is False
    assert candidate["reason"] == "stale_snapshot"
    assert candidate["data_age_seconds"] == 500


def test_worker_with_only_non_tool_capable_model_loaded_is_excluded():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=False,
        karmo_ai01_loaded_models=[],
        worker_snapshots={
            "KARMO-WORKER01": _fresh_worker_snapshot(loaded_models=["granite3.3:2b"]),
        },
        now=NOW,
    )
    candidate = decision.candidates_considered[1]
    assert candidate["eligible"] is False
    assert candidate["reason"] == "no_tool_capable_model_loaded"


def test_decision_never_selects_a_non_tool_capable_model_even_if_loaded_alongside_one():
    decision = compute_shadow_decision(
        capability_registry=CAPS,
        karmo_ai01_reachable=True,
        karmo_ai01_loaded_models=["granite3.3:2b", "qwen3:8b"],
        worker_snapshots={},
        now=NOW,
    )
    assert decision.chosen_model == "qwen3:8b"


def test_collect_shadow_signals_degrades_gracefully_when_karmo_ai01_unreachable():
    class FakeReader:
        def get_worker_ollama_health(self, worker_id):
            return {"ollama_snapshot": None, "ollama_snapshot_at": None, "last_seen_at": None}

    reachable, loaded, snapshots = collect_shadow_signals(
        worker_health_reader=FakeReader(),
        worker_ids=("KARMO-WORKER01",),
        karmo_ai01_base_url="http://127.0.0.1:1",
        timeout=1.0,
    )
    assert reachable is False
    assert loaded == []
    assert snapshots["KARMO-WORKER01"]["ollama_snapshot"] is None


def test_collect_shadow_signals_isolates_a_failing_worker_reader_per_worker():
    class FlakyReader:
        def get_worker_ollama_health(self, worker_id):
            if worker_id == "KARMO-WORKER01":
                raise RuntimeError("db hiccup")
            return {"ollama_snapshot": {"loaded_models": ["qwen3:8b"]}, "ollama_snapshot_at": NOW, "last_seen_at": NOW}

    _reachable, _loaded, snapshots = collect_shadow_signals(
        worker_health_reader=FlakyReader(),
        worker_ids=("KARMO-WORKER01", "KARMO-WORKER02"),
        karmo_ai01_base_url="http://127.0.0.1:1",
        timeout=1.0,
    )
    assert snapshots["KARMO-WORKER01"] is None
    assert snapshots["KARMO-WORKER02"]["ollama_snapshot"]["loaded_models"] == ["qwen3:8b"]


def test_null_worker_health_reader_always_returns_none():
    reader = NullWorkerHealthReader()
    assert reader.get_worker_ollama_health("KARMO-WORKER01") is None
    assert reader.status == "DEGRADED_CONFIG_MISSING"


def test_null_worker_health_reader_reports_busy_fail_closed():
    """Section 3.9 fail-closed: unknown busy status must exclude a
    worker from routing, never wrongly include one."""
    assert NullWorkerHealthReader().is_worker_busy("KARMO-WORKER01") is True


def test_build_default_worker_health_reader_returns_null_reader_when_file_missing(tmp_path):
    reader = build_default_worker_health_reader(dsn_file=str(tmp_path / "does-not-exist.dsn"))
    assert isinstance(reader, NullWorkerHealthReader)


def test_build_default_worker_health_reader_rejects_world_readable_dsn_file(tmp_path):
    dsn_file = tmp_path / "postgres.dsn"
    dsn_file.write_text("postgresql://karmo@127.0.0.1:5433/karmo")
    os.chmod(dsn_file, 0o644)
    try:
        build_default_worker_health_reader(dsn_file=str(dsn_file))
        raise AssertionError("expected ShadowRouterError")
    except ShadowRouterError:
        pass


def test_build_default_worker_health_reader_rejects_empty_dsn_file(tmp_path):
    dsn_file = tmp_path / "postgres.dsn"
    dsn_file.write_text("")
    os.chmod(dsn_file, 0o600)
    try:
        build_default_worker_health_reader(dsn_file=str(dsn_file))
        raise AssertionError("expected ShadowRouterError")
    except ShadowRouterError:
        pass


def test_build_default_worker_health_reader_constructs_a_real_store(tmp_path):
    from core_service.worker_coordination import PostgresWorkerCoordinatorStore

    dsn_file = tmp_path / "postgres.dsn"
    dsn_file.write_text("postgresql://karmo@127.0.0.1:5433/karmo")
    os.chmod(dsn_file, 0o600)
    reader = build_default_worker_health_reader(dsn_file=str(dsn_file))
    assert isinstance(reader, PostgresWorkerCoordinatorStore)


def test_log_shadow_decision_never_raises_even_with_malformed_candidates():
    decision_like = type("D", (), {
        "chosen_host": "karmo-ai01", "chosen_model": "qwen3:8b", "reason": "x",
        "candidates_considered": ({"host": "karmo-ai01"},),  # missing "eligible" key
    })()
    log_shadow_decision(decision_like)  # must not raise
