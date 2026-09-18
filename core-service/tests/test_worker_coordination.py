from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "worker-runtime" / "app"))

from crypto_boundary import (  # noqa: E402
    CryptoBoundaryError,
    ExecutionTicketAuthority,
    KeyResolver,
    ResultAuthenticator,
    WorkerAuthenticator,
    token_digest,
)
from core_service.worker_coordination import (  # noqa: E402
    OutboundTransportPolicy,
    PostgresWorkerCoordinatorStore,
    WorkerCoordinationError,
    WorkerCoordinator,
)
from core_service.control import (  # noqa: E402
    ApprovalEngine,
    ApprovalState,
    CapabilityClass,
)
from core_service.persistence import PostgresApprovalStore  # noqa: E402
from core_service.worker_gateway_backend import PostgresWorkerGatewayBackend  # noqa: E402
from core_service.worker_dispatch import dispatch_and_wait  # noqa: E402

import os  # noqa: E402

PG_HOST = os.environ.get("KARMO_CORE_TEST_PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("KARMO_CORE_TEST_PG_PORT", "55434")
PG_DB = os.environ.get("KARMO_CORE_TEST_PG_DB", "karmo_core_test")
PG_USER = os.environ.get("KARMO_CORE_TEST_PG_USER", "karmo_core_test")
PG_PASSWORD = os.environ.get("KARMO_CORE_TEST_PG_PASSWORD", "karmo_core_test_synthetic_local_only")


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


pytestmark = pytest.mark.skipif(not _reachable(), reason="no isolated Core PostgreSQL available")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    migrations_dir = REPO_ROOT / "core-service" / "core_service" / "migrations"
    migration_1 = migrations_dir / "001_core_v2_substrate.sql"
    migration_2 = migrations_dir / "002_worker_coordination.sql"
    # 003 adds karmo_worker_job_payloads -- this file's dispatch_and_wait
    # round-trip test now calls attach_job_arguments(), which needs it;
    # 004 (orchestration tasks) remains genuinely unneeded here and stays
    # owned by its own test file. 005 adds
    # karmo_workers.ollama_snapshot/ollama_snapshot_at (Model Router Phase
    # A) -- this file's own tests depend on those columns existing. 007
    # adds karmo_worker_job_results (Model Router Phase D1) -- the
    # dispatch_and_wait round-trip test depends on it to read back the
    # real result content, not just a digest.
    migration_3 = migrations_dir / "003_worker_job_payloads.sql"
    migration_5 = migrations_dir / "005_worker_ollama_health.sql"
    migration_7 = migrations_dir / "007_worker_job_results.sql"
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(migration_1.read_text())
        cur.execute(migration_2.read_text())
        cur.execute(migration_3.read_text())
        cur.execute(migration_5.read_text())
        cur.execute(migration_7.read_text())


@pytest.fixture(autouse=True)
def _clean():
    with psycopg.connect(_conninfo(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE public.karmo_worker_events, public.karmo_execution_tickets, "
            "public.karmo_worker_jobs, public.karmo_workers CASCADE"
        )
    yield


WORKER_KEY = b"w" * 32
COORDINATOR_KEY = b"c" * 32


def _keys(key_id):
    return {"worker-key-v1": WORKER_KEY, "coord-key-v1": COORDINATOR_KEY}.get(key_id)


def _crypto():
    resolver = KeyResolver(_keys)
    return (
        WorkerAuthenticator(resolver),
        ExecutionTicketAuthority(resolver, signing_key_id="coord-key-v1"),
        ResultAuthenticator(resolver),
    )


def _approve(*, tool_id="karmolab.host_health", tool_version="1", arguments=None, authorized_executor="worker-1"):
    """Create a real APPROVED record in core_approval_records, backed by the
    same ApprovalEngine/PostgresApprovalStore the direct-dispatch path uses.
    Worker jobs must be authorized by a real approval -- never a bare
    caller-supplied approval_id string."""
    arguments = arguments if arguments is not None else {"host": "karmo-ai01"}
    engine = ApprovalEngine(store=PostgresApprovalStore(_connection_factory))
    pending = engine.request(
        requester="kamara",
        tool_id=tool_id,
        tool_version=tool_version,
        arguments=arguments,
        authority_class=CapabilityClass.EXTERNAL_ACTION.value,
    )
    engine.approve(pending.approval_id, approver="kamara", authorized_executor=authorized_executor)
    return engine, pending.approval_id, pending.arguments_digest


def _setup_leased_job(store, worker_auth, coordinator, *, arguments=None, tool_id="karmolab.host_health", tool_version="1"):
    store.register_worker(
        worker_id="worker-1",
        key_id="worker-key-v1",
        capabilities=[tool_id],
        metadata={"transport": "outbound-only"},
    )
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(
        credential_token=credential,
        worker_id="worker-1",
        lease_seconds=120,
    )
    _engine, approval_id, digest = _approve(
        tool_id=tool_id, tool_version=tool_version, arguments=arguments, authorized_executor="worker-1",
    )
    task_id = str(uuid.uuid4())
    job_id = store.enqueue_job(
        idempotency_key=f"{task_id}:{tool_id}:{tool_version}",
        task_id=task_id,
        approval_id=approval_id,
        tool_id=tool_id,
        tool_version=tool_version,
        arguments_digest=digest,
    )
    lease = store.lease_job(job_id=job_id, worker_id="worker-1", lease_seconds=60)
    return credential, job_id, lease


def test_full_worker_identity_ticket_result_lifecycle_is_durable_and_single_use():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)
    assert lease.attempt_count == 1

    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease, ttl_seconds=30)
    verified = tickets.verify(
        token,
        approval_id=lease.approval_id,
        arguments_digest=lease.arguments_digest,
        executor_identity=lease.worker_id,
        task_id=lease.task_id,
        tool_id=lease.tool_id,
        tool_version=lease.tool_version,
    )
    assert verified["tool_id"] == "karmolab.host_health"
    assert verified["tool_version"] == "1"

    assert coordinator.authorize_execution(token=token, lease=lease) is True
    with pytest.raises(WorkerCoordinationError, match="already consumed"):
        coordinator.authorize_execution(token=token, lease=lease)

    result = {"host": "karmo-ai01", "status": "healthy"}
    envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    digest = coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=envelope)
    assert digest == results.result_digest(result)
    assert store.get_job_state(job_id)["state"] == "RESULT_SUBMITTED"

    store.finalize_job(job_id=job_id, success=True)
    durable = store.get_job_state(job_id)
    assert durable["state"] == "SUCCEEDED"
    assert durable["result_digest"] == digest
    assert PostgresWorkerCoordinatorStore(_connection_factory).get_job_state(job_id)["state"] == "SUCCEEDED"


