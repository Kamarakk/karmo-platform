from karmo_core.service import CoreService, HealthState


def test_core_starts_healthy_and_remains_inert():
    service = CoreService()
    service.start()
    health = service.health()

    assert health["state"] == HealthState.HEALTHY
    assert health["failure_reason"] is None
    assert health["network_listener_enabled"] is False
    assert health["persistent_writes_enabled"] is False
    assert health["worker_transport_enabled"] is False


def test_core_failure_is_visible():
    service = CoreService()
    service.fail("CONFIGURATION_ERROR")
    health = service.health()

    assert health["state"] == HealthState.FAILED
    assert health["failure_reason"] == "CONFIGURATION_ERROR"
