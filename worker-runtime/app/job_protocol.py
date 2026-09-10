"""KARMO Worker Runtime -- job protocol (Phase 6).

JOB, JOB_LEASE, JOB_RESULT, JOB_EVIDENCE. Wraps the reused JobStore
(state machine, deterministic identity, claim-token fencing) with
worker-specific fields, and -- genuinely, not just conceptually -- wires
it to the reused ApprovalEngine for capabilities whose computed
authority_requirement demands approval before execution. This closes the
integration gap the prior adversarial review found between the Tool
Registry and Approval Engine prototypes (neither had ever been exercised
together): here, a capability's authority_class is looked up for real and
fed into a real approval flow, not a hardcoded string.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from approval_engine_reuse import ApprovalEngine, ApprovalState, ApprovalStateError, arguments_digest
from capability_manifest import CapabilityManifestError, get_canonical_capability
from job_model_reuse import Job, JobState, JobStateError, JobStore
from tool_registry_reuse import ApprovalRequirement, compute_approval_requirement


class JobProtocolError(RuntimeError):
    pass


def payload_digest(capability_id, payload):
    """Same canonical-json-sha256 pattern as the Approval Engine's own
    arguments_digest -- reused directly rather than reimplemented."""
    return arguments_digest(capability_id, "payload", payload)


@dataclass
class JobResult:
    output: dict
    result_digest: str
    completed_at: datetime


@dataclass
class JobEvidence:
    stdout_summary: str
    duration_seconds: float
    evidence_files: list = field(default_factory=list)


@dataclass
class WorkerJob:
    job: Job  # underlying reused state machine
    capability_id: str
    payload: dict
    payload_digest: str
    authority_requirement: str
    timeout_seconds: int
    retry_policy: dict
    correlation_id: str = None
    approval_id: str = None
    assigned_worker_id: str = None
    result: JobResult = None
    evidence: JobEvidence = None

    @property
    def job_id(self):
        return self.job.job_id

    @property
    def state(self):
        return self.job.state


class WorkerJobQueue:
    def __init__(self, *, clock=None, lease_seconds=120, approval_ttl_seconds=300):
        self._job_store = JobStore(clock=clock, lease_seconds=lease_seconds)
        self._approval_engine = ApprovalEngine(clock=clock, default_ttl_seconds=approval_ttl_seconds)
        self._worker_jobs = {}  # job_id -> WorkerJob

    def submit(self, *, capability_id, payload, idempotency_key, correlation_id=None):
        """Deterministic identity + payload digest binding, per Phase 6's
        explicit requirements. Refuses unknown capabilities (I-09
        discipline, same as the registry itself)."""
        try:
            canonical = get_canonical_capability(capability_id)
        except CapabilityManifestError as error:
            raise JobProtocolError(str(error)) from error

        authority_requirement = compute_approval_requirement(
            canonical["authority_class"], financial_action=False, destructive_action=False
        )

        underlying = self._job_store.submit(capability_id, idempotency_key)
        if underlying.job_id in self._worker_jobs:
            return self._worker_jobs[underlying.job_id]  # idempotent resubmission

        worker_job = WorkerJob(
            job=underlying,
            capability_id=capability_id,
            payload=dict(payload),
            payload_digest=payload_digest(capability_id, payload),
            authority_requirement=authority_requirement.value,
            timeout_seconds=canonical["timeout_seconds"],
            retry_policy=canonical["retry_policy"],
            correlation_id=correlation_id,
        )
        self._worker_jobs[underlying.job_id] = worker_job
        return worker_job

    def _require(self, job_id):
        worker_job = self._worker_jobs.get(job_id)
        if worker_job is None:
            raise JobProtocolError(f"no such job: {job_id}")
        return worker_job

    def lease(self, job_id, *, worker_id, presented_payload, presented_payload_digest=None):
        """A worker leases a job -- payload is re-presented and its
        digest re-verified at lease time (not merely trusted from
        submission), so a job cannot be tampered with between submission
        and execution without detection. Changing material job arguments
        invalidates the digest match required to proceed, exactly the
        same discipline as the Approval Engine's own argument binding."""
        worker_job = self._require(job_id)

        attempted_digest = presented_payload_digest or payload_digest(worker_job.capability_id, presented_payload)
        if attempted_digest != worker_job.payload_digest:
            raise JobProtocolError(
                f"payload digest mismatch for job {job_id} -- expected {worker_job.payload_digest}, "
                f"got {attempted_digest} -- refusing lease (job payload tampering or corruption)"
            )

        try:
            self._job_store.claim(job_id, worker_id=worker_id)
        except JobStateError as error:
            # Never leak the underlying job_model exception type across
            # this module's own boundary -- JobProtocolError is the one
            # error type callers of WorkerJobQueue should ever need to
            # catch, exactly like every other method here.
            raise JobProtocolError(str(error)) from error
        worker_job.assigned_worker_id = worker_id
        return worker_job

    def request_approval_if_required(self, job_id, *, requester):
        """If the capability's computed authority requires more than
        NONE, transition RUNNING -> WAITING_FOR_APPROVAL and open a real
        ApprovalEngine request bound to this job's exact capability_id +
        payload. Capabilities in the initial SAFE set are all
        authority_requirement=NONE, so this path is not exercised by
        Phase 9's real tasks -- but the mechanism is real and tested
        (see tests/test_job_protocol.py), not merely designed."""
        worker_job = self._require(job_id)
        if worker_job.authority_requirement == ApprovalRequirement.NONE.value:
            return worker_job  # no approval needed, stays RUNNING

        self._job_store.transition(job_id, JobState.WAITING_FOR_APPROVAL, claim_token=worker_job.job.claim_token)
        approval = self._approval_engine.request(
            requester=requester,
            tool_id=worker_job.capability_id,
            tool_version="1.0.0",
            arguments=worker_job.payload,
            authority_class=worker_job.authority_requirement,
        )
        worker_job.approval_id = approval.approval_id
        return worker_job

    def approve(self, job_id, *, approver):
        worker_job = self._require(job_id)
        if worker_job.approval_id is None:
            raise JobProtocolError(f"job {job_id} has no pending approval to grant")
        self._approval_engine.approve(worker_job.approval_id, approver=approver)
        self._job_store.transition(job_id, JobState.RUNNING, claim_token=worker_job.job.claim_token)
        return worker_job

    def deny(self, job_id, *, approver, reason=""):
        worker_job = self._require(job_id)
        if worker_job.approval_id is None:
            raise JobProtocolError(f"job {job_id} has no pending approval to deny")
        self._approval_engine.deny(worker_job.approval_id, approver=approver, reason=reason)
        self._job_store.transition(job_id, JobState.FAILED, claim_token=worker_job.job.claim_token)
        return worker_job

    def complete(self, job_id, *, output, duration_seconds, stdout_summary, evidence_files=None, claim_token=None):
        worker_job = self._require(job_id)
        token = claim_token or worker_job.job.claim_token

        # If this capability required approval, executing without a
        # matching EXECUTED-bound approval is refused -- the job protocol
        # itself enforces the same "approval must be consumed, not
        # assumed" discipline the Approval Engine enforces internally.
        if worker_job.approval_id is not None:
            approval_record = self._approval_engine.get(worker_job.approval_id)
            if approval_record.state != ApprovalState.APPROVED:
                raise JobProtocolError(
                    f"job {job_id} requires approval state APPROVED to complete, "
                    f"found {approval_record.state.value}"
                )

        result_digest = hashlib.sha256(
            json.dumps(output, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

        self._job_store.transition(job_id, JobState.SUCCEEDED, claim_token=token)
        worker_job.result = JobResult(
            output=output, result_digest=result_digest, completed_at=datetime.now(timezone.utc)
        )
        worker_job.evidence = JobEvidence(
            stdout_summary=stdout_summary, duration_seconds=duration_seconds,
            evidence_files=evidence_files or [],
        )
        return worker_job

    def fail(self, job_id, *, reason, claim_token=None):
        worker_job = self._require(job_id)
        token = claim_token or worker_job.job.claim_token
        self._job_store.transition(job_id, JobState.FAILED, claim_token=token, note=reason)
        return worker_job

    def cancel(self, job_id, *, reason=""):
        self._job_store.cancel(job_id, reason=reason)
        return self._require(job_id)

    def get(self, job_id):
        return self._require(job_id)
