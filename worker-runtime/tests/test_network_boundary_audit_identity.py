from capability_manifest import SAFE_CAPABILITIES
from coordinator import Coordinator
from crypto_boundary import KeyResolver, ResultAuthenticator, WorkerAuthenticator
from network_boundary import SecureCoordinatorBoundary
from worker_registry import WorkerHealth


WORKER_KEY = b"w" * 32


def _keys(key_id):
    return {"worker-1-key": WORKER_KEY}.get(key_id)


def test_approval_requester_is_derived_from_authenticated_worker():
    keys = KeyResolver(_keys)
    worker_auth = WorkerAuthenticator(keys)
    coordinator = Coordinator()
    boundary = SecureCoordinatorBoundary(
        coordinator,
        worker_authenticator=worker_auth,
        result_authenticator=ResultAuthenticator(keys),
    )
    credential = worker_auth.issue(
        worker_id="worker-1", key_id="worker-1-key", ttl_seconds=60
    )
    boundary.register(
        worker_id="worker-1",
        credential=credential,
        hostname="karmo-worker01",
        worker_version="0.1.0",
        platform="linux",
        architecture="x86_64",
        capabilities=[dict(SAFE_CAPABILITIES["hash_verify"])],
        resource_limits={"cpu": 8, "memory_mb": 10240},
    )
    boundary.heartbeat("worker-1", credential=credential, health=WorkerHealth.HEALTHY)
    coordinator.submit_job(
        capability_id="hash_verify",
        payload={"path": "example.txt"},
        idempotency_key="audit-identity-test",
    )
    leased = boundary.poll("worker-1", ["hash_verify"], credential=credential)

    # Exercise the approval path directly without expanding the production-safe
    # capability manifest. The boundary must own requester identity regardless of
    # the job's authority level.
    leased.authority_requirement = "EXPLICIT_PER_CALL"
    pending = boundary.request_approval(
        "worker-1", leased.job_id, credential=credential
    )
    approval = coordinator.jobs._approval_engine.get(pending.approval_id)
    assert approval.requester == "worker:worker-1"