def test_result_is_refused_until_ticket_has_been_consumed():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)
    result = {"ok": True}
    envelope = results.sign(
        worker_id=lease.worker_id, key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(WorkerCoordinationError, match="was not consumed"):
        coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=envelope)
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_worker_identity_key_mismatch_and_revocation_fail_closed():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")

    wrong_key_credential = WorkerAuthenticator(
        KeyResolver(lambda key_id: b"x" * 32 if key_id == "other" else _keys(key_id))
    ).issue(worker_id="worker-1", key_id="other", ttl_seconds=60)
    with pytest.raises((WorkerCoordinationError, CryptoBoundaryError)):
        coordinator.authenticate_heartbeat(credential_token=wrong_key_credential, worker_id="worker-1")

    store.revoke_worker("worker-1")
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=60)
    with pytest.raises(WorkerCoordinationError):
        coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")


def test_tampered_ticket_tool_binding_and_result_are_refused():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator, arguments={"host": "other-host"})
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)

    with pytest.raises(CryptoBoundaryError):
        tickets.verify(
            token, approval_id=lease.approval_id, arguments_digest="tampered",
            executor_identity=lease.worker_id, task_id=lease.task_id,
            tool_id=lease.tool_id, tool_version=lease.tool_version,
        )
    with pytest.raises(CryptoBoundaryError):
        tickets.verify(
            token, approval_id=lease.approval_id, arguments_digest=lease.arguments_digest,
            executor_identity=lease.worker_id, task_id=lease.task_id,
            tool_id="karmolab.other", tool_version=lease.tool_version,
        )

    coordinator.authorize_execution(token=token, lease=lease)
    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(CryptoBoundaryError):
        coordinator.accept_result(execution_ticket=token, lease=lease, result={"ok": False}, envelope=envelope)

    wrong_ticket_envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=hashlib.sha256(b"different-ticket").hexdigest(),
    )
    with pytest.raises(CryptoBoundaryError, match="execution-ticket binding mismatch"):
        coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=wrong_ticket_envelope)
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_expired_lease_moves_to_recovery_required_and_never_requeues_automatically():
    class Clock:
        def __init__(self):
            self.now = datetime.now(timezone.utc)
        def __call__(self):
            return self.now

    clock = Clock()
    store = PostgresWorkerCoordinatorStore(_connection_factory, clock=clock)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.heartbeat(worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120)
    _engine, approval_id, digest = _approve()
    task_id = str(uuid.uuid4())
    job_id = store.enqueue_job(
        idempotency_key=f"{task_id}:host_health", task_id=task_id, approval_id=approval_id,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest,
    )
    store.lease_job(job_id=job_id, worker_id="worker-1", lease_seconds=5)
    clock.now += timedelta(seconds=6)

    assert store.recover_expired_leases() == [job_id]
    state = store.get_job_state(job_id)
    assert state["state"] == "RECOVERY_REQUIRED"
    assert "unknown execution outcome" in state["last_error"]
    with pytest.raises(WorkerCoordinationError):
        store.lease_job(job_id=job_id, worker_id="worker-1")


