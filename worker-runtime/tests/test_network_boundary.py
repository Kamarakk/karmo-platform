import pytest

from capability_manifest import SAFE_CAPABILITIES
from coordinator import Coordinator
from crypto_boundary import KeyResolver, ResultAuthenticator, WorkerAuthenticator
from network_boundary import NetworkBoundaryError, SecureCoordinatorBoundary
from worker_registry import WorkerHealth, WorkerStatus


WORKER_KEY = b"w" * 32
OTHER_WORKER_KEY = b"x" * 32


def _keys(key_id):
    return {
        "worker-1-key": WORKER_KEY,
        "worker-2-key": OTHER_WORKER_KEY,
    }.get(key_id)


def _identity():
    return {
        "hostname": "karmo-worker01",
        "worker_version": "0.1.0",
        "platform": "linux",
        "architecture": "x86_64",
        "capabilities": [dict(SAFE_CAPABILITIES["hash_verify"])],
        "resource_limits": {"cpu": 8, "memory_mb": 10240},
        "labels": ["local", "cpu"],
    }


def _boundary(clock_value=None):
    keys = KeyResolver(_keys)
    if clock_value is None:
        worker_auth = WorkerAuthenticator(keys)
    else:
        worker_auth = WorkerAuthenticator(keys, clock=lambda: clock_value[0])
    result_auth = ResultAuthenticator(keys)
    coordinator = Coordinator()
    boundary = SecureCoordinatorBoundary(
        coordinator,
        worker_authenticator=worker_auth,
        result_authenticator=result_auth,
    )
    return coordinator, boundary, worker_auth, result_auth


def test_every_worker_call_requires_a_valid_bound_credential():
    coordinator, boundary, worker_auth, _ = _boundary()
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=60
    )

    record = boundary.register(
        worker_id="worker-1", credential=credential, **_identity()
    )
    assert record.status == WorkerStatus.REGISTERED

    record = boundary.heartbeat(
        "worker-1", credential=credential, health=WorkerHealth.HEALTHY
    )
    assert record.status == WorkerStatus.AVAILABLE

    with pytest.raises(NetworkBoundaryError):
        boundary.heartbeat("worker-1", credential=credential + "tampered")

    with pytest.raises(NetworkBoundaryError):
        boundary.heartbeat("different-worker", credential=credential)

    assert coordinator.workers.get("worker-1").status == WorkerStatus.AVAILABLE


def test_expired_worker_credential_is_refused_before_coordinator_mutation():
    now = [1_000]
    coordinator, boundary, worker_auth, _ = _boundary(now)
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=10
    )
    boundary.register(worker_id="worker-1", credential=credential, **_identity())
    previous_seen = coordinator.workers.get("worker-1").last_seen

    now[0] = 1_011
    with pytest.raises(NetworkBoundaryError):
        boundary.heartbeat("worker-1", credential=credential)

    assert coordinator.workers.get("worker-1").last_seen == previous_seen


def test_signed_result_is_required_and_bound_to_worker_job_and_output():
    coordinator, boundary, worker_auth, result_auth = _boundary()
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=60
    )
    boundary.register(worker_id="worker-1", credential=credential, **_identity())
    boundary.heartbeat("worker-1", credential=credential, health=WorkerHealth.HEALTHY)

    submitted = coordinator.submit_job(
        capability_id="hash_verify",
        payload={"path": "example.txt"},
        idempotency_key="network-boundary-test-1",
    )
    leased = boundary.poll(
        "worker-1", ["hash_verify"], credential=credential
    )
    assert leased.job_id == submitted.job_id

    output = {"sha256": "abc123"}
    envelope = result_auth.sign(
        worker_id="worker-1",
        key_id="worker-1-key",
        task_id=leased.job_id,
        result=output,
    )

    with pytest.raises(NetworkBoundaryError):
        boundary.submit_result(
            "worker-1",
            leased.job_id,
            credential=credential,
            result_authentication=envelope,
            output={"sha256": "tampered"},
            duration_seconds=0.01,
            stdout_summary="",
        )

    completed = boundary.submit_result(
        "worker-1",
        leased.job_id,
        credential=credential,
        result_authentication=envelope,
        output=output,
        duration_seconds=0.01,
        stdout_summary="",
    )
    assert completed.result.output == output
    assert coordinator.workers.get("worker-1").status == WorkerStatus.AVAILABLE


def test_result_must_use_same_key_as_authenticated_worker_credential():
    coordinator, boundary, worker_auth, result_auth = _boundary()
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=60
    )
    boundary.register(worker_id="worker-1", credential=credential, **_identity())
    boundary.heartbeat("worker-1", credential=credential, health=WorkerHealth.HEALTHY)
    coordinator.submit_job(
        capability_id="hash_verify",
        payload={"path": "example.txt"},
        idempotency_key="network-boundary-key-binding",
    )
    leased = boundary.poll("worker-1", ["hash_verify"], credential=credential)

    output = {"sha256": "abc123"}
    wrong_key_envelope = result_auth.sign(
        worker_id="worker-1",
        key_id="worker-2-key",
        task_id=leased.job_id,
        result=output,
    )

    with pytest.raises(NetworkBoundaryError, match="result key"):
        boundary.submit_result(
            "worker-1",
            leased.job_id,
            credential=credential,
            result_authentication=wrong_key_envelope,
            output=output,
            duration_seconds=0.01,
            stdout_summary="",
        )

    assert coordinator.jobs.get(leased.job_id).result is None


def test_worker_cannot_submit_result_for_another_workers_job():
    coordinator, boundary, worker_auth, result_auth = _boundary()
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=60
    )
    boundary.register(worker_id="worker-1", credential=credential, **_identity())
    boundary.heartbeat("worker-1", credential=credential, health=WorkerHealth.HEALTHY)
    coordinator.submit_job(
        capability_id="hash_verify",
        payload={"path": "example.txt"},
        idempotency_key="network-boundary-test-2",
    )
    leased = boundary.poll("worker-1", ["hash_verify"], credential=credential)

    output = {"sha256": "abc123"}
    envelope = result_auth.sign(
        worker_id="worker-1",
        key_id="worker-1-key",
        task_id=leased.job_id,
        result=output,
    )
    with pytest.raises(NetworkBoundaryError):
        boundary.submit_result(
            "worker-2",
            leased.job_id,
            credential=credential,
            result_authentication=envelope,
            output=output,
            duration_seconds=0.01,
            stdout_summary="",
        )
