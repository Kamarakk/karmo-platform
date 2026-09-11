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