def test_heartbeat_persists_ollama_snapshot_and_its_own_timestamp():
    """Model Router Phase A (see docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md
    Section 3.1). ollama_snapshot_at is tracked separately from
    last_seen_at so a consumer can tell exactly how stale the snapshot
    itself is, independent of whether the worker is alive."""
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")

    before = store.get_worker_ollama_health("worker-1")
    assert before == {"ollama_snapshot": None, "ollama_snapshot_at": None, "last_seen_at": None}

    store.heartbeat(
        worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120,
        ollama_snapshot={"loaded_models": ["qwen3:8b", "granite3.3:2b"]},
    )
    after = store.get_worker_ollama_health("worker-1")
    assert after["ollama_snapshot"] == {"loaded_models": ["qwen3:8b", "granite3.3:2b"]}
    assert after["ollama_snapshot_at"] is not None
    assert after["last_seen_at"] is not None


def test_heartbeat_without_snapshot_leaves_prior_snapshot_in_place():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.heartbeat(
        worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120,
        ollama_snapshot={"loaded_models": ["qwen3:8b"]},
    )
    first = store.get_worker_ollama_health("worker-1")

    # A later heartbeat with no snapshot (older worker binary, or a failed
    # local probe) must not wipe the last-known value.
    store.heartbeat(worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120)
    second = store.get_worker_ollama_health("worker-1")

    assert second["ollama_snapshot"] == {"loaded_models": ["qwen3:8b"]}
    assert second["ollama_snapshot_at"] == first["ollama_snapshot_at"]
    assert second["last_seen_at"] >= first["last_seen_at"]


def test_get_worker_ollama_health_returns_none_for_unknown_worker():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    assert store.get_worker_ollama_health("no-such-worker") is None


