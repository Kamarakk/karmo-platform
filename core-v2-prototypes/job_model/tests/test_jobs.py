"""Deterministic identity, idempotency, crash/restart recovery (via
claim-token fencing), and state-machine validity -- the properties the
Core v2 architecture doc requires of any job/event model, proven against
this minimal prototype rather than a full scheduler."""

from datetime import datetime, timedelta, timezone

import pytest
from jobs import Job, JobState, JobStateError, JobStore, deterministic_job_id


class FakeClock:
    def __init__(self, start=None):
        self._now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self._now

    def advance(self, seconds):
        self._now += timedelta(seconds=seconds)


@pytest.fixture()
def clock():
    return FakeClock()


@pytest.fixture()
def store(clock):
    return JobStore(clock=clock, lease_seconds=60)


def test_deterministic_identity_is_stable_across_calls():
    id1 = deterministic_job_id("bloomboss.import", "order-42")
    id2 = deterministic_job_id("bloomboss.import", "order-42")
    assert id1 == id2


def test_deterministic_identity_differs_for_different_keys():
    id1 = deterministic_job_id("bloomboss.import", "order-42")
    id2 = deterministic_job_id("bloomboss.import", "order-43")
    assert id1 != id2


# Duplicate requests -> idempotency
def test_duplicate_submission_returns_the_same_job_not_a_new_one(store):
    job1 = store.submit("bloomboss.import", "order-42")
    job2 = store.submit("bloomboss.import", "order-42")

    assert job1.job_id == job2.job_id
    assert len(store._jobs) == 1


# Crashes / restart recovery via claim-token fencing
def test_claiming_an_already_leased_job_is_refused(store):
    job = store.submit("t", "k")
    store.claim(job.job_id, worker_id="worker-1")

    with pytest.raises(JobStateError, match="already claimed"):
        store.claim(job.job_id, worker_id="worker-2")


def test_stale_lease_can_be_reclaimed_by_a_new_worker(store, clock):
    job = store.submit("t", "k")
    store.claim(job.job_id, worker_id="worker-1")  # crashes, never finishes

    clock.advance(61)  # past the 60s lease

    reclaimed = store.claim(job.job_id, worker_id="worker-2")
    assert reclaimed.attempt_count == 2  # this is the SECOND attempt


def test_old_workers_claim_token_is_fenced_out_after_reclaim(store, clock):
    """Mirrors H01-T11's own scenario exactly: an old worker that
    eventually finishes AFTER its lease was reclaimed must not be able
    to overwrite the newer state."""
    job = store.submit("t", "k")
    first = store.claim(job.job_id, worker_id="worker-1")
    old_token = first.claim_token

    clock.advance(61)
    store.claim(job.job_id, worker_id="worker-2")  # reclaims, new token issued

    with pytest.raises(JobStateError, match="stale claim_token"):
        store.transition(job.job_id, JobState.SUCCEEDED, claim_token=old_token)


def test_current_workers_claim_token_succeeds(store):
    job = store.submit("t", "k")
    claimed = store.claim(job.job_id, worker_id="worker-1")

    finished = store.transition(job.job_id, JobState.SUCCEEDED, claim_token=claimed.claim_token)
    assert finished.state == JobState.SUCCEEDED


# State machine validity
@pytest.mark.parametrize(
    "from_state,to_state",
    [
        (JobState.QUEUED, JobState.RUNNING),
        (JobState.QUEUED, JobState.CANCELLED),
        (JobState.RUNNING, JobState.SUCCEEDED),
        (JobState.RUNNING, JobState.FAILED),
        (JobState.RUNNING, JobState.WAITING_FOR_APPROVAL),
        (JobState.RUNNING, JobState.TIMED_OUT),
        (JobState.RUNNING, JobState.CANCELLED),
        (JobState.WAITING_FOR_APPROVAL, JobState.RUNNING),
        (JobState.WAITING_FOR_APPROVAL, JobState.FAILED),
        (JobState.WAITING_FOR_APPROVAL, JobState.CANCELLED),
        (JobState.WAITING_FOR_APPROVAL, JobState.TIMED_OUT),
    ],
)
def test_valid_transitions_succeed(store, from_state, to_state):
    job = store.submit("t", f"k-{from_state}-{to_state}")
    job.state = from_state  # jump directly to the state under test

    result = store.transition(job.job_id, to_state)
    assert result.state == to_state


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        (JobState.SUCCEEDED, JobState.RUNNING),  # terminal -> anything
        (JobState.FAILED, JobState.SUCCEEDED),
        (JobState.CANCELLED, JobState.RUNNING),
        (JobState.TIMED_OUT, JobState.RUNNING),
        (JobState.QUEUED, JobState.SUCCEEDED),  # skipping RUNNING
        (JobState.QUEUED, JobState.WAITING_FOR_APPROVAL),  # must go through RUNNING first
    ],
)
def test_invalid_transitions_are_refused(store, from_state, to_state):
    job = store.submit("t", f"k-{from_state}-{to_state}")
    job.state = from_state

    with pytest.raises(JobStateError, match="invalid transition"):
        store.transition(job.job_id, to_state)


def test_progress_and_result_persist_on_the_job_record(store):
    job = store.submit("t", "k")
    claimed = store.claim(job.job_id, worker_id="w")
    claimed.progress = {"percent": 50}

    finished = store.transition(job.job_id, JobState.SUCCEEDED, claim_token=claimed.claim_token)
    finished.result = {"output": "synthetic"}

    reread = store.get(job.job_id)
    assert reread.progress == {"percent": 50}
    assert reread.result == {"output": "synthetic"}


def test_audit_trail_captures_full_lifecycle(store):
    job = store.submit("t", "k")
    claimed = store.claim(job.job_id, worker_id="w")
    store.transition(job.job_id, JobState.SUCCEEDED, claim_token=claimed.claim_token)

    final = store.get(job.job_id)
    transitions = [(e["from_state"], e["to_state"]) for e in final.audit_trail]
    assert transitions == [
        ("QUEUED", "QUEUED"),
        ("QUEUED", "RUNNING"),
        ("RUNNING", "SUCCEEDED"),
    ]
