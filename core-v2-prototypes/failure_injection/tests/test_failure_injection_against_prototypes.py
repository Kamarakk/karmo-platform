"""Representative tests applying the failure-injection framework against
the Approval Engine and Job Model prototypes built earlier in this same
program -- proving the framework actually exercises real prototype code
paths, not just itself in isolation."""

from datetime import datetime, timezone

import pytest
from injectors import (
    DependencyRateLimited,
    FlakyCallable,
    MalformedResult,
    PartialWrite,
    PostgresUnavailable,
    ProcessCrash,
    QdrantUnavailable,
    RateLimiter,
    ToolTimeout,
    retry_with_backoff,
    validate_result_shape,
)

from engine import ApprovalEngine, ApprovalState, ApprovalStateError
from jobs import JobState, JobStateError, JobStore


TOOL_ID = "bloomboss.inventory.record_sale"
TOOL_VERSION = "1.0.0"
ARGS = {"order_id": "synthetic-1"}


@pytest.fixture()
def approval_engine():
    return ApprovalEngine(default_ttl_seconds=300)


@pytest.fixture()
def job_store():
    return JobStore(lease_seconds=60)


# --- PostgreSQL unavailable, propagated through a tool execution --------

def test_postgres_unavailable_during_execution_lands_in_failed(approval_engine):
    record = approval_engine.request(
        requester="kamara", tool_id=TOOL_ID, tool_version=TOOL_VERSION,
        arguments=ARGS, authority_class="REVERSIBLE_WRITE",
    )
    approval_engine.approve(record.approval_id, approver="kamara")

    def _executor():
        raise PostgresUnavailable("synthetic: connection refused")

    with pytest.raises(PostgresUnavailable):
        approval_engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION,
            arguments=ARGS, executor_identity="kamara", action=_executor,
        )

    assert approval_engine.get(record.approval_id).state == ApprovalState.FAILED


# --- Qdrant unavailable, with retry that eventually succeeds -------------

def test_qdrant_unavailable_then_recovers_within_retry_budget():
    calls = []

    def _upsert():
        calls.append(1)
        return "synthetic-point-id"

    flaky = FlakyCallable(_upsert, fail_on_calls=[1, 2], failure=QdrantUnavailable)

    result = retry_with_backoff(flaky, max_attempts=3, backoff_seconds=1, sleep=lambda s: None)

    assert result == "synthetic-point-id"
    assert flaky.call_count == 3  # failed twice, succeeded on the third


def test_qdrant_unavailable_exhausts_retry_budget_and_raises():
    def _always_fails():
        raise QdrantUnavailable("synthetic: still down")

    flaky = FlakyCallable(_always_fails, fail_on_calls=[1, 2, 3], failure=QdrantUnavailable)

    with pytest.raises(QdrantUnavailable):
        retry_with_backoff(flaky, max_attempts=3, backoff_seconds=1, sleep=lambda s: None)


# --- Tool timeout -----------------------------------------------------

def test_tool_timeout_during_execution_lands_in_failed(approval_engine):
    record = approval_engine.request(
        requester="kamara", tool_id=TOOL_ID, tool_version=TOOL_VERSION,
        arguments=ARGS, authority_class="REVERSIBLE_WRITE",
    )
    approval_engine.approve(record.approval_id, approver="kamara")

    def _executor():
        raise ToolTimeout("synthetic: exceeded timeout_seconds")

    with pytest.raises(ToolTimeout):
        approval_engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION,
            arguments=ARGS, executor_identity="kamara", action=_executor,
        )
    assert approval_engine.get(record.approval_id).state == ApprovalState.FAILED


# --- Malformed result ---------------------------------------------------

def test_malformed_result_is_detected_not_silently_accepted():
    good_result = {"status": "ok", "record_id": "synthetic-1"}
    validate_result_shape(good_result, required_keys=["status", "record_id"])  # no raise

    bad_result = {"status": "ok"}  # missing record_id
    with pytest.raises(MalformedResult, match="record_id"):
        validate_result_shape(bad_result, required_keys=["status", "record_id"])


def test_malformed_result_from_a_tool_executor_propagates_as_failure(approval_engine):
    record = approval_engine.request(
        requester="kamara", tool_id=TOOL_ID, tool_version=TOOL_VERSION,
        arguments=ARGS, authority_class="REVERSIBLE_WRITE",
    )
    approval_engine.approve(record.approval_id, approver="kamara")

    def _executor():
        return validate_result_shape({"status": "ok"}, required_keys=["status", "record_id"])

    with pytest.raises(MalformedResult):
        approval_engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION,
            arguments=ARGS, executor_identity="kamara", action=_executor,
        )
    assert approval_engine.get(record.approval_id).state == ApprovalState.FAILED