def test_lease_job_refuses_missing_or_unapproved_authority():
    """BLOCKER regression: a worker job must never be leasable without a
    real, currently-APPROVED KARMO authority record matching it exactly."""
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.heartbeat(worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=120)

    # No approval_id at all.
    job_no_approval = store.enqueue_job(
        idempotency_key=f"no-approval:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=None,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest="a" * 64,
    )
    with pytest.raises(WorkerCoordinationError, match="no approval_id"):
        store.lease_job(job_id=job_no_approval, worker_id="worker-1")

    # approval_id that does not exist in core_approval_records.
    job_fake_approval = store.enqueue_job(
        idempotency_key=f"fake-approval:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=str(uuid.uuid4()),
        tool_id="karmolab.host_health", tool_version="1", arguments_digest="a" * 64,
    )
    with pytest.raises(WorkerCoordinationError, match="no such approval"):
        store.lease_job(job_id=job_fake_approval, worker_id="worker-1")

    # A real approval that is still REQUESTED (never approved).
    engine = ApprovalEngine(store=PostgresApprovalStore(_connection_factory))
    requested = engine.request(
        requester="kamara", tool_id="karmolab.host_health", tool_version="1",
        arguments={"host": "karmo-ai01"}, authority_class=CapabilityClass.EXTERNAL_ACTION.value,
    )
    job_unapproved = store.enqueue_job(
        idempotency_key=f"unapproved:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=requested.approval_id,
        tool_id="karmolab.host_health", tool_version="1",
        arguments_digest=requested.arguments_digest,
    )
    with pytest.raises(WorkerCoordinationError, match="not APPROVED"):
        store.lease_job(job_id=job_unapproved, worker_id="worker-1")

    # A real APPROVED approval whose tool/arguments do not match the job.
    _engine2, approval_id, _digest = _approve(arguments={"host": "karmo-ai01"})
    job_mismatched_args = store.enqueue_job(
        idempotency_key=f"mismatched-args:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=approval_id,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest="f" * 64,
    )
    with pytest.raises(WorkerCoordinationError, match="does not match"):
        store.lease_job(job_id=job_mismatched_args, worker_id="worker-1")

    # A real APPROVED approval authorized for a DIFFERENT worker.
    _engine3, approval_id_2, digest_2 = _approve(authorized_executor="worker-2")
    job_wrong_executor = store.enqueue_job(
        idempotency_key=f"wrong-executor:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=approval_id_2,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest_2,
    )
    with pytest.raises(WorkerCoordinationError, match="not the approval's authorized executor"):
        store.lease_job(job_id=job_wrong_executor, worker_id="worker-1")


def test_lease_job_claims_the_approval_and_finalize_closes_it_out():
    """A successful lease atomically claims the backing approval (mirroring
    PostgresExecutionCoordinator.claim), and finalize_job closes it out to a
    real terminal state instead of leaving it CLAIMED forever."""
    approval_store = PostgresApprovalStore(_connection_factory)
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)

    claimed = approval_store.get(lease.approval_id)
    assert claimed.state == ApprovalState.CLAIMED
    assert claimed.execution_binding is not None

    # The same approval can never be claimed a second time by another job.
    duplicate_job = store.enqueue_job(
        idempotency_key=f"duplicate-claim:{uuid.uuid4()}", task_id=str(uuid.uuid4()), approval_id=lease.approval_id,
        tool_id=lease.tool_id, tool_version=lease.tool_version,
        arguments_digest=lease.arguments_digest,
    )
    with pytest.raises(WorkerCoordinationError, match="not APPROVED"):
        store.lease_job(job_id=duplicate_job, worker_id="worker-1")

    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)
    coordinator.authorize_execution(token=token, lease=lease)
    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=envelope)
    store.finalize_job(job_id=job_id, success=True)

    finished = approval_store.get(lease.approval_id)
    assert finished.state == ApprovalState.EXECUTED


