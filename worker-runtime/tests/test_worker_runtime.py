"""KARMO Worker Runtime v0.1 -- failure and adversarial test suite (Phase 11).

Exactly the 24 numbered scenarios required by the authorizing instruction,
each as its own test (or tight group of tests) named test_scenario_NN_*,
plus a handful of supporting capability/integration tests that are not
part of the 24 but exercise the real end-to-end pull-based flow and the
real Phase 9 capability handlers against the synthetic fixture workspace.

No production data, no external network access, no real model downloads
anywhere in this file. The model_chat tests use a local loopback HTTP
test double (127.0.0.1, ephemeral port, this process only) rather than a
real Ollama instance -- required because run_capability now executes
handlers in a spawned (not forked) child, which re-imports capabilities.py
fresh and cannot see a monkeypatched function or module attribute from
the parent process; only real, externally-observable state (an actual
socket, an env var) crosses that boundary.
"""

import base64
import hashlib
import http.server
import json
import multiprocessing
import os
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import capabilities  # noqa: F401 -- import for its registration side effect (sandbox._HANDLERS population)
from approval_engine_reuse import ApprovalState
from capability_manifest import CapabilityManifestError, SAFE_CAPABILITIES, validate_capability_declaration
from coordinator import Coordinator, CoordinatorError
from job_model_reuse import JobState, JobStateError
from job_protocol import JobProtocolError
from sandbox import (
    MAX_EVIDENCE_FILES,
    MAX_RESULT_BYTES,
    PathTraversalError,
    SandboxError,
    _HANDLERS,
    register_handler,
    resolve_within_sandbox,
    run_capability,
)
from tool_registry_reuse import CapabilityClass
from transport import LocalTransport
from worker_client import WorkerClient, WorkerClientError
from worker_registry import WorkerHealth, WorkerRegistryError, WorkerStatus

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "allowed_workspace"