# --- Partial write -------------------------------------------------------

def test_partial_write_leaves_job_failed_not_succeeded(job_store):
    """Simulates a two-step operation (e.g. Qdrant upsert succeeds,
    registry write fails) -- the job must land in FAILED, never
    SUCCEEDED, even though step one genuinely completed."""
    job = job_store.submit("document.ingest", "doc-synthetic-1")
    claimed = job_store.claim(job.job_id, worker_id="w1")

    step_one_completed = {"qdrant_upsert": False}

    def _do_step_one():
        step_one_completed["qdrant_upsert"] = True

    def _do_step_two():
        raise PartialWrite("synthetic: registry write failed after Qdrant upsert succeeded")

    _do_step_one()
    with pytest.raises(PartialWrite):
        _do_step_two()

    finished = job_store.transition(job.job_id, JobState.FAILED, claim_token=claimed.claim_token)

    assert step_one_completed["qdrant_upsert"] is True  # step one's effect is real and not rolled back
    assert finished.state == JobState.FAILED  # but the job is honestly reported as failed


# --- Duplicate event -----------------------------------------------------

def test_duplicate_event_does_not_create_a_second_job(job_store):
    job1 = job_store.submit("t", "same-key")
    job2 = job_store.submit("t", "same-key")
    assert job1.job_id == job2.job_id


# --- Process crash (mid-claim, before completion) -------------------------

def test_process_crash_mid_job_is_recovered_by_lease_expiry(job_store):
    job = job_store.submit("t", "k")
    claimed = job_store.claim(job.job_id, worker_id="worker-1")
    # worker-1 "crashes" here -- never transitions the job further.

    from datetime import timedelta
    lease_expired_at = claimed.claimed_at + timedelta(seconds=61)
    job_store._clock = lambda: lease_expired_at

    reclaimed = job_store.claim(job.job_id, worker_id="worker-2")
    assert reclaimed.attempt_count == 2


# --- Expired approval (already covered in approval_engine's own suite;
# proven again here specifically through the failure-injection framework's
# own vocabulary, for completeness of this program's required category
# list) ---

def test_approval_expired_category_matches_engine_behavior():
    from datetime import timedelta

    clock_state = {"now": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    engine = ApprovalEngine(clock=lambda: clock_state["now"], default_ttl_seconds=30)

    record = engine.request(
        requester="kamara", tool_id=TOOL_ID, tool_version=TOOL_VERSION,
        arguments=ARGS, authority_class="REVERSIBLE_WRITE",
    )
    engine.approve(record.approval_id, approver="kamara")
    clock_state["now"] += timedelta(seconds=31)

    with pytest.raises(ApprovalStateError):
        engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION,
            arguments=ARGS, executor_identity="kamara", action=lambda: pytest.fail("must never be called"),
        )


# --- Permission denial ---------------------------------------------------

def test_permission_denial_is_a_distinct_failure_from_approval_denial(approval_engine):
    """A DENIED approval (a human said no) and a PermissionDenied
    failure (the tool itself refused at execution time, e.g. a
    scope-mismatch the dispatcher would catch) are different things --
    this test keeps them distinct rather than conflating "not approved"
    with "not permitted"."""
    record = approval_engine.request(
        requester="kamara", tool_id=TOOL_ID, tool_version=TOOL_VERSION,
        arguments=ARGS, authority_class="REVERSIBLE_WRITE",
    )
    approval_engine.approve(record.approval_id, approver="kamara")

    from injectors import PermissionDenied

    def _executor():
        raise PermissionDenied("synthetic: tool's own scope check refused this call")

    with pytest.raises(PermissionDenied):
        approval_engine.execute(
            record.approval_id, tool_id=TOOL_ID, tool_version=TOOL_VERSION,
            arguments=ARGS, executor_identity="kamara", action=_executor,
        )
    assert approval_engine.get(record.approval_id).state == ApprovalState.FAILED


# --- Dependency rate limit -------------------------------------------------

def test_dependency_rate_limit_trips_after_threshold():
    limiter = RateLimiter(limit=2, window=10)

    limiter.check(now=0)
    limiter.check(now=1)
    with pytest.raises(DependencyRateLimited):
        limiter.check(now=2)


def test_dependency_rate_limit_resets_after_window_elapses():
    limiter = RateLimiter(limit=2, window=10)

    limiter.check(now=0)
    limiter.check(now=1)
    limiter.check(now=15)  # window has elapsed since now=0