def test_register_worker_cannot_silently_rotate_existing_worker_key():
    """HIGH regression: re-calling register_worker for an already-registered
    worker must never change its key -- only a credential-proven rotation
    may."""
    def _keys_v2(key_id):
        return {"worker-key-v1": WORKER_KEY, "worker-key-v2": b"n" * 32}.get(key_id)

    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth = WorkerAuthenticator(KeyResolver(_keys_v2))
    tickets = ExecutionTicketAuthority(KeyResolver(_keys_v2), signing_key_id="coord-key-v1")
    results = ResultAuthenticator(KeyResolver(_keys_v2))
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)

    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    with pytest.raises(WorkerCoordinationError, match="already registered"):
        store.register_worker(worker_id="worker-1", key_id="attacker-key")

    # The original key still authenticates; an attacker-supplied key never took effect.
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=60)
    coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")

    # Rotation without proof of the current key is refused.
    with pytest.raises(WorkerCoordinationError, match="does not match"):
        store.rotate_key(worker_id="worker-1", current_key_id="wrong-key", new_key_id="worker-key-v2")

    # Rotation proven with a credential signed by the CURRENT key succeeds.
    rotation_credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=60)
    coordinator.rotate_worker_key(credential_token=rotation_credential, worker_id="worker-1", new_key_id="worker-key-v2")

    # The old key no longer authenticates; the new one does.
    with pytest.raises(WorkerCoordinationError):
        coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1")
    new_credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v2", ttl_seconds=60)
    coordinator.authenticate_heartbeat(credential_token=new_credential, worker_id="worker-1")


def test_update_capabilities_grants_new_claim_to_active_worker():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1", capabilities=["commander.system_snapshot"])

    updated = store.update_capabilities(worker_id="worker-1", add_capabilities=["model_chat"])

    assert updated == ("commander.system_snapshot", "model_chat")


def test_update_capabilities_appends_a_durable_event():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")

    store.update_capabilities(worker_id="worker-1", add_capabilities=["model_chat"])

    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_type FROM public.karmo_worker_events WHERE worker_id=%s ORDER BY created_at DESC LIMIT 1",
            ("worker-1",),
        )
        assert cur.fetchone()[0] == "WORKER_CAPABILITIES_UPDATED"


def test_update_capabilities_is_a_noop_if_already_claimed():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1", capabilities=["model_chat"])

    updated = store.update_capabilities(worker_id="worker-1", add_capabilities=["model_chat"])

    assert updated == ("model_chat",)


def test_update_capabilities_refuses_nonexistent_worker():
    store = PostgresWorkerCoordinatorStore(_connection_factory)

    with pytest.raises(WorkerCoordinationError, match="inactive/revoked or does not exist"):
        store.update_capabilities(worker_id="ghost-worker", add_capabilities=["model_chat"])


def test_update_capabilities_refuses_revoked_worker():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.revoke_worker("worker-1")

    with pytest.raises(WorkerCoordinationError, match="inactive/revoked or does not exist"):
        store.update_capabilities(worker_id="worker-1", add_capabilities=["model_chat"])


def test_update_capabilities_refuses_while_worker_has_leased_work():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    _setup_leased_job(store, worker_auth, coordinator)

    with pytest.raises(WorkerCoordinationError, match="leased work"):
        store.update_capabilities(worker_id="worker-1", add_capabilities=["model_chat"])


def test_update_capabilities_rejects_empty_grant():
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")

    with pytest.raises(WorkerCoordinationError, match="non-empty"):
        store.update_capabilities(worker_id="worker-1", add_capabilities=[])


