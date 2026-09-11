import builtins

from worker_service.health import health


def test_worker_health_binds_to_production_core_and_stays_inert():
    state = health()
    assert state["status"] == "healthy"
    assert state["core_bound"] is True
    assert state["core_read_approval_floor"] == "NONE"
    assert state["network_listener"] is False
    assert state["worker_network_transport"] is False
    assert state["capability_execution_enabled"] is False
    assert state["persistent_writes"] is False


def test_worker_fails_closed_when_core_binding_is_unavailable(monkeypatch):
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("core_service"):
            raise ImportError("core unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    state = health()
    assert state["status"] == "unhealthy"
    assert state["core_bound"] is False
    assert state["capability_execution_enabled"] is False
    assert state["worker_network_transport"] is False