def _unused_loopback_port() -> int:
    """A port nothing is listening on, for the connection-refused case --
    bind-then-close guarantees it was free at the instant of the check."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class _FakeOllamaServer:
    """Local loopback HTTP double for Ollama's /api/generate, scoped to one
    test. Runs in a background thread in THIS process (not the sandboxed
    child), so recording what it received is a plain shared list -- no
    cross-process/pickling concerns."""

    def __init__(self, *, status_code=200, response_body=b'{"response": "ok"}'):
        self.received_bodies = []
        outer = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                outer.received_bodies.append(json.loads(raw.decode("utf-8")))
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_body)

            def log_message(self, format, *args):  # noqa: A002 -- silence test output
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._server.shutdown()
        self._server.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/api/generate"

    @property
    def chat_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/api/chat"


class FakeClock:
    def __init__(self, start=None):
        self._now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self._now

    def advance(self, seconds):
        self._now += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def coordinator(clock):
    return Coordinator(clock=clock)


@pytest.fixture
def approval_required_capability(monkeypatch):
    """A synthetic capability whose computed authority_requirement is not
    NONE -- none of the real Phase 9 SAFE_CAPABILITIES require approval,
    but the approval-gates-execution mechanism must still be provably
    correct against something that does. Also registers a real sandbox
    handler for it (reusing hash_verify's), so end-to-end tests that
    actually execute it (not just exercise job_protocol directly) work."""
    synthetic = dict(SAFE_CAPABILITIES["hash_verify"])
    synthetic["capability_id"] = "synthetic_approval_gated"
    synthetic["authority_class"] = CapabilityClass.REVERSIBLE_WRITE
    monkeypatch.setitem(SAFE_CAPABILITIES, "synthetic_approval_gated", synthetic)
    monkeypatch.setitem(_HANDLERS, "synthetic_approval_gated", _HANDLERS["hash_verify"])
    return "synthetic_approval_gated"


STANDARD_CAPS = ["hash_verify", "pytest", "static_analysis", "repository_analysis", "resource_benchmark"]


def _caps(*capability_ids):
    return [{"capability_id": cid} for cid in capability_ids]


def _register(coordinator, worker_id="dev01", capabilities=None, **overrides):
    kwargs = dict(
        worker_id=worker_id,
        hostname="karmo-dev01.local",
        worker_version="0.1.0",
        platform="Darwin",
        architecture="arm64",
        capabilities=_caps(*(capabilities or STANDARD_CAPS)),
        resource_limits={"cpu": 8, "memory_mb": 8192},
    )
    kwargs.update(overrides)
    return coordinator.register_worker(**kwargs)


# --- Scenario 1: worker registration ---------------------------------------

def test_scenario_01_worker_registration(coordinator):
    record = _register(coordinator)
    assert record.worker_id == "dev01"
    assert record.status == WorkerStatus.REGISTERED
    assert record.hostname == "karmo-dev01.local"
    assert record.architecture == "arm64"
    assert set(record.capabilities) == set(STANDARD_CAPS)
    assert coordinator.workers.get("dev01") is record


# --- Scenario 2: duplicate worker registration ------------------------------

def test_scenario_02_duplicate_registration_same_identity_is_idempotent(coordinator):
    first = _register(coordinator)
    second = _register(coordinator, worker_version="0.1.1")
    assert first is second
    assert second.worker_version == "0.1.1"


def test_scenario_02_duplicate_registration_conflicting_identity_is_refused(coordinator):
    _register(coordinator)
    with pytest.raises(CoordinatorError, match="different identity"):
        _register(coordinator, hostname="some-other-host.local")


# --- Scenario 3: heartbeat ---------------------------------------------------

def test_scenario_03_heartbeat_moves_worker_to_available(coordinator, clock):
    _register(coordinator)
    clock.advance(5)
    record = coordinator.heartbeat("dev01")
    assert record.status == WorkerStatus.AVAILABLE
    assert record.last_seen == clock()


# --- Scenario 4: worker goes offline -----------------------------------------

def test_scenario_04_worker_goes_offline_after_heartbeat_timeout(coordinator, clock):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    clock.advance(91)  # default heartbeat_timeout_seconds=90
    coordinator.workers.sweep_stale_workers()
    assert coordinator.workers.get("dev01").status == WorkerStatus.OFFLINE


# =============================================================================
# Worker-reported health vs. coordinator-owned scheduling state (fix
# verification). Prior to this fix, heartbeat(..., status=...) accepted
# ANY WorkerStatus from the caller, letting a worker force itself
# AVAILABLE while the coordinator still held it BUSY on a live lease (or
# vice versa) -- bypassing mark_busy()/mark_available()'s lease-driven
# authority entirely. heartbeat() now only accepts an optional `health`
# (WorkerHealth.HEALTHY/DEGRADED); BUSY is untouchable by a worker's own
# heartbeat, in either direction.
# =============================================================================

def test_worker_cannot_force_itself_available_via_heartbeat_while_busy(coordinator):
    """The core exploit this fix closes: a worker holding a live lease
    (BUSY) heartbeats -- with or without a health value -- and must NOT
    be able to make itself AVAILABLE again behind the coordinator's back,
    which would let the coordinator double-lease a second job to a
    worker still executing the first."""
    _register(coordinator, capabilities=["hash_verify"])
    coordinator.heartbeat("dev01")
    coordinator.submit_job(capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="busy-1")
    leased = coordinator.poll_for_job("dev01", ["hash_verify"])
    assert leased is not None
    assert coordinator.workers.get("dev01").status == WorkerStatus.BUSY

    coordinator.heartbeat("dev01")  # plain heartbeat, no health value
    assert coordinator.workers.get("dev01").status == WorkerStatus.BUSY  # must NOT have flipped to AVAILABLE

    coordinator.heartbeat("dev01", health=WorkerHealth.HEALTHY)
    assert coordinator.workers.get("dev01").status == WorkerStatus.BUSY  # still BUSY -- health cannot override a lease

    # And the job is still leased to this worker -- no double-lease
    # occurred because of the heartbeat.
    second_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="busy-2",
    )
    assert coordinator.poll_for_job("dev01", ["hash_verify"]) is None  # worker still BUSY, not eligible


def test_heartbeat_no_longer_accepts_an_arbitrary_status_kwarg(coordinator):
    """The old signature -- heartbeat(worker_id, status=WorkerStatus.X) --
    must be gone. A caller attempting the old raw status override gets a
    TypeError (unexpected keyword), not a silently-accepted scheduling
    override."""
    _register(coordinator)
    with pytest.raises(TypeError):
        coordinator.workers.heartbeat("dev01", status=WorkerStatus.AVAILABLE)


def test_worker_can_self_report_degraded_health_without_touching_a_live_lease(coordinator):
    """Preserve a safe way to report DEGRADED: allowed when the worker is
    AVAILABLE (not currently leased anything), refused/ignored-for-status
    purposes when BUSY (the coordinator, not the worker, owns that
    transition)."""
    _register(coordinator)
    coordinator.heartbeat("dev01")
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE

    coordinator.heartbeat("dev01", health=WorkerHealth.DEGRADED)
    assert coordinator.workers.get("dev01").status == WorkerStatus.DEGRADED
    # A DEGRADED worker is not eligible for new work.
    assert coordinator.workers.eligible_workers("hash_verify") == []

    # Recovery: a subsequent healthy heartbeat brings it back.
    coordinator.heartbeat("dev01")
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE


def test_worker_busy_on_a_lease_cannot_self_report_degraded_out_of_it(coordinator):
    _register(coordinator, capabilities=["hash_verify"])
    coordinator.heartbeat("dev01")
    coordinator.submit_job(capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="busy-degrade-1")
    coordinator.poll_for_job("dev01", ["hash_verify"])
    assert coordinator.workers.get("dev01").status == WorkerStatus.BUSY

    coordinator.heartbeat("dev01", health=WorkerHealth.DEGRADED)
    assert coordinator.workers.get("dev01").status == WorkerStatus.BUSY  # unchanged -- coordinator owns BUSY exits


def test_heartbeat_rejects_an_invalid_health_value(coordinator):
    _register(coordinator)
    with pytest.raises(CoordinatorError):
        coordinator.heartbeat("dev01", health="not-a-real-health-value")


# --- Scenario 5: capability missing ------------------------------------------

def test_scenario_05_capability_missing_excludes_worker_from_eligibility(coordinator):
    _register(coordinator, capabilities=["hash_verify"])
    coordinator.heartbeat("dev01")
    assert coordinator.workers.is_eligible("dev01", "pytest") is False
    assert coordinator.workers.eligible_workers("pytest") == []
    assert coordinator.workers.is_eligible("dev01", "hash_verify") is True


# --- Scenario 6: unauthorized capability -------------------------------------

def test_scenario_06_unauthorized_capability_registration_refused(coordinator):
    with pytest.raises(CoordinatorError, match="permanently excluded"):
        _register(coordinator, capabilities=["ssh"])


def test_scenario_06_worker_cannot_be_leased_a_job_outside_its_capabilities(coordinator):
    _register(coordinator, capabilities=["hash_verify"])
    coordinator.heartbeat("dev01")
    coordinator.submit_job(
        capability_id="pytest", payload={"test_dir": "sample_tests"},
        idempotency_key="k-unauth-1",
    )
    leased = coordinator.poll_for_job("dev01", capabilities=["pytest"])
    assert leased is None  # worker never even sees a job for a capability it doesn't hold


# --- Scenario 7: malformed job ------------------------------------------------

def test_scenario_07_malformed_job_unknown_capability_refused_at_submit(coordinator):
    with pytest.raises(CoordinatorError):
        coordinator.submit_job(capability_id="not_a_real_capability", payload={}, idempotency_key="k-malformed-1")


def test_scenario_07_malformed_payload_fails_cleanly_at_execution(coordinator, clock):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    coordinator.submit_job(capability_id="hash_verify", payload={}, idempotency_key="k-malformed-2")  # missing "path"
    leased = coordinator.poll_for_job("dev01", capabilities=["hash_verify"])
    assert leased is not None
    with pytest.raises(SandboxError):
        run_capability("hash_verify", leased.payload, timeout_seconds=30, allowed_root=FIXTURES)


# --- Scenario 8: payload digest mismatch -------------------------------------

def test_scenario_08_payload_digest_mismatch_refuses_lease(coordinator):
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-digest-1",
    )
    with pytest.raises(JobProtocolError, match="digest mismatch"):
        coordinator.jobs.lease(
            worker_job.job_id, worker_id="dev01",
            presented_payload={"path": "sample_document.txt", "extra": "tampered"},
        )
    # Job must remain untouched -- available for a legitimate worker.
    assert coordinator.jobs.get(worker_job.job_id).state == JobState.QUEUED


# --- Scenario 9: duplicate job submission ------------------------------------

def test_scenario_09_duplicate_job_submission_is_idempotent(coordinator):
    first = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-dup-1",
    )
    second = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-dup-1",
    )
    assert first.job_id == second.job_id
    assert first is second


# --- Scenario 10: duplicate execution attempt --------------------------------

def test_scenario_10_duplicate_execution_attempt_refused_while_lease_live(coordinator):
    _register(coordinator)
    _register(coordinator, worker_id="dev02", hostname="karmo-dev02.local")
    coordinator.heartbeat("dev01")
    coordinator.heartbeat("dev02")

    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-dupexec-1",
    )
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    with pytest.raises(JobProtocolError):
        coordinator.jobs.lease(worker_job.job_id, worker_id="dev02", presented_payload=worker_job.payload)


# --- Scenario 11: worker crash before execution ------------------------------

def test_scenario_11_worker_crash_before_execution_allows_stale_lease_reclaim(coordinator, clock):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-crash-1",
    )
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    assert coordinator.jobs.get(worker_job.job_id).job.attempt_count == 1

    clock.advance(200)  # exceeds default lease_seconds=120 -- worker never came back
    reclaimed = coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    assert reclaimed.job.attempt_count == 2  # a fresh claim, not a reuse of the dead lease


# --- Scenario 12: worker crash after execution before ack --------------------

def test_scenario_12_stale_claim_token_is_fenced_out_after_reclaim(coordinator, clock):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-crash-2",
    )
    leased = coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    original_token = leased.job.claim_token  # the crashed worker's own token, captured before it "dies"

    clock.advance(200)  # lease expires; worker never submitted a result
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)  # reclaimed

    # The (conceptually crashed, now-returned) original worker tries to
    # complete using its now-stale claim_token -- must be fenced, exactly
    # like the H0.1 outbox relay's own claim-token fencing.
    with pytest.raises(JobStateError, match="stale claim_token"):
        coordinator.jobs.complete(
            worker_job.job_id, output={"sha256": "deadbeef"}, duration_seconds=0.1,
            stdout_summary="late", claim_token=original_token,
        )


# --- Scenario 13: stale lease ------------------------------------------------

def test_scenario_13_stale_lease_is_explicitly_reclaimable(coordinator, clock):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-stale-1",
    )
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    # Immediately re-leasing before expiry must fail...
    with pytest.raises(JobProtocolError):
        coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    # ...but after the lease window elapses, it becomes reclaimable.
    clock.advance(121)
    reclaimed = coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    assert reclaimed.state == JobState.RUNNING


# --- Scenario 14: timeout -----------------------------------------------------
#
# These probe handlers are module-level, not nested closures: run_capability
# now executes handlers in a spawned child, which requires the target to be
# picklable by reference. A function defined inside a test (and, worse, one
# that closes over a per-test local like a tmp_path marker) cannot be
# pickled at all -- pass any per-test data through the payload dict instead,
# the same way a real handler receives its arguments.

def _slow_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    time.sleep(0.2)
    return {"ok": True}, "slow", []


register_handler("test_slow_probe", _slow_probe_handler)


def _hanging_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    time.sleep(2.0)
    Path(payload["marker_path"]).write_text("i finished")  # must never happen -- killed first
    return {"ok": True}, "should not get here", []


register_handler("test_hanging_probe", _hanging_probe_handler)


def _oversized_output_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    huge_output = {"data": "x" * (MAX_RESULT_BYTES + 1024)}
    return huge_output, "small summary", []


register_handler("test_oversized_output_probe", _oversized_output_probe_handler)


def test_scenario_14_execution_exceeding_timeout_is_refused():
    with pytest.raises(SandboxError, match="exceeded its"):
        run_capability("test_slow_probe", {}, timeout_seconds=0.05)


def test_scenario_14_timeout_is_a_real_kill_not_a_post_hoc_check(tmp_path):
    """Proves the deadline is actually enforced, not merely measured
    after the fact: the handler only writes its 'finished' marker file
    AFTER a long sleep. If the child process were allowed to run to
    completion (the old, insufficient post-return elapsed-time check),
    the marker would exist by the time run_capability returns. With a
    real kill, the process is terminated mid-sleep and the marker is
    never written."""
    marker = tmp_path / "finished.marker"

    start = time.monotonic()
    with pytest.raises(SandboxError, match="exceeded its"):
        run_capability("test_hanging_probe", {"marker_path": str(marker)}, timeout_seconds=0.2)
    elapsed = time.monotonic() - start

    assert elapsed < 1.5  # returned well before the handler's 2.0s sleep would have finished
    assert not marker.exists()  # the process was actually killed, not merely reported as timed out


# --- Bound the complete returned result (not only stdout_summary) -------------

def test_oversized_structured_output_is_refused_not_truncated():
    with pytest.raises(SandboxError, match="oversized result"):
        run_capability("test_oversized_output_probe", {}, timeout_seconds=5)


def _too_many_evidence_files_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    evidence_files = [f"file-{i}.txt" for i in range(MAX_EVIDENCE_FILES + 1)]
    return {"ok": True}, "summary", evidence_files


register_handler("test_too_many_evidence_probe", _too_many_evidence_files_probe_handler)


def test_oversized_evidence_files_list_is_refused():
    with pytest.raises(SandboxError, match="too many evidence files"):
        run_capability("test_too_many_evidence_probe", {}, timeout_seconds=5)


# --- Scenario 15: cancellation ------------------------------------------------

def test_scenario_15_cancellation_of_queued_job(coordinator):
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-cancel-1",
    )
    cancelled = coordinator.jobs.cancel(worker_job.job_id, reason="no longer needed")
    assert cancelled.state == JobState.CANCELLED


def test_scenario_15_cancellation_of_running_job(coordinator):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-cancel-2",
    )
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    cancelled = coordinator.jobs.cancel(worker_job.job_id, reason="superseded")
    assert cancelled.state == JobState.CANCELLED


# --- Scenario 16: result digest ------------------------------------------------

def test_scenario_16_result_digest_is_deterministic(coordinator):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    worker_job = coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-digest-out-1",
    )
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    output = {"sha256": "abc123", "path": "sample_document.txt"}
    completed = coordinator.finalize_success(
        worker_job.job_id, output=output, duration_seconds=0.01, stdout_summary="ok",
    )

    expected = hashlib.sha256(
        json.dumps(output, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    assert completed.result.result_digest == expected


# --- Scenario 17: changed arguments invalidate an approval binding ------------

def test_scenario_17_changed_arguments_invalidate_approval_binding(coordinator, monkeypatch):
    # Inject a synthetic capability requiring approval (REVERSIBLE_WRITE)
    # for this test only -- none of the real Phase 9 SAFE_CAPABILITIES
    # require approval, but the mechanism must still be provably correct.
    synthetic = dict(SAFE_CAPABILITIES["hash_verify"])
    synthetic["capability_id"] = "synthetic_reversible_write"
    synthetic["authority_class"] = CapabilityClass.REVERSIBLE_WRITE
    monkeypatch.setitem(SAFE_CAPABILITIES, "synthetic_reversible_write", synthetic)

    worker_job = coordinator.jobs.submit(
        capability_id="synthetic_reversible_write", payload={"path": "sample_document.txt"},
        idempotency_key="k-approval-1",
    )
    assert worker_job.authority_requirement != "NONE"

    _register(coordinator, capabilities=["synthetic_reversible_write"])
    coordinator.heartbeat("dev01")
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)
    coordinator.jobs.request_approval_if_required(worker_job.job_id, requester="kamara")
    coordinator.jobs.approve(worker_job.job_id, approver="kamara")

    # A material argument change after the approval was bound must not be
    # completable under the original approval -- attempting to lease with
    # different payload (simulating a changed job) is refused by the
    # digest check exactly as in scenario 8; the approval stays bound to
    # the ORIGINAL payload_digest and is never silently reused for
    # different arguments.
    assert worker_job.payload_digest == coordinator.jobs.get(worker_job.job_id).payload_digest
    with pytest.raises(JobProtocolError, match="digest mismatch"):
        coordinator.jobs.lease(
            worker_job.job_id, worker_id="dev01",
            presented_payload={"path": "sample_document.txt", "changed": "yes"},
        )


# =============================================================================
# Approval gates EXECUTION, not merely completion (fix verification).
#
# Prior to this fix, a worker's sandboxed capability handler ran
# unconditionally the moment a job was leased -- approval state was only
# ever checked afterward, at complete() time, by which point the (possibly
# unapproved/unauthorized/tampered) execution had already happened.
# job_protocol.WorkerJobQueue.execute() is now the single choke point: for
# any capability whose computed authority_requirement is not NONE, the
# action (the actual sandboxed execution) is only ever invoked from
# INSIDE the reused ApprovalEngine.execute() -- never duplicated here --
# which enforces approval state, executor identity, expiry, an exact
# arguments digest, and single-use consumption into EXECUTED.
# =============================================================================

def _lease_and_request_approval(coordinator, worker_job, worker_id="dev01"):
    _register(coordinator, worker_id=worker_id, capabilities=[worker_job.capability_id])
    coordinator.heartbeat(worker_id)
    coordinator.jobs.lease(worker_job.job_id, worker_id=worker_id, presented_payload=worker_job.payload)
    coordinator.jobs.request_approval_if_required(worker_job.job_id, requester="kamara")
    return worker_job


def test_approval_gate_unapproved_job_cannot_execute(coordinator, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-unapproved",
    )
    _lease_and_request_approval(coordinator, worker_job)  # WAITING_FOR_APPROVAL -- never approved

    executed = []
    with pytest.raises(JobProtocolError):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
            action=lambda: executed.append(True),
        )
    assert executed == []  # the action must never have run


def test_approval_gate_no_approval_requested_at_all_cannot_execute(coordinator, approval_required_capability):
    """Distinct from the above: no approval was even requested (a worker
    skipping the approval step entirely and going straight for
    execution)."""
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-none",
    )
    _register(coordinator, capabilities=[approval_required_capability])
    coordinator.heartbeat("dev01")
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    executed = []
    with pytest.raises(JobProtocolError, match="requires approval"):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
            action=lambda: executed.append(True),
        )
    assert executed == []


def test_approval_gate_expired_approval_cannot_execute(coordinator, clock, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-expired",
    )
    _lease_and_request_approval(coordinator, worker_job)
    coordinator.jobs.approve(worker_job.job_id, approver="kamara", authorized_executor="dev01")

    clock.advance(400)  # WorkerJobQueue's default approval_ttl_seconds=300

    executed = []
    with pytest.raises(JobProtocolError, match="EXPIRED"):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
            action=lambda: executed.append(True),
        )
    assert executed == []


def test_approval_gate_changed_payload_after_approval_cannot_execute(coordinator, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-changed",
    )
    _lease_and_request_approval(coordinator, worker_job)
    coordinator.jobs.approve(worker_job.job_id, approver="kamara", authorized_executor="dev01")

    executed = []
    with pytest.raises(JobProtocolError, match="do not match what was approved"):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev01", presented_payload={"x": 999},
            action=lambda: executed.append(True),
        )
    assert executed == []
    approval = coordinator.jobs._approval_engine.get(worker_job.approval_id)
    assert approval.state == ApprovalState.FAILED  # invalidated, not merely refused for this one call


def test_approval_gate_wrong_executor_cannot_execute(coordinator, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-wrong-executor",
    )
    _lease_and_request_approval(coordinator, worker_job)
    coordinator.jobs.approve(worker_job.job_id, approver="kamara", authorized_executor="dev01")

    executed = []
    with pytest.raises(JobProtocolError, match="does not match"):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev02", presented_payload=worker_job.payload,
            action=lambda: executed.append(True),
        )
    assert executed == []
    approval = coordinator.jobs._approval_engine.get(worker_job.approval_id)
    assert approval.state == ApprovalState.FAILED


def test_approval_gate_one_approval_cannot_execute_twice(coordinator, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-twice",
    )
    _lease_and_request_approval(coordinator, worker_job)
    coordinator.jobs.approve(worker_job.job_id, approver="kamara", authorized_executor="dev01")

    first = coordinator.jobs.execute(
        worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
        action=lambda: {"done": True},
    )
    assert first == {"done": True}

    with pytest.raises(JobProtocolError, match="EXECUTED"):
        coordinator.jobs.execute(
            worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
            action=lambda: {"done": "second attempt -- must never run"},
        )


def test_approval_gate_successful_execution_ends_executed_and_unlocks_completion(coordinator, approval_required_capability):
    worker_job = coordinator.jobs.submit(
        capability_id=approval_required_capability, payload={"x": 1}, idempotency_key="gate-success",
    )
    _lease_and_request_approval(coordinator, worker_job)
    coordinator.jobs.approve(worker_job.job_id, approver="kamara", authorized_executor="dev01")

    result = coordinator.jobs.execute(
        worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
        action=lambda: {"done": True},
    )
    assert result == {"done": True}

    approval = coordinator.jobs._approval_engine.get(worker_job.approval_id)
    assert approval.state == ApprovalState.EXECUTED

    # complete() must now succeed -- it requires EXECUTED, which execute()
    # (not complete() itself) is what actually produces.
    completed = coordinator.finalize_success(
        worker_job.job_id, output={"done": True}, duration_seconds=0.01, stdout_summary="ok",
    )
    assert completed.state == JobState.SUCCEEDED


def test_approval_gate_none_required_capability_executes_directly(coordinator):
    """Control case: a real SAFE_CAPABILITIES entry (authority_requirement
    NONE) must execute without any approval machinery in the way at all."""
    worker_job = coordinator.jobs.submit(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="gate-none-required",
    )
    assert worker_job.authority_requirement == "NONE"
    _register(coordinator)
    coordinator.heartbeat("dev01")
    coordinator.jobs.lease(worker_job.job_id, worker_id="dev01", presented_payload=worker_job.payload)

    result = coordinator.jobs.execute(
        worker_job.job_id, executor_identity="dev01", presented_payload=worker_job.payload,
        action=lambda: {"ran": True},
    )
    assert result == {"ran": True}


def _register_and_park(coordinator, capability_id, worker_id="dev01", idempotency_key="park-1"):
    """Shared setup for the pending-approval WorkerClient tests below:
    register a worker, submit an approval-required job, and drive it
    through poll_and_execute_once() to the parked (WAITING_FOR_APPROVAL)
    state via the real, normal WorkerClient/transport path -- not the
    low-level job_protocol API directly."""
    coordinator.register_worker(
        worker_id=worker_id, hostname=f"{worker_id}.local", worker_version="0.1.0",
        platform="Darwin", architecture="arm64", capabilities=_caps(capability_id),
        resource_limits={"cpu": 8, "memory_mb": 8192},
    )
    coordinator.heartbeat(worker_id)
    coordinator.submit_job(
        capability_id=capability_id, payload={"path": "sample_document.txt"}, idempotency_key=idempotency_key,
    )
    transport = LocalTransport(coordinator)
    client = WorkerClient(worker_id=worker_id, transport=transport, allowed_root=FIXTURES)
    pending = client.poll_and_execute_once([capability_id])
    return client, transport, pending


# =============================================================================
# Pending-approval workflow through the NORMAL WorkerClient/transport path
# (fix for a gap found by re-verification): an approval-required job must
# be able to enter WAITING_FOR_APPROVAL without executing or being marked
# FAILED, sit there safely while polled repeatedly, and later resume
# execution -- exactly once -- once actually approved. The prior design's
# poll_and_execute_once() had no way to represent "legitimately pending"
# as anything but a hard failure, so an approval-required job was marked
# FAILED the instant it was leased, even though nothing was actually
# wrong. request_approval()/resume() (job_protocol.py, coordinator.py,
# transport.py, worker_client.py) fix this. The in-process, callable-based
# transport limitation already documented for execute() is unchanged and
# explicitly NOT redesigned here -- resume() inherits the exact same gap
# (see transport.py's module docstring).
# =============================================================================

def test_worker_client_approval_required_job_parks_without_executing_or_failing(coordinator, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability)

    assert pending is not None
    assert pending.state == JobState.WAITING_FOR_APPROVAL
    assert pending.result is None  # the sandboxed handler never ran
    assert coordinator.jobs.get(pending.job_id).state == JobState.WAITING_FOR_APPROVAL  # not FAILED


def test_worker_client_repeated_polling_while_pending_does_not_execute_or_duplicate(coordinator, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability)
    approval_id = pending.approval_id
    audit_len_before = len(coordinator.jobs._approval_engine.get(approval_id).audit_trail)

    # Polling again: the worker is still BUSY holding the pending job, so
    # no new job is leased and nothing executes.
    again = client.poll_and_execute_once([approval_required_capability])
    assert again is None
    assert coordinator.jobs.get(pending.job_id).state == JobState.WAITING_FOR_APPROVAL

    # Checking in via try_resume() while still unapproved: safe, returns
    # None, no execution, no duplicate approval request.
    for _ in range(3):
        result = client.try_resume(pending)
        assert result is None
    assert coordinator.jobs.get(pending.job_id).state == JobState.WAITING_FOR_APPROVAL
    assert coordinator.jobs.get(pending.job_id).approval_id == approval_id  # same approval, not re-requested
    assert len(coordinator.jobs._approval_engine.get(approval_id).audit_trail) == audit_len_before


def test_worker_client_resumes_and_executes_exactly_once_after_approval(coordinator, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability)
    coordinator.jobs.approve(pending.job_id, approver="kamara", authorized_executor="dev01")

    completed = client.try_resume(pending)
    assert completed is not None
    assert completed.state == JobState.SUCCEEDED
    assert len(completed.result.output["sha256"]) == 64  # the real handler actually ran, exactly once
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE  # released after completion

    # A second resume attempt on the same (now-finished) job is refused,
    # not a silent duplicate execution.
    with pytest.raises(WorkerClientError):
        client.try_resume(pending)


def test_worker_client_wrong_worker_cannot_resume(coordinator, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability, worker_id="dev01")
    coordinator.register_worker(
        worker_id="dev02", hostname="dev02.local", worker_version="0.1.0", platform="Darwin",
        architecture="arm64", capabilities=_caps(approval_required_capability), resource_limits={},
    )
    coordinator.heartbeat("dev02")
    coordinator.jobs.approve(pending.job_id, approver="kamara", authorized_executor="dev01")

    impostor_client = WorkerClient(worker_id="dev02", transport=transport, allowed_root=FIXTURES)
    with pytest.raises(WorkerClientError):
        impostor_client.try_resume(pending)
    assert coordinator.jobs.get(pending.job_id).state != JobState.SUCCEEDED  # nothing executed for the impostor

    # The legitimate worker can still resume normally afterward -- the
    # wrong-worker attempt did not corrupt the job.
    completed = client.try_resume(pending)
    assert completed.state == JobState.SUCCEEDED


def test_worker_client_denial_ends_safely_and_releases_worker(coordinator, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability)
    coordinator.deny_job(pending.job_id, approver="kamara", reason="not needed")

    assert coordinator.jobs.get(pending.job_id).state == JobState.FAILED
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE  # released, not stuck BUSY

    with pytest.raises(WorkerClientError):
        client.try_resume(pending)  # already terminal -- refused cleanly, not a crash


def test_worker_client_expiry_ends_safely_and_releases_worker(coordinator, clock, approval_required_capability):
    client, transport, pending = _register_and_park(coordinator, approval_required_capability)
    clock.advance(400)  # WorkerJobQueue's default approval_ttl_seconds=300 -- never approved in time

    with pytest.raises(WorkerClientError):
        client.try_resume(pending)

    assert coordinator.jobs.get(pending.job_id).state == JobState.FAILED
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE  # released, not stuck BUSY


def test_worker_client_approval_expires_after_being_approved_ends_safely(coordinator, clock, monkeypatch):
    """Distinct from test_worker_client_expiry_ends_safely_and_releases_worker
    above (expiry while still WAITING_FOR_APPROVAL, never approved): this
    covers a gap a third round of independent review found -- the
    approval IS granted (approve() moves the job WAITING_FOR_APPROVAL ->
    RUNNING), but then expires before try_resume() ever consumes it.
    resume()'s terminal-approval-ends-job-safely branch previously only
    checked for job state WAITING_FOR_APPROVAL before transitioning to
    FAILED; approve() had already moved the job past that into RUNNING,
    so this exact sequence left the job stuck RUNNING and its worker
    stuck BUSY forever -- nothing ever transitioned it to FAILED. Uses a
    call-counting handler (not just checking for an absent result) to
    prove the action was never invoked, not merely that no result was
    recorded."""
    synthetic = dict(SAFE_CAPABILITIES["hash_verify"])
    synthetic["capability_id"] = "synthetic_expire_after_approve"
    synthetic["authority_class"] = CapabilityClass.REVERSIBLE_WRITE
    monkeypatch.setitem(SAFE_CAPABILITIES, "synthetic_expire_after_approve", synthetic)

    call_count = []

    def _counting_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
        call_count.append(1)
        return {"ok": True}, "ran", []

    monkeypatch.setitem(_HANDLERS, "synthetic_expire_after_approve", _counting_handler)

    coordinator.register_worker(
        worker_id="dev01", hostname="dev01.local", worker_version="0.1.0", platform="Darwin",
        architecture="arm64", capabilities=_caps("synthetic_expire_after_approve"), resource_limits={},
    )
    coordinator.heartbeat("dev01")
    coordinator.submit_job(
        capability_id="synthetic_expire_after_approve", payload={"path": "sample_document.txt"},
        idempotency_key="expire-after-approve-1",
    )
    client = WorkerClient(worker_id="dev01", transport=LocalTransport(coordinator), allowed_root=FIXTURES)

    # 1. Job parks for approval.
    pending = client.poll_and_execute_once(["synthetic_expire_after_approve"])
    assert pending.state == JobState.WAITING_FOR_APPROVAL

    # 2. Approval is granted for the assigned worker.
    coordinator.jobs.approve(pending.job_id, approver="kamara", authorized_executor="dev01")
    assert coordinator.jobs.get(pending.job_id).state == JobState.RUNNING  # approved, not yet executed

    # 3. Approval expires before execution.
    clock.advance(400)  # WorkerJobQueue's default approval_ttl_seconds=300

    # 4. try_resume() executes no action.
    with pytest.raises(WorkerClientError):
        client.try_resume(pending)
    assert call_count == []

    # 5. Job ends FAILED.
    assert coordinator.jobs.get(pending.job_id).state == JobState.FAILED

    # 6. Worker returns AVAILABLE.
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE

    # 7. Another resume cannot execute.
    with pytest.raises(WorkerClientError):
        client.try_resume(pending)
    assert call_count == []


def test_worker_client_none_required_capability_flow_is_unchanged(coordinator):
    """Control case, through the real WorkerClient path this time (not
    just job_protocol directly, see test_approval_gate_none_required_...
    above): a NONE-authority capability executes immediately on the
    first poll, with no parking step at all."""
    coordinator.register_worker(
        worker_id="dev01", hostname="karmo-dev01.local", worker_version="0.1.0",
        platform="Darwin", architecture="arm64", capabilities=_caps("hash_verify"),
        resource_limits={"cpu": 8, "memory_mb": 8192},
    )
    coordinator.heartbeat("dev01")
    coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="none-flow-1",
    )
    client = WorkerClient(worker_id="dev01", transport=LocalTransport(coordinator), allowed_root=FIXTURES)

    result = client.poll_and_execute_once(["hash_verify"])
    assert result.state == JobState.SUCCEEDED
    assert len(result.result.output["sha256"]) == 64


# --- Scenario 18: path traversal attempt ---------------------------------------

def test_scenario_18_path_traversal_is_refused():
    with pytest.raises(PathTraversalError):
        resolve_within_sandbox(FIXTURES, "../../../etc/passwd")


def test_scenario_18_path_traversal_via_hash_verify_capability():
    with pytest.raises(PathTraversalError):
        run_capability("hash_verify", {"path": "../../../etc/passwd"}, timeout_seconds=30, allowed_root=FIXTURES)


# --- Scenario 19: oversized output -----------------------------------------------

def _huge_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    huge = "x" * (200 * 1024)  # well beyond MAX_OUTPUT_BYTES=64KB
    return {"n": len(huge)}, huge, []


register_handler("test_huge_probe", _huge_probe_handler)


def test_scenario_19_oversized_output_is_truncated():
    _, stdout_summary, _, _ = run_capability("test_huge_probe", {}, timeout_seconds=5)
    assert stdout_summary.endswith("...<truncated>")
    assert len(stdout_summary.encode("utf-8")) < 200 * 1024


# --- Scenario 20: arbitrary-shell attempt -----------------------------------------

def test_scenario_20_arbitrary_shell_capability_has_no_handler():
    assert "shell_anything" not in _HANDLERS
    with pytest.raises(SandboxError, match="no registered handler"):
        run_capability("shell_anything", {"cmd": "rm -rf /"}, timeout_seconds=5)


def test_scenario_20_forbidden_capability_id_rejected_at_the_manifest_layer():
    with pytest.raises(CapabilityManifestError, match="permanently excluded"):
        validate_capability_declaration({"capability_id": "shell_anything"})


# --- Scenario 21: worker marked disabled -----------------------------------------

def test_scenario_21_disabled_worker_is_refused(coordinator):
    _register(coordinator)
    coordinator.heartbeat("dev01")
    coordinator.disable_worker("dev01", reason="operator action")

    with pytest.raises(CoordinatorError, match="DISABLED"):
        coordinator.heartbeat("dev01")

    assert coordinator.poll_for_job("dev01", capabilities=["hash_verify"]) is None


# --- Scenario 22: job routed to correct eligible worker ---------------------------

def test_scenario_22_job_routed_to_correct_eligible_worker(coordinator):
    _register(coordinator, worker_id="dev01", capabilities=["hash_verify"])
    _register(coordinator, worker_id="dev02", hostname="karmo-dev02.local", capabilities=["pytest"])
    coordinator.heartbeat("dev01")
    coordinator.heartbeat("dev02")

    coordinator.submit_job(
        capability_id="pytest", payload={"test_dir": "sample_tests"}, idempotency_key="k-route-1",
    )

    assert coordinator.poll_for_job("dev01", capabilities=["hash_verify", "pytest"]) is None
    leased = coordinator.poll_for_job("dev02", capabilities=["hash_verify", "pytest"])
    assert leased is not None
    assert leased.capability_id == "pytest"
    assert leased.assigned_worker_id == "dev02"


# --- Scenario 23: no eligible worker available ------------------------------------

def test_scenario_23_no_eligible_worker_available(coordinator):
    coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-noworker-1",
    )
    assert coordinator.workers.eligible_workers("hash_verify") == []
    # No worker registered at all -- polling as an unknown worker_id is
    # itself refused, distinct from "registered but ineligible".
    with pytest.raises(WorkerRegistryError):
        coordinator.poll_for_job("nonexistent-worker", capabilities=["hash_verify"])


# --- Scenario 24: coordinator restart / recovery (in-memory prototype scope) -----

def test_scenario_24_fresh_coordinator_instance_has_no_leaked_state(coordinator, clock):
    """This prototype is explicitly in-memory only (Phase 7: 'coordinator
    and worker may run locally using loopback or in-memory/local
    transport'). There is no durable persistence to recover from yet --
    that gap is named, not hidden, in SECURITY_REVIEW.md and the future
    network integration plan. What IS provable here: no hidden global
    mutable state leaks between Coordinator instances (a real recovery
    implementation would need to rebuild from a persisted store, not from
    process memory that happens to still be warm)."""
    _register(coordinator)
    coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-restart-1",
    )
    assert len(coordinator.workers.all_workers()) == 1

    fresh = Coordinator(clock=clock)
    assert fresh.workers.all_workers() == []
    with pytest.raises(WorkerRegistryError):
        fresh.workers.get("dev01")


# =============================================================================
# Supporting tests: real capability handlers + full pull-based end-to-end flow.
# Not part of the numbered 24, but required to demonstrate the worker
# actually executes real work, not just protocol plumbing.
# =============================================================================

def test_end_to_end_pull_based_hash_verify(coordinator, clock):
    coordinator.register_worker(
        worker_id="dev01", hostname="karmo-dev01.local", worker_version="0.1.0",
        platform="Darwin", architecture="arm64", capabilities=_caps("hash_verify"),
        resource_limits={"cpu": 8, "memory_mb": 8192},
    )
    coordinator.heartbeat("dev01")
    coordinator.submit_job(
        capability_id="hash_verify", payload={"path": "sample_document.txt"}, idempotency_key="k-e2e-1",
    )

    transport = LocalTransport(coordinator)
    client = WorkerClient(worker_id="dev01", transport=transport, allowed_root=FIXTURES)
    result = client.poll_and_execute_once(["hash_verify"])

    assert result is not None
    assert result.state == JobState.SUCCEEDED
    assert len(result.result.output["sha256"]) == 64
    assert coordinator.workers.get("dev01").status == WorkerStatus.AVAILABLE  # returned to pool


def test_worker_client_no_eligible_work_returns_none(coordinator):
    coordinator.register_worker(
        worker_id="dev01", hostname="karmo-dev01.local", worker_version="0.1.0",
        platform="Darwin", architecture="arm64", capabilities=_caps("hash_verify"),
        resource_limits={"cpu": 8, "memory_mb": 8192},
    )
    coordinator.heartbeat("dev01")
    transport = LocalTransport(coordinator)
    client = WorkerClient(worker_id="dev01", transport=transport, allowed_root=FIXTURES)
    assert client.poll_and_execute_once(["hash_verify"]) is None


def test_capability_hash_verify_matches_real_sha256():
    output, summary, duration, evidence = run_capability(
        "hash_verify", {"path": "sample_document.txt"}, timeout_seconds=30, allowed_root=FIXTURES,
    )
    real = hashlib.sha256((FIXTURES / "sample_document.txt").read_bytes()).hexdigest()
    assert output["sha256"] == real


def test_capability_pytest_runs_real_subprocess_against_fixture():
    output, summary, duration, evidence = run_capability(
        "pytest", {"test_dir": "sample_tests"}, timeout_seconds=60, allowed_root=FIXTURES,
    )
    assert output["exit_code"] == 0
    assert "passed" in output["summary"]


def test_capability_static_analysis_reports_no_errors_on_valid_file():
    output, summary, duration, evidence = run_capability(
        "static_analysis", {"files": ["sample_tests/test_synthetic.py"]}, timeout_seconds=30, allowed_root=FIXTURES,
    )
    assert output["ok"] is True
    assert output["errors"] == []


def test_capability_repository_analysis_counts_fixture_files():
    output, summary, duration, evidence = run_capability(
        "repository_analysis", {"repo_path": "."}, timeout_seconds=30, allowed_root=FIXTURES,
    )
    assert output["file_count"] >= 2


def test_capability_resource_benchmark_is_bounded_even_for_huge_requested_iterations():
    output, summary, duration, evidence = run_capability(
        "resource_benchmark", {"iterations": 999_999_999}, timeout_seconds=30,
    )
    assert output["iterations"] == 5_000_000  # clamped, never caller-controlled unbounded


def test_capability_embedding_benchmark_is_bounded_even_for_huge_requested_vector_count():
    output, summary, duration, evidence = run_capability(
        "embedding_benchmark_test", {"vector_count": 999_999_999}, timeout_seconds=30,
    )
    assert output["vector_count"] == 10_000  # clamped


def test_capability_media_probe_reports_labeled_verified_status():
    output, summary, duration, evidence = run_capability("media_probe_test", {}, timeout_seconds=15)
    assert "metal_available" in output
    assert isinstance(output["metal_available"], bool)


def test_capability_local_model_probe_reports_truthful_model_status():
    # KARMO-DEV01 may legitimately gain approved local tooling over time
    # (e.g. Ollama was later installed for the separate KARMO AI Learning
    # Program); discovery tests must validate truthful detection rather
    # than freeze a historical machine package state.
    import resource_discovery

    output, summary, duration, evidence = run_capability("local_model_probe", {}, timeout_seconds=15)
    assert isinstance(output["mlx_installed"], bool)
    assert isinstance(output["ollama_installed"], bool)

    # Cross-check against a direct resource_discovery call on the same
    # host -- both must agree, since they're querying the same real state.
    acceleration = resource_discovery.discover_acceleration()
    assert output["mlx_installed"] == acceleration["mlx_installed"]
    assert output["ollama_installed"] == acceleration["ollama_installed"]


def test_capability_model_chat_calls_local_ollama_and_returns_response(monkeypatch):
    with _FakeOllamaServer(response_body=b'{"response": "the answer is 4"}') as server:
        monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", server.url)

        output, summary, duration, evidence = run_capability(
            "model_chat", {"model": "qwen3:8b", "prompt": "what is 2+2?"}, timeout_seconds=120,
        )

        assert output == {"response": "the answer is 4"}
        assert "qwen3:8b" in summary
        assert server.received_bodies == [
            {"model": "qwen3:8b", "prompt": "what is 2+2?", "stream": False}
        ]


def test_capability_model_chat_refuses_model_outside_allowed_set(monkeypatch):
    # Validation must reject before ever reaching the network call -- point
    # at a guaranteed-unused port so a regression that skips validation
    # fails fast on a real connection error instead of silently succeeding.
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")

    with pytest.raises(SandboxError, match="model not in allowed set"):
        run_capability("model_chat", {"model": "gpt-4", "prompt": "hi"}, timeout_seconds=120)


def test_capability_model_chat_refuses_empty_prompt(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")

    with pytest.raises(SandboxError, match="prompt must be non-empty"):
        run_capability("model_chat", {"model": "qwen3:8b", "prompt": "   "}, timeout_seconds=120)


def test_capability_model_chat_refuses_oversized_prompt(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")
    huge_prompt = "x" * (capabilities.MAX_MODEL_CHAT_PROMPT_CHARS + 1)

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability("model_chat", {"model": "qwen3:8b", "prompt": huge_prompt}, timeout_seconds=120)


def test_capability_model_chat_wraps_ollama_call_failure(monkeypatch):
    # A real connection-refused error (nothing listening on this port) --
    # the same failure mode the original mock simulated, now exercised
    # against the real urllib call the spawned child actually makes.
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")

    with pytest.raises(SandboxError, match="model_chat call to local Ollama failed"):
        run_capability("model_chat", {"model": "qwen3:8b", "prompt": "hi"}, timeout_seconds=120)


def test_capability_model_chat_manifest_matches_registered_allowed_models():
    manifest = SAFE_CAPABILITIES["model_chat"]
    assert manifest["authority_class"] == CapabilityClass.READ
    allowed = set(manifest["input_schema"]["properties"]["model"]["enum"])
    assert allowed == capabilities.__dict__["_ALLOWED_MODEL_CHAT_MODELS"]


# --- model_chat_tools (Model Router Phase D1) -------------------------------

def test_capability_model_chat_tools_calls_ollama_chat_and_returns_tool_call(monkeypatch):
    body = b'{"message": {"content": "", "tool_calls": [{"function": {"name": "list_tasks", "arguments": {}}}]}}'
    with _FakeOllamaServer(response_body=body) as server:
        monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", server.chat_url)

        output, summary, duration, evidence = run_capability(
            "model_chat_tools",
            {
                "model": "qwen3:8b",
                "messages": [{"role": "user", "content": "what tasks are open?"}],
                "tools": [{"type": "function", "function": {"name": "list_tasks", "parameters": {}}}],
            },
            timeout_seconds=120,
        )

        assert output["content"] == ""
        assert output["tool_calls"] == [{"function": {"name": "list_tasks", "arguments": {}}}]
        assert "qwen3:8b" in summary
        assert server.received_bodies == [
            {
                "model": "qwen3:8b",
                "messages": [{"role": "user", "content": "what tasks are open?"}],
                "stream": False,
                "think": False,
                "tools": [{"type": "function", "function": {"name": "list_tasks", "parameters": {}}}],
            }
        ]


def test_capability_model_chat_tools_works_without_tools_offered(monkeypatch):
    body = b'{"message": {"content": "hello there", "tool_calls": null}}'
    with _FakeOllamaServer(response_body=body) as server:
        monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", server.chat_url)

        output, summary, duration, evidence = run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}]},
            timeout_seconds=120,
        )

        assert output == {"content": "hello there", "tool_calls": None}
        assert "tools" not in server.received_bodies[0]


def test_capability_model_chat_tools_refuses_model_outside_allowed_set(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")

    with pytest.raises(SandboxError, match="model not in allowed set"):
        run_capability(
            "model_chat_tools",
            {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_refuses_empty_messages(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")

    with pytest.raises(SandboxError, match="messages must be a non-empty list"):
        run_capability("model_chat_tools", {"model": "qwen3:8b", "messages": []}, timeout_seconds=120)


def test_capability_model_chat_tools_refuses_too_many_messages(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")
    messages = [{"role": "user", "content": "hi"}] * (capabilities.__dict__["_MAX_MODEL_CHAT_TOOLS_MESSAGES"] + 1)

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability("model_chat_tools", {"model": "qwen3:8b", "messages": messages}, timeout_seconds=120)


def test_capability_model_chat_tools_refuses_invalid_message_role(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")

    with pytest.raises(SandboxError, match="invalid message role"):
        run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "admin", "content": "hi"}]},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_refuses_oversized_message_content(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")
    huge = "x" * (capabilities.__dict__["_MAX_MODEL_CHAT_TOOLS_MESSAGE_CHARS"] + 1)

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "user", "content": huge}]},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_refuses_non_list_tools(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")

    with pytest.raises(SandboxError, match="tools must be a list"):
        run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}], "tools": "not-a-list"},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_refuses_too_many_tools(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")
    tools = [{"type": "function", "function": {"name": "t"}}] * (
        capabilities.__dict__["_MAX_MODEL_CHAT_TOOLS_COUNT"] + 1
    )

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}], "tools": tools},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_wraps_ollama_call_failure(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_CHAT_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/chat")

    with pytest.raises(SandboxError, match="model_chat_tools call to local Ollama failed"):
        run_capability(
            "model_chat_tools",
            {"model": "qwen3:8b", "messages": [{"role": "user", "content": "hi"}]},
            timeout_seconds=120,
        )


def test_capability_model_chat_tools_manifest_is_additive_not_a_version_bump():
    """Model Router Phase D1: model_chat_tools must never disturb the
    already-deployed, already-configured model_chat 1.0.0 -- production
    worker configs declare that exact version today."""
    assert SAFE_CAPABILITIES["model_chat"]["version"] == "1.0.0"
    assert SAFE_CAPABILITIES["model_chat"]["input_schema"]["required"] == ["model", "prompt"]
    manifest = SAFE_CAPABILITIES["model_chat_tools"]
    assert manifest["authority_class"] == CapabilityClass.READ
    assert manifest["idempotent"] is False
    allowed = set(manifest["input_schema"]["properties"]["model"]["enum"])
    assert allowed == capabilities.__dict__["_ALLOWED_MODEL_CHAT_MODELS"]


def test_capability_vision_describe_calls_local_ollama_and_returns_answer(monkeypatch):
    image_b64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
    with _FakeOllamaServer(response_body=b'{"response": "a red square"}') as server:
        monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", server.url)

        output, summary, duration, evidence = run_capability(
            "vision_describe",
            {"model": "moondream", "question": "what color is this?", "image_base64": image_b64},
            timeout_seconds=60,
        )

        assert output == {"answer": "a red square"}
        assert "moondream" in summary
        assert server.received_bodies == [
            {
                "model": "moondream",
                "prompt": "what color is this?",
                "images": [image_b64],
                "stream": False,
            }
        ]


def test_capability_vision_describe_defaults_model_and_question(monkeypatch):
    image_b64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
    with _FakeOllamaServer(response_body=b'{"response": "a photo"}') as server:
        monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", server.url)

        output, summary, duration, evidence = run_capability(
            "vision_describe", {"image_base64": image_b64}, timeout_seconds=60,
        )

        assert output == {"answer": "a photo"}
        assert server.received_bodies[0]["model"] == "moondream"
        assert server.received_bodies[0]["prompt"] == "Describe this image."


def test_capability_vision_describe_refuses_model_outside_allowed_set(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")
    image_b64 = base64.b64encode(b"x").decode("ascii")

    with pytest.raises(SandboxError, match="model not in allowed set"):
        run_capability(
            "vision_describe",
            {"model": "qwen3:8b", "question": "what is this?", "image_base64": image_b64},
            timeout_seconds=60,
        )


def test_capability_vision_describe_refuses_empty_question(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")
    image_b64 = base64.b64encode(b"x").decode("ascii")

    with pytest.raises(SandboxError, match="question must be non-empty"):
        run_capability(
            "vision_describe", {"question": "   ", "image_base64": image_b64}, timeout_seconds=60,
        )


def test_capability_vision_describe_refuses_invalid_base64(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")

    with pytest.raises(SandboxError, match="not valid base64"):
        run_capability(
            "vision_describe", {"question": "what is this?", "image_base64": "not-valid-base64!!!"}, timeout_seconds=60,
        )


def test_capability_vision_describe_refuses_empty_decoded_image(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")

    with pytest.raises(SandboxError, match="empty"):
        run_capability(
            "vision_describe", {"question": "what is this?", "image_base64": ""}, timeout_seconds=60,
        )


def test_capability_vision_describe_refuses_oversized_image(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")
    huge_b64 = base64.b64encode(b"x" * (capabilities.MAX_VISION_IMAGE_BYTES + 1)).decode("ascii")

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability(
            "vision_describe", {"question": "what is this?", "image_base64": huge_b64}, timeout_seconds=60,
        )


def test_capability_vision_describe_wraps_ollama_call_failure(monkeypatch):
    monkeypatch.setenv("KARMO_OLLAMA_GENERATE_URL", f"http://127.0.0.1:{_unused_loopback_port()}/api/generate")
    image_b64 = base64.b64encode(b"x").decode("ascii")

    with pytest.raises(SandboxError, match="vision_describe call to local Ollama failed"):
        run_capability(
            "vision_describe", {"question": "what is this?", "image_base64": image_b64}, timeout_seconds=60,
        )


def test_capability_vision_describe_manifest_matches_registered_allowed_models():
    manifest = SAFE_CAPABILITIES["vision_describe"]
    assert manifest["authority_class"] == CapabilityClass.READ
    allowed = set(manifest["input_schema"]["properties"]["model"]["enum"])
    assert allowed == capabilities.__dict__["_ALLOWED_VISION_MODELS"]


_FAKE_WHISPER_SCRIPT = str(Path(__file__).resolve().parent / "fixtures" / "fake_whisper_transcribe_script.py")


def test_capability_transcribe_audio_calls_whisper_and_returns_text(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)
    audio_b64 = base64.b64encode(b"the quick brown fox").decode("ascii")

    output, summary, duration, evidence = run_capability(
        "transcribe_audio", {"model": "small", "audio_base64": audio_b64}, timeout_seconds=30,
    )

    assert output == {"text": "the quick brown fox"}
    assert "small" in summary


def test_capability_transcribe_audio_defaults_to_small_model(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)
    audio_b64 = base64.b64encode(b"hello").decode("ascii")

    output, summary, duration, evidence = run_capability(
        "transcribe_audio", {"audio_base64": audio_b64}, timeout_seconds=30,
    )

    assert output == {"text": "hello"}


def test_capability_transcribe_audio_refuses_model_outside_allowed_set(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)
    audio_b64 = base64.b64encode(b"x").decode("ascii")

    with pytest.raises(SandboxError, match="model not in allowed set"):
        run_capability(
            "transcribe_audio", {"model": "large", "audio_base64": audio_b64}, timeout_seconds=30,
        )


def test_capability_transcribe_audio_refuses_invalid_base64(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)

    with pytest.raises(SandboxError, match="not valid base64"):
        run_capability(
            "transcribe_audio", {"audio_base64": "not-valid-base64!!!"}, timeout_seconds=30,
        )


def test_capability_transcribe_audio_refuses_empty_audio(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)

    with pytest.raises(SandboxError, match="empty"):
        run_capability("transcribe_audio", {"audio_base64": ""}, timeout_seconds=30)


def test_capability_transcribe_audio_refuses_oversized_audio(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", _FAKE_WHISPER_SCRIPT)
    huge_b64 = base64.b64encode(b"x" * (capabilities.MAX_AUDIO_BYTES + 1)).decode("ascii")

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability("transcribe_audio", {"audio_base64": huge_b64}, timeout_seconds=30)


def test_capability_transcribe_audio_wraps_subprocess_failure(monkeypatch):
    monkeypatch.setenv("KARMO_WHISPER_PYTHON", sys.executable)
    monkeypatch.setenv("KARMO_WHISPER_SCRIPT", f"/nonexistent/{_unused_loopback_port()}.py")
    audio_b64 = base64.b64encode(b"x").decode("ascii")

    with pytest.raises(SandboxError, match="transcribe_audio subprocess failed"):
        run_capability("transcribe_audio", {"audio_base64": audio_b64}, timeout_seconds=30)


def test_capability_transcribe_audio_manifest_matches_registered_allowed_models():
    manifest = SAFE_CAPABILITIES["transcribe_audio"]
    assert manifest["authority_class"] == CapabilityClass.READ
    allowed = set(manifest["input_schema"]["properties"]["model"]["enum"])
    assert allowed == capabilities.__dict__["_ALLOWED_WHISPER_MODELS"]


_FAKE_PIPER_BINARY = str(Path(__file__).resolve().parent / "fixtures" / "fake_piper_binary")


def test_capability_synthesize_speech_calls_piper_and_returns_audio(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", _FAKE_PIPER_BINARY)
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")

    output, summary, duration, evidence = run_capability(
        "synthesize_speech", {"text": "hello there", "voice": "en_US-amy-medium"}, timeout_seconds=30,
    )

    assert base64.b64decode(output["audio_base64"]) == b"hello there"
    assert "en_US-amy-medium" in summary


def test_capability_synthesize_speech_defaults_to_amy_medium_voice(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", _FAKE_PIPER_BINARY)
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")

    output, summary, duration, evidence = run_capability(
        "synthesize_speech", {"text": "hi"}, timeout_seconds=30,
    )

    assert base64.b64decode(output["audio_base64"]) == b"hi"


def test_capability_synthesize_speech_refuses_voice_outside_allowed_set(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", _FAKE_PIPER_BINARY)
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")

    with pytest.raises(SandboxError, match="voice not in allowed set"):
        run_capability(
            "synthesize_speech", {"text": "hi", "voice": "en_GB-alan-low"}, timeout_seconds=30,
        )


def test_capability_synthesize_speech_refuses_empty_text(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", _FAKE_PIPER_BINARY)
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")

    with pytest.raises(SandboxError, match="text must be non-empty"):
        run_capability("synthesize_speech", {"text": "   "}, timeout_seconds=30)


def test_capability_synthesize_speech_refuses_oversized_text(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", _FAKE_PIPER_BINARY)
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")
    huge = "x" * (capabilities.MAX_SPEECH_TEXT_CHARS + 1)

    with pytest.raises(SandboxError, match="exceeds"):
        run_capability("synthesize_speech", {"text": huge}, timeout_seconds=30)


def test_capability_synthesize_speech_wraps_subprocess_failure(monkeypatch):
    monkeypatch.setenv("KARMO_PIPER_BINARY", f"/nonexistent/{_unused_loopback_port()}")
    monkeypatch.setenv("KARMO_PIPER_VOICE_MODEL", "/fake/voice.onnx")

    with pytest.raises(SandboxError, match="synthesize_speech subprocess failed"):
        run_capability("synthesize_speech", {"text": "hi"}, timeout_seconds=30)


def test_capability_synthesize_speech_manifest_matches_registered_allowed_voices():
    manifest = SAFE_CAPABILITIES["synthesize_speech"]
    assert manifest["authority_class"] == CapabilityClass.READ
    allowed = set(manifest["input_schema"]["properties"]["voice"]["enum"])
    assert allowed == capabilities.__dict__["_ALLOWED_PIPER_VOICES"]


def test_capability_document_processing_synthetic_chunking():
    output, summary, duration, evidence = run_capability(
        "document_processing_test", {"path": "sample_document.txt"}, timeout_seconds=30, allowed_root=FIXTURES,
    )
    assert output["chunk_count"] >= 1
    assert output["char_count"] > 0


# --- Spawn-context sandbox resilience -------------------------------------
#
# run_capability executes handlers via multiprocessing's "spawn" context
# (not "fork"), specifically to avoid a class of silent worker hang: a
# long-lived process makes many subprocess/network calls between jobs, and
# if any of those leave a background thread holding a lock at the exact
# instant a job triggers a fork, the forked child can inherit that lock
# permanently held -- deadlocking forever with no exception anywhere. spawn
# starts a clean interpreter instead, at the cost of requiring the handler,
# payload, and result to be picklable. These tests cover that boundary.

def test_unpicklable_handler_is_refused_cleanly_not_as_a_raw_pickling_error():
    def _closure_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
        return {"ok": True}, "should never run", []

    register_handler("test_unpicklable_probe", _closure_handler)
    with pytest.raises(SandboxError, match="could not be started under the sandbox's spawn context"):
        run_capability("test_unpicklable_probe", {}, timeout_seconds=5)


def _exits_before_sending_result_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    os._exit(1)  # hard process exit -- never reaches conn.send(), never a Python exception


register_handler("test_exits_before_result_probe", _exits_before_sending_result_handler)


def test_child_exit_before_sending_result_is_refused_not_hung():
    with pytest.raises(SandboxError, match="produced no result"):
        run_capability("test_exits_before_result_probe", {}, timeout_seconds=5)


def _echo_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    return {"echo": payload["value"]}, "echo", []


register_handler("test_echo_probe", _echo_probe_handler)


def test_repeated_execution_from_one_long_lived_caller_leaves_no_leaked_children():
    # Simulates the real production shape this bug came from: one process
    # calling run_capability many times over its lifetime, never restarting
    # between calls. Every call must succeed independently and leave no
    # child process or active multiprocessing bookkeeping behind for the
    # next one to trip over.
    for i in range(20):
        output, _, _, _ = run_capability("test_echo_probe", {"value": i}, timeout_seconds=5)
        assert output == {"echo": i}
        assert multiprocessing.active_children() == []


def test_repeated_timeouts_from_one_long_lived_caller_leave_no_leaked_children():
    for _ in range(5):
        with pytest.raises(SandboxError, match="exceeded its"):
            run_capability("test_hanging_probe", {"marker_path": "/dev/null/unused"}, timeout_seconds=0.1)
        assert multiprocessing.active_children() == []


def test_resource_discovery_full_report_runs_without_error():
    import resource_discovery
    report = resource_discovery.full_report()
    assert report["cpu"]["status"] == "VERIFIED"
    assert report["cpu"]["machine"] == "arm64"
    assert report["acceleration"]["apple_silicon"] is True

    # KARMO-DEV01 may legitimately gain approved local tooling over time
    # (e.g. Ollama was later installed for the separate KARMO AI Learning
    # Program); discovery tests must validate truthful detection rather
    # than freeze a historical machine package state.
    for tool in ("mlx", "ollama"):
        installed = report["acceleration"][f"{tool}_installed"]
        status = report["acceleration"][f"{tool}_status"]
        assert isinstance(installed, bool)
        assert status == ("VERIFIED" if installed else "NOT_INSTALLED")


def _speech_sized_output_probe_handler(payload, *, sandbox_root, allowed_root, timeout_seconds):
    return {"audio_base64": "U" * (MAX_RESULT_BYTES * 4)}, "speech", []


def test_synthesize_speech_may_return_more_than_the_default_result_cap(monkeypatch):
    """A spoken reply is far bigger than 64 KiB; its result goes back to
    Core in pieces, so only this capability gets the larger cap."""
    monkeypatch.setitem(_HANDLERS, "synthesize_speech", _speech_sized_output_probe_handler)
    output, _summary, _duration, _evidence = run_capability("synthesize_speech", {}, timeout_seconds=5)
    assert len(output["audio_base64"]) == MAX_RESULT_BYTES * 4
    with pytest.raises(SandboxError, match="oversized result"):
        run_capability("test_oversized_output_probe", {}, timeout_seconds=5)