def test_revoked_worker_cannot_consume_ticket_or_submit_result_midflight():
    """HIGH regression: revocation must be effective against work already
    leased/ticketed, not just against future heartbeats/leases."""
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results)
    credential, job_id, lease = _setup_leased_job(store, worker_auth, coordinator)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease)

    store.revoke_worker("worker-1")

    with pytest.raises(WorkerCoordinationError, match="not active"):
        coordinator.authorize_execution(token=token, lease=lease)

    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(WorkerCoordinationError, match="not active"):
        coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=envelope)
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_stale_heartbeat_worker_cannot_submit_result_even_with_valid_job_lease():
    """HIGH regression: a worker whose heartbeat has gone stale must not be
    trusted at result-submission time, even if its independent job lease
    (set once, at lease_job time) has not yet expired."""
    class Clock:
        def __init__(self):
            self.now = datetime.now(timezone.utc)
        def __call__(self):
            return self.now

    clock = Clock()
    store = PostgresWorkerCoordinatorStore(_connection_factory, clock=clock)
    worker_auth = WorkerAuthenticator(KeyResolver(_keys), clock=lambda: clock.now.timestamp())
    tickets = ExecutionTicketAuthority(KeyResolver(_keys), signing_key_id="coord-key-v1", clock=lambda: clock.now.timestamp())
    results = ResultAuthenticator(KeyResolver(_keys))
    coordinator = WorkerCoordinator(store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results, clock=lambda: clock.now)

    store.register_worker(worker_id="worker-1", key_id="worker-key-v1")
    store.heartbeat(worker_id="worker-1", credential_key_id="worker-key-v1", lease_seconds=5)  # short heartbeat
    _engine, approval_id, digest = _approve()
    task_id = str(uuid.uuid4())
    job_id = store.enqueue_job(
        idempotency_key=f"{task_id}:host_health", task_id=task_id, approval_id=approval_id,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest,
    )
    lease = store.lease_job(job_id=job_id, worker_id="worker-1", lease_seconds=300)  # long job lease
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=999999)
    token = coordinator.issue_execution_ticket(credential_token=credential, lease=lease, ttl_seconds=999999)
    coordinator.authorize_execution(token=token, lease=lease)

    clock.now += timedelta(seconds=10)  # heartbeat (5s) now stale; job lease (300s) still valid

    result = {"ok": True}
    envelope = results.sign(
        worker_id="worker-1", key_id="worker-key-v1", task_id=lease.task_id,
        result=result, execution_ticket_digest=token_digest(token),
    )
    with pytest.raises(WorkerCoordinationError, match="heartbeat lease expired"):
        coordinator.accept_result(execution_ticket=token, lease=lease, result=result, envelope=envelope)
    assert store.get_job_state(job_id)["state"] == "LEASED"


def test_enqueue_job_requires_idempotency_key_and_refuses_duplicates():
    """MEDIUM regression: a retried enqueue_job call for the same logical
    attempt must never silently create a second job row -- unlike
    approval_id (fixed separately), there was previously no unique-key
    protection here at all, unlike tool_invocation_ledger.idempotency_key."""
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    _engine, approval_id, digest = _approve()
    task_id = str(uuid.uuid4())

    with pytest.raises(WorkerCoordinationError, match="idempotency_key is required"):
        store.enqueue_job(
            idempotency_key="", task_id=task_id, approval_id=approval_id,
            tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest,
        )

    key = f"{task_id}:host_health:attempt-1"
    job_id = store.enqueue_job(
        idempotency_key=key, task_id=task_id, approval_id=approval_id,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest,
    )

    # A retry with the SAME idempotency_key (e.g. after a timeout where the
    # caller doesn't know whether the first enqueue landed) must not create
    # a second job -- it must fail loudly, exactly like
    # PostgresInvocationLedger.begin() does for a reused key.
    with pytest.raises(WorkerCoordinationError, match="duplicate worker-job idempotency key"):
        store.enqueue_job(
            idempotency_key=key, task_id=task_id, approval_id=approval_id,
            tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest,
        )
    existing = store.get_job_by_idempotency_key(key)
    assert existing["job_id"] == job_id
    assert existing["state"] == "QUEUED"

    # A deliberately new attempt (new idempotency_key) for the same logical
    # task/tool/arguments is still allowed -- this is dedup for retries, not
    # a permanent per-task/tool lock.
    _engine2, approval_id_2, digest_2 = _approve()
    other_job_id = store.enqueue_job(
        idempotency_key=f"{task_id}:host_health:attempt-2", task_id=task_id, approval_id=approval_id_2,
        tool_id="karmolab.host_health", tool_version="1", arguments_digest=digest_2,
    )
    assert other_job_id != job_id
    assert store.get_job_by_idempotency_key(f"{task_id}:host_health:attempt-2")["job_id"] == other_job_id


