import pytest

from core_service.persistence import (
    ExecutionClaim,
    PersistenceError,
    PostgresExecutionCoordinator,
    PostgresInvocationLedger,
)


class RejectConnectionFactory:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        raise AssertionError("database access should not occur")


@pytest.mark.parametrize(
    "status",
    [None, "", "STARTED", "UNKNOWN", "executed", "failed"],
)
def test_invocation_ledger_rejects_invalid_terminal_status_before_db_access(status):
    factory = RejectConnectionFactory()
    ledger = PostgresInvocationLedger(factory)

    with pytest.raises(PersistenceError, match="invalid terminal invocation status"):
        ledger.complete("00000000-0000-0000-0000-000000000001", status=status)

    assert factory.calls == 0


@pytest.mark.parametrize("status", ["EXECUTED", "FAILED"])
def test_invocation_ledger_accepts_only_defined_terminal_statuses(status):
    factory = RejectConnectionFactory()
    ledger = PostgresInvocationLedger(factory)

    with pytest.raises(AssertionError, match="database access should not occur"):
        ledger.complete("00000000-0000-0000-0000-000000000001", status=status)

    assert factory.calls == 1


@pytest.mark.parametrize(
    "status",
    [None, "", "STARTED", "UNKNOWN", "executed", "failed"],
)
def test_execution_coordinator_rejects_invalid_terminal_status_before_db_access(status):
    factory = RejectConnectionFactory()
    coordinator = PostgresExecutionCoordinator(factory)
    claim = ExecutionClaim(
        invocation_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        idempotency_key="test-terminal-status",
    )

    with pytest.raises(PersistenceError, match="invalid terminal invocation status"):
        coordinator.finish(claim, status=status)

    assert factory.calls == 0


@pytest.mark.parametrize("status", ["EXECUTED", "FAILED"])
def test_execution_coordinator_accepts_only_defined_terminal_statuses(status):
    factory = RejectConnectionFactory()
    coordinator = PostgresExecutionCoordinator(factory)
    claim = ExecutionClaim(
        invocation_id="00000000-0000-0000-0000-000000000001",
        approval_id="00000000-0000-0000-0000-000000000002",
        idempotency_key="test-terminal-status",
    )

    with pytest.raises(AssertionError, match="database access should not occur"):
        coordinator.finish(claim, status=status)

    assert factory.calls == 1
