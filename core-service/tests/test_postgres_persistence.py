"""Real-PostgreSQL integration tests for core_service.persistence /
recovery_persistence.

Every other durable-control-plane test exercises hand-written in-memory
Python doubles that mimic the intended contract. None of them execute the
actual SQL in persistence.py/recovery_persistence.py. That SQL -- column
order, ``::uuid``/``::jsonb`` casts, ``ON CONFLICT``/``FOR UPDATE``/
``RETURNING`` clauses, and the CAS ``WHERE state_version=%s`` guard -- is
what actually runs against production PostgreSQL, so it must be proven
against a real PostgreSQL instance, not re-derived from a mock.

Requires a reachable PostgreSQL instance (env-configurable; see
``_conninfo`` below) and the ``psycopg`` driver. Skips cleanly if neither is
available, so this file never silently fails other suites in an environment
without PostgreSQL.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg is required for real-PostgreSQL persistence tests")

from core_service.control import (  # noqa: E402
    ApprovalEngine,
    ApprovalState,
    CapabilityClass,
    CoreControlError,
)
from core_service.persistence import (  # noqa: E402
    PersistenceError,
    PostgresApprovalStore,
    PostgresCapabilityStore,
    PostgresExecutionCoordinator,
    PostgresInvocationLedger,
    PostgresTaskStore,
)
from core_service.recovery_persistence import PostgresRecoveryStore  # noqa: E402
from core_service.registry import CapabilityRegistry  # noqa: E402
from core_service.task_state import TaskState  # noqa: E402

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "core_service" / "migrations" / "001_core_v2_substrate.sql"
)


def _conninfo():
    return (
        f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
        f"user={PG_USER} password={PG_PASSWORD}"
    )


def _connection_factory():
    return psycopg.connect(_conninfo())


def _reachable():
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason=(
        "no reachable PostgreSQL at "
        f"{PG_HOST}:{PG_PORT}/{PG_DB} -- set KARMO_CORE_TEST_PG_* to point at one"
    ),
)


@pytest.fixture(scope="module", autouse=True)
def _apply_migration():
    sql = MIGRATION_PATH.read_text()
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)


@pytest.fixture(autouse=True)
def _clean_tables():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE public.karmo_task_events, public.karmo_tasks, "
            "public.tool_invocation_ledger, public.core_approval_records, "
            "public.tool_registry"
        )
    yield


def _approval_record(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        approval_id=uuid.uuid4(),
        requester="kamara",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest="a" * 64,
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
        created_at=now,
        expires_at=now + timedelta(seconds=3600),
    )
    defaults.update(overrides)
    from core_service.control import ApprovalRecord
    return ApprovalRecord(**defaults)


def test_capability_store_put_get_list_roundtrip_through_real_sql():
    store = PostgresCapabilityStore(_connection_factory)
    manifest = {
        "tool_id": "repo.read",
        "domain": "karmolab",
        "version": "1.0.0",
        "description": "test capability",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "capability_class": "READ",
        "read_scope": ["repo"],
        "write_scope": [],
        "external_side_effects": False,
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": [],
        "secret_requirements": [],
        "invocation_identity": "worker",
        "timeout_seconds": 30,
        "retry_policy": {"max_attempts": 1},
        "idempotent": True,
        "idempotency_mechanism": "arguments_digest",
        "rollback_or_compensation": "not required",
        "health_check": "local",
        "deprecation_policy": "versioned",
        "dependencies": [],
        "observability": ["correlation_id"],
        "failure_isolation": "per invocation",
    }
    record = CapabilityRegistry.validate_manifest(manifest)
    from core_service.control import compute_approval_requirement
    from core_service.registry import RegisteredCapability
    registered = RegisteredCapability(record, compute_approval_requirement(record["capability_class"]))
    store.put(registered)

    fetched = store.get("repo.read", "1.0.0")
    assert fetched.tool_id == "repo.read"
    assert fetched.capability_class == CapabilityClass.READ
    assert fetched.deprecated is False

    listed = store.list("repo.read")
    assert len(listed) == 1
    assert listed[0].tool_id == "repo.read"


def test_approval_store_save_get_roundtrip_and_update_through_real_sql():
    store = PostgresApprovalStore(_connection_factory)
    record = _approval_record()
    version = store.save(record, expected_version=None)
    assert version == 1

    fetched = store.get(str(record.approval_id))
    assert fetched.state == ApprovalState.REQUESTED
    assert fetched.requester == "kamara"
    assert fetched.arguments_digest == record.arguments_digest
    assert fetched.version == 1

    record.transition(ApprovalState.APPROVED, "kamara", "approved", datetime.now(timezone.utc))
    record.authorized_executor = "worker-1"
    version = store.save(record, expected_version=version)
    assert version == 2

    updated = store.get(str(record.approval_id))
    assert updated.state == ApprovalState.APPROVED
    assert updated.authorized_executor == "worker-1"
    assert updated.version == 2
    assert len(updated.audit_trail) == 1
    assert updated.audit_trail[0]["to_state"] == "APPROVED"

    # A second save reusing the pre-update (now-stale) version must fail
    # closed rather than silently overwrite the newer row.
    with pytest.raises(CoreControlError):
        store.save(record, expected_version=1)


def test_concurrent_postgres_writers_race_and_exactly_one_wins():
    """Two real threads, each with its own PostgreSQL connection, race to
    write conflicting terminal decisions for the same approval from the same
    starting version. Exactly one must win; the other must fail closed with
    no corruption -- proving the compare-and-swap holds under genuine
    concurrency, not just sequential simulation."""
    approval_store = PostgresApprovalStore(_connection_factory)
    record = _approval_record()
    base_version = approval_store.save(record, expected_version=None)

    barrier = threading.Barrier(2)
    results = {}

    def racer(name, target_state, actor):
        local = approval_store.get(str(record.approval_id))
        local.transition(target_state, actor, f"{name} attempt", datetime.now(timezone.utc))
        barrier.wait(timeout=5)
        try:
            approval_store.save(local, expected_version=base_version)
            results[name] = "won"
        except CoreControlError:
            results[name] = "lost"

    t1 = threading.Thread(target=racer, args=("approve", ApprovalState.APPROVED, "kamara"))
    t2 = threading.Thread(target=racer, args=("deny", ApprovalState.DENIED, "someone-else"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert sorted(results.values()) == ["lost", "won"]
    final = approval_store.get(str(record.approval_id))
    assert final.state in (ApprovalState.APPROVED, ApprovalState.DENIED)
    assert final.version == base_version + 1
    winner = "approve" if final.state == ApprovalState.APPROVED else "deny"
    assert results[winner] == "won"


def test_invocation_ledger_begin_complete_and_duplicate_key_through_real_sql():
    ledger = PostgresInvocationLedger(_connection_factory)
    invocation_id = ledger.begin(
        idempotency_key="task-1:karmolab.host_health:1",
        task_id=None,
        tool_id="karmolab.host_health",
        tool_version="1",
        requester="kamara",
        model_identity="qwen3:8b",
        executor_identity="worker-1",
        arguments_digest="b" * 64,
        authority_decision="NONE",
    )
    fetched = ledger.get_by_idempotency_key("task-1:karmolab.host_health:1")
    assert fetched.invocation_id == invocation_id
    assert fetched.status == "STARTED"
    assert fetched.completed_at is None

    with pytest.raises(PersistenceError):
        ledger.begin(
            idempotency_key="task-1:karmolab.host_health:1",
            task_id=None,
            tool_id="karmolab.host_health",
            tool_version="1",
            requester="kamara",
            model_identity="qwen3:8b",
            executor_identity="worker-1",
            arguments_digest="b" * 64,
            authority_decision="NONE",
        )

    unfinished = ledger.list_unfinished()
    assert [item.invocation_id for item in unfinished] == [invocation_id]

    ledger.complete(invocation_id, status="EXECUTED", result_digest="c" * 64)
    fetched_after = ledger.get_by_idempotency_key("task-1:karmolab.host_health:1")
    assert fetched_after.status == "EXECUTED"
    assert fetched_after.completed_at is not None
    assert ledger.list_unfinished() == []

    with pytest.raises(PersistenceError):
        ledger.complete(invocation_id, status="EXECUTED")


def test_task_store_save_get_stale_version_and_events_through_real_sql():
    store = PostgresTaskStore(_connection_factory)
    from core_service.task_state import TaskRecord

    record = TaskRecord(
        task_id=str(uuid.uuid4()),
        objective="inspect host",
        requester="kamara",
        risk="LOW",
        allowed_capabilities=["karmolab.host_health"],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    version = store.save(record)
    assert version == 1

    fetched = store.get(record.task_id)
    assert fetched.objective == "inspect host"
    assert fetched.state == TaskState.CREATED
    assert fetched.allowed_capabilities == ["karmolab.host_health"]

    fetched.transition(TaskState.PLANNED, actor="karmo")
    new_version = store.save(fetched, expected_version=1)
    assert new_version == 2

    with pytest.raises(PersistenceError):
        store.save(fetched, expected_version=1)

    by_state = store.list_by_states([TaskState.PLANNED])
    assert [task.task_id for task in by_state] == [record.task_id]

    event_id = store.append_event(
        event_key=f"test-event:{record.task_id}",
        task_id=record.task_id,
        event_type="TEST_EVENT",
        actor="tester",
        payload={"note": "hello"},
    )
    assert event_id

    with pytest.raises(PersistenceError):
        store.append_event(
            event_key=f"test-event:{record.task_id}",
            task_id=record.task_id,
            event_type="TEST_EVENT",
            actor="tester",
            payload={"note": "duplicate"},
        )

    events = store.list_events(record.task_id)
    assert len(events) == 1
    assert events[0].event_type == "TEST_EVENT"
    assert events[0].payload == {"note": "hello"}


def test_execution_coordinator_claim_and_finish_through_real_sql():
    approval_store = PostgresApprovalStore(_connection_factory)
    engine = ApprovalEngine(store=approval_store)
    pending = engine.request(
        requester="kamara",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments={"host": "karmo-ai01"},
        authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(pending.approval_id, approver="kamara", authorized_executor="worker-1")

    coordinator = PostgresExecutionCoordinator(_connection_factory)
    claim = coordinator.claim(
        approval_id=pending.approval_id,
        idempotency_key="task-2:karmolab.host_health:1",
        task_id=None,
        tool_id="karmolab.host_health",
        tool_version="1",
        requester="kamara",
        model_identity=None,
        executor_identity="worker-1",
        arguments={"host": "karmo-ai01"},
        authority_decision="EXPLICIT_PER_SESSION_OR_TASK",
    )
    claimed_state = approval_store.get(pending.approval_id)
    assert claimed_state.state == ApprovalState.CLAIMED
    assert claimed_state.execution_binding == claim.invocation_id

    with pytest.raises(CoreControlError):
        coordinator.claim(
            approval_id=pending.approval_id,
            idempotency_key="task-2:karmolab.host_health:1-retry",
            task_id=None,
            tool_id="karmolab.host_health",
            tool_version="1",
            requester="kamara",
            model_identity=None,
            executor_identity="worker-1",
            arguments={"host": "karmo-ai01"},
            authority_decision="EXPLICIT_PER_SESSION_OR_TASK",
        )

    coordinator.finish(claim, status="EXECUTED", result_digest="d" * 64)
    finished_state = approval_store.get(pending.approval_id)
    assert finished_state.state == ApprovalState.EXECUTED

    with pytest.raises(PersistenceError):
        coordinator.finish(claim, status="EXECUTED", result_digest="d" * 64)


def test_execution_coordinator_rejects_duplicate_idempotency_key_without_claiming_authority():
    approval_store = PostgresApprovalStore(_connection_factory)
    engine = ApprovalEngine(store=approval_store)

    first = engine.request(
        requester="kamara", tool_id="karmolab.host_health", tool_version="1",
        arguments={"host": "a"}, authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(first.approval_id, approver="kamara", authorized_executor="worker-1")
    second = engine.request(
        requester="kamara", tool_id="karmolab.host_health", tool_version="1",
        arguments={"host": "b"}, authority_class=CapabilityClass.REVERSIBLE_WRITE.value,
    )
    engine.approve(second.approval_id, approver="kamara", authorized_executor="worker-1")

    coordinator = PostgresExecutionCoordinator(_connection_factory)
    coordinator.claim(
        approval_id=first.approval_id, idempotency_key="shared-key", task_id=None,
        tool_id="karmolab.host_health", tool_version="1", requester="kamara",
        model_identity=None, executor_identity="worker-1", arguments={"host": "a"},
        authority_decision="EXPLICIT_PER_SESSION_OR_TASK",
    )

    with pytest.raises(PersistenceError):
        coordinator.claim(
            approval_id=second.approval_id, idempotency_key="shared-key", task_id=None,
            tool_id="karmolab.host_health", tool_version="1", requester="kamara",
            model_identity=None, executor_identity="worker-1", arguments={"host": "b"},
            authority_decision="EXPLICIT_PER_SESSION_OR_TASK",
        )

    # The second approval must remain APPROVED, not CLAIMED: the duplicate
    # idempotency key must roll back the claim attempt rather than consume
    # the second approval's authority.
    untouched = approval_store.get(second.approval_id)
    assert untouched.state == ApprovalState.APPROVED
    assert untouched.execution_binding is None


def test_recovery_store_save_with_event_is_atomic_through_real_sql():
    task_store = PostgresTaskStore(_connection_factory)
    recovery_store = PostgresRecoveryStore(_connection_factory)
    from core_service.task_state import TaskRecord

    record = TaskRecord(
        task_id=str(uuid.uuid4()),
        objective="inspect host",
        requester="kamara",
        risk="LOW",
        allowed_capabilities=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    version = task_store.save(record)
    record.transition(TaskState.PLANNED, actor="karmo")
    version = task_store.save(record, expected_version=version)
    record.transition(TaskState.READY, actor="karmo")
    version = task_store.save(record, expected_version=version)
    record.transition(TaskState.RUNNING, actor="worker-1")
    version = task_store.save(record, expected_version=version)

    record.transition(TaskState.RECOVERY_REQUIRED, actor="karmo-recovery")
    next_version = recovery_store.save_with_event(
        record,
        expected_version=version,
        event_key=f"restart-recovery:{record.task_id}:{version}",
        event_type="RECOVERY_REQUIRED",
        actor="karmo-recovery",
        payload={"reason": "process_restart"},
    )
    assert next_version == version + 1

    fetched = task_store.get(record.task_id)
    assert fetched.state == TaskState.RECOVERY_REQUIRED
    events = task_store.list_events(record.task_id)
    assert len(events) == 1
    assert events[0].event_type == "RECOVERY_REQUIRED"

    # Stale expected_version: the state update AND the event insert must both
    # fail -- neither the version bump nor a duplicate/second event may land.
    stale_record = task_store.get(record.task_id)
    stale_record.transition(TaskState.FAILED, actor="stale-writer")
    with pytest.raises(PersistenceError):
        recovery_store.save_with_event(
            stale_record,
            expected_version=version,  # already superseded
            event_key=f"stale-attempt:{record.task_id}",
            event_type="RECOVERY_REQUIRED",
            actor="stale-writer",
            payload={},
        )
    assert len(task_store.list_events(record.task_id)) == 1
    assert task_store.get(record.task_id).state == TaskState.RECOVERY_REQUIRED

    # Duplicate event_key at the correct version: the version bump must also
    # roll back when the event insert conflicts -- state_version must not
    # move without its paired event landing.
    with pytest.raises(PersistenceError):
        recovery_store.save_with_event(
            fetched,
            expected_version=next_version,
            event_key=f"restart-recovery:{record.task_id}:{version}",  # reused key
            event_type="RECOVERY_REQUIRED",
            actor="karmo-recovery",
            payload={"reason": "duplicate"},
        )
    assert task_store.get(record.task_id).state_version == next_version