def test_outbound_transport_policy_forbids_inbound_or_reachability_authority():
    assert OutboundTransportPolicy().validate() is True
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(worker_inbound_listener=True).validate()
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(reachability_grants_authority=True).validate()
    with pytest.raises(WorkerCoordinationError):
        OutboundTransportPolicy(require_encrypted_transport=False).validate()


def test_dispatch_and_wait_full_round_trip_against_the_real_worker_job_pipeline():
    """Model Router Phase D1's Core-side glue, proven against the REAL
    worker job/ticket/result pipeline (not fakes) -- enqueue via
    dispatch_and_wait, then drive the worker side through the real
    PostgresWorkerGatewayBackend exactly as an actual worker's poll/
    authorize/submit_result calls would, and confirm dispatch_and_wait
    surfaces the genuine result content, not just a digest."""
    store = PostgresWorkerCoordinatorStore(_connection_factory)
    worker_auth, tickets, results = _crypto()
    coordinator = WorkerCoordinator(
        store, worker_authenticator=worker_auth, ticket_authority=tickets, result_authenticator=results,
    )
    gateway_backend = PostgresWorkerGatewayBackend(
        store=store, coordinator=coordinator, connection_factory=_connection_factory,
    )
    approval_engine = ApprovalEngine(store=PostgresApprovalStore(_connection_factory))

    store.register_worker(worker_id="worker-1", key_id="worker-key-v1", capabilities=["model_chat_tools"])
    credential = worker_auth.issue(worker_id="worker-1", key_id="worker-key-v1", ttl_seconds=300)
    coordinator.authenticate_heartbeat(credential_token=credential, worker_id="worker-1", lease_seconds=120)

    real_answer = {"content": "the answer is 4", "tool_calls": None}
    worker_acted = {"done": False}

    def simulate_worker_completing_the_job_then_sleep(_seconds):
        if not worker_acted["done"]:
            worker_acted["done"] = True
            polled = gateway_backend.poll(
                worker_id="worker-1", credential_token=credential, capabilities=["model_chat_tools"],
            )
            assert polled is not None
            gateway_backend.authorize_execution(
                worker_id="worker-1", credential_token=credential,
                lease=polled["lease"], execution_ticket=polled["execution_ticket"],
            )
            envelope = results.sign(
                worker_id="worker-1", key_id="worker-key-v1", task_id=polled["lease"]["task_id"],
                result=real_answer, execution_ticket_digest=token_digest(polled["execution_ticket"]),
            )
            gateway_backend.submit_result(
                worker_id="worker-1", credential_token=credential,
                lease=polled["lease"], execution_ticket=polled["execution_ticket"],
                result=real_answer, envelope=envelope, success=True, error=None,
            )
        import time as _time
        _time.sleep(0.02)

    outcome = dispatch_and_wait(
        store=store,
        gateway_backend=gateway_backend,
        approval_engine=approval_engine,
        worker_id="worker-1",
        tool_id="model_chat_tools",
        tool_version="1.0.0",
        arguments={"model": "qwen3:8b", "messages": [{"role": "user", "content": "what is 2+2?"}]},
        total_deadline_seconds=10.0,
        poll_interval_seconds=0.02,
        sleep=simulate_worker_completing_the_job_then_sleep,
    )

    assert outcome.outcome == "SUCCEEDED"
    assert outcome.result == real_answer
    assert store.get_worker_job_result(outcome.job_id)["result"] == real_answer
