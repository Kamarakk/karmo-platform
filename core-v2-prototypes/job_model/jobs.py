"""KARMO generic job/event execution model -- ISOLATED PROTOTYPE, MINIMAL.

Deliberately NOT a full scheduler (no timers, no background thread, no
persistence backend) -- per explicit instruction. Proves the state
machine and the idempotency/claim-fencing design decisions only, reusing
the H0.1 outbox relay's already-proven pattern
(test/h01/app/outbox.py: FOR UPDATE SKIP LOCKED + claim-token fencing)
rather than inventing a new one -- see
docs/architecture/KARMO_CURRENT_ARCHITECTURE_MAP.md's own "what can reuse
existing H0.1 outbox patterns" analysis.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL_STATES = {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED, JobState.TIMED_OUT}

# Explicit transition table -- anything not listed here is invalid and
# refused, mirroring the Approval Engine's own discipline.
VALID_TRANSITIONS = {
    JobState.QUEUED: {JobState.RUNNING, JobState.CANCELLED},
    JobState.RUNNING: {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.WAITING_FOR_APPROVAL,
        JobState.TIMED_OUT,
        JobState.CANCELLED,
    },
    JobState.WAITING_FOR_APPROVAL: {
        JobState.RUNNING,
        JobState.FAILED,  # approval denied -- a legitimate terminal outcome, not a fake resume-then-fail
        JobState.CANCELLED,
        JobState.TIMED_OUT,
    },
}


class JobStateError(RuntimeError):
    pass


def deterministic_job_id(job_type, idempotency_key):
    """Same shape as H0.1's event_id_for_user_id -- a stable UUID5 so a
    duplicate submission with the same idempotency_key always resolves
    to the same job_id, never a new row."""
    canonical_name = f"karmo-core-job:{job_type}:{idempotency_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_name))


@dataclass
class Job:
    job_id: str
    job_type: str
    idempotency_key: str
    state: JobState = JobState.QUEUED
    claim_token: str = None
    claimed_at: datetime = None
    attempt_count: int = 0
    progress: dict = field(default_factory=dict)
    result: object = None
    audit_trail: list = field(default_factory=list)

    def _record(self, to_state, now, note=""):
        self.audit_trail.append(
            {"timestamp": now.isoformat(), "from_state": self.state.value, "to_state": to_state.value, "note": note}
        )
        self.state = to_state


class JobStore:
    """In-memory prototype. A real implementation would extend
    public.karmo_outbox's own shape (or a sibling table with the same
    claim/lease columns) rather than a new persistence mechanism."""

    def __init__(self, *, clock=None, lease_seconds=300):
        self._jobs = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lease_seconds = lease_seconds

    def _now(self):
        return self._clock()

    def submit(self, job_type, idempotency_key):
        """Idempotent by construction: submitting the same
        (job_type, idempotency_key) twice returns the EXISTING job,
        never creates a duplicate -- directly mirroring
        document_ingest's document_exists() / registry_db.get_by_hash()
        pattern."""
        job_id = deterministic_job_id(job_type, idempotency_key)
        if job_id in self._jobs:
            return self._jobs[job_id]

        job = Job(job_id=job_id, job_type=job_type, idempotency_key=idempotency_key)
        job._record(JobState.QUEUED, self._now(), "submitted")
        self._jobs[job_id] = job
        return job

    def claim(self, job_id, *, worker_id):
        """FOR UPDATE SKIP LOCKED's in-memory analog: a job already
        claimed (RUNNING with a live, unexpired lease) cannot be claimed
        again; a stale lease (claimed_at + lease_seconds < now) can be
        reclaimed, exactly like the H0.1 relay's own stale-processing
        recovery. QUEUED and WAITING_FOR_APPROVAL (resuming after
        approval) are the two other states claim() may start from --
        both already permit a transition to RUNNING per
        VALID_TRANSITIONS."""
        job = self._require(job_id)

        if job.state == JobState.RUNNING:
            lease_expiry = job.claimed_at + timedelta(seconds=self._lease_seconds)
            if self._now() < lease_expiry:
                raise JobStateError(f"job {job_id} is already claimed and its lease has not expired")
            # stale lease: permitted to reclaim, fall through below.
        elif JobState.RUNNING not in VALID_TRANSITIONS.get(job.state, set()):
            raise JobStateError(f"cannot claim job in state {job.state.value}")

        job.claim_token = str(uuid.uuid4())
        job.claimed_at = self._now()
        job.attempt_count += 1
        job._record(JobState.RUNNING, self._now(), f"claimed by {worker_id}")
        return job

    def _require(self, job_id):
        job = self._jobs.get(job_id)
        if job is None:
            raise JobStateError(f"no such job: {job_id}")
        return job

    def transition(self, job_id, to_state, *, claim_token=None, note=""):
        job = self._require(job_id)

        if job.state == JobState.RUNNING and claim_token is not None and job.claim_token != claim_token:
            raise JobStateError(
                f"stale claim_token for job {job_id} -- a newer worker has already reclaimed it, "
                "this transition is fenced out (mirrors H0.1's claim-token fencing exactly)"
            )

        allowed = VALID_TRANSITIONS.get(job.state, set())
        if to_state not in allowed:
            raise JobStateError(f"invalid transition {job.state.value} -> {to_state.value}")

        job._record(to_state, self._now(), note)
        if to_state in (JobState.SUCCEEDED,):
            job.claim_token = None
        return job

    def cancel(self, job_id, *, reason=""):
        job = self._require(job_id)
        allowed = VALID_TRANSITIONS.get(job.state, set())
        if JobState.CANCELLED not in allowed:
            raise JobStateError(f"cannot cancel job in state {job.state.value}")
        job._record(JobState.CANCELLED, self._now(), reason or "cancelled")
        return job

    def get(self, job_id):
        return self._require(job_id)
