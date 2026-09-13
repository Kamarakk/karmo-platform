from datetime import datetime, timedelta, timezone

import pytest

from core_service.worker_gateway_backend import (
    PostgresWorkerGatewayBackend,
    WorkerGatewayBackendError,
    lease_from_wire,
    lease_to_wire,
)
from core_service.worker_coordination import WorkerCoordinationError, WorkerLease


NOW = datetime.now(timezone.utc)


def _lease(worker_id="karmo-worker01", job_id="job-1"):
    return WorkerLease(
        job_id=job_id,
        task_id="task-1",
        worker_id=worker_id,
        lease_token="lease-1",
        tool_id="karmolab.host_health",
        tool_version="1",
        arguments_digest="a" * 64,
        approval_id="approval-1",
        attempt_count=1,
        lease_expires_at=NOW + timedelta(seconds=60),
    )


class Auth:
    def __init__(self):
        self.calls = []

    def verify(self, token, *, expected_worker_id):
        self.calls.append((token, expected_worker_id))
        if token != "credential":
            raise RuntimeError("bad credential")
        return {"key_id": "worker-key-v1", "worker_id": expected_worker_id}


class Store:
    def __init__(self):
        self.required = []
        self.leased = []
        self.finalized = []
        self.fail_first = False

    def require_current_key(self, *, worker_id, key_id):
        self.required.append((worker_id, key_id))
        return True

    def lease_job(self, *, job_id, worker_id):
        self.leased.append((job_id, worker_id))
        if self.fail_first and len(self.leased) == 1:
            raise WorkerCoordinationError("lost race")
        return _lease(worker_id=worker_id, job_id=job_id)

    def finalize_job(self, *, job_id, success, error=None):
        self.finalized.append((job_id, success, error))


class Coordinator:
    def __init__(self):
        self.worker_authenticator = Auth()
        self.authorized = []
        self.accepted = []

    def authenticate_heartbeat(self, *, credential_token, worker_id, lease_seconds):
        assert credential_token == "credential"
        assert worker_id == "karmo-worker01"
        return NOW + timedelta(seconds=lease_seconds)

    def issue_execution_ticket(self, *, credential_token, lease):
        assert credential_token == "credential"
        return "signed-ticket"

    def authorize_execution(self, *, token, lease):
        self.authorized.append((token, lease))
        return True

    def accept_result(self, *, execution_ticket, lease, result, envelope):
        self.accepted.append((execution_ticket, lease, result, envelope))
        return "result-digest"


class Cursor:
    def __init__(self, worker_caps, candidate_ids):
        self.worker_caps = worker_caps
        self.candidate_ids = candidate_ids
        self.last_query = ""
        self.params = None

    def execute(self, query, params):
        self.last_query = query
        self.params = params

    def fetchone(self):
        return (self.worker_caps, "ACTIVE", NOW + timedelta(seconds=90))

    def fetchall(self):
        eligible, worker_id, limit = self.params
        assert set(eligible).issubset(set(self.worker_caps))
        assert worker_id == "karmo-worker01"
        assert limit <= 128
        return [(job_id,) for job_id in self.candidate_ids]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _backend(*, caps=None, jobs=None):
    store = Store()
    coordinator = Coordinator()
    cursor = Cursor(
        caps or ["karmolab.host_health", "karmolab.repo_status"],
        jobs or ["job-1"],
    )
    backend = PostgresWorkerGatewayBackend(
        store=store,
        coordinator=coordinator,
        connection_factory=lambda: Connection(cursor),
    )
    return backend, store, coordinator, cursor


def test_lease_wire_roundtrip_requires_exact_worker_binding():
    original = _lease()
    wire = lease_to_wire(original)
    assert lease_from_wire(wire, expected_worker_id="karmo-worker01") == original
    with pytest.raises(WorkerGatewayBackendError, match="identity mismatch"):
        lease_from_wire(wire, expected_worker_id="karmo-worker02")


def test_poll_worker_claimed_capabilities_only_narrow_registered_capabilities():
    backend, store, coordinator, cursor = _backend()
    response = backend.poll(
        worker_id="karmo-worker01",
        credential_token="credential",
        capabilities=["karmolab.host_health", "unregistered.admin"],
    )
    assert cursor.params[0] == ["karmolab.host_health"]
    assert store.required == [("karmo-worker01", "worker-key-v1")]
    assert store.leased == [("job-1", "karmo-worker01")]
    assert response["execution_ticket"] == "signed-ticket"
    assert response["lease"]["worker_id"] == "karmo-worker01"


def test_poll_lease_transition_race_fails_closed_instead_of_masking_authority_change():
    backend, store, coordinator, cursor = _backend(jobs=["job-1", "job-2"])
    store.fail_first = True
    with pytest.raises(WorkerCoordinationError, match="lost race"):
        backend.poll(
            worker_id="karmo-worker01",
            credential_token="credential",
            capabilities=["karmolab.host_health"],
        )
    assert store.leased == [("job-1", "karmo-worker01")]


def test_authorize_execution_authenticates_current_key_then_consumes_ticket():
    backend, store, coordinator, _ = _backend()
    wire = lease_to_wire(_lease())
    assert backend.authorize_execution(
        worker_id="karmo-worker01",
        credential_token="credential",
        lease=wire,
        execution_ticket="signed-ticket",
    ) == {"authorized": True}
    assert store.required == [("karmo-worker01", "worker-key-v1")]
    assert coordinator.authorized[0][0] == "signed-ticket"


def test_submit_result_accepts_authenticated_result_before_terminal_finalization():
    backend, store, coordinator, _ = _backend()
    wire = lease_to_wire(_lease())
    response = backend.submit_result(
        worker_id="karmo-worker01",
        credential_token="credential",
        lease=wire,
        execution_ticket="signed-ticket",
        result={"status": "healthy"},
        envelope={"payload": {"key_id": "worker-key-v1"}, "signature": "sig"},
        success=True,
        error=None,
    )
    assert response == {
        "accepted": True,
        "state": "SUCCEEDED",
        "result_digest": "result-digest",
    }
    assert len(coordinator.accepted) == 1
    assert store.finalized == [("job-1", True, None)]


def test_submit_result_rejects_cross_worker_lease_before_coordinator_call():
    backend, store, coordinator, _ = _backend()
    wire = lease_to_wire(_lease(worker_id="karmo-worker02"))
    with pytest.raises(WorkerGatewayBackendError, match="identity mismatch"):
        backend.submit_result(
            worker_id="karmo-worker01",
            credential_token="credential",
            lease=wire,
            execution_ticket="signed-ticket",
            result={},
            envelope={},
            success=False,
            error="failed",
        )
    assert coordinator.accepted == []
    assert store.finalized == []
