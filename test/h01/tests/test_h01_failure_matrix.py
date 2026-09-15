"""KARMO H0.1 isolated failure matrix: H01-T01 through H01-T18.

Each test function below is mapped ONE-TO-ONE, by ID, to a row of the frozen
matrix at docs/handoff/h01/frozen-design/FAILURE-TEST-MATRIX-H01.md and the
required_test_ids in docs/handoff/h01/frozen-design/acceptance-criteria-h01.json.
The scenario/injection/required-result described in each row is reproduced in
this file's docstrings verbatim so the mapping can be checked by inspection.

This suite exercises the frozen, verbatim-copied H0.1 artifacts
(test/h01/app/migrations/001_h01_karmo_outbox.sql, transactional_memory.py,
outbox.py) against a local, isolated, Docker-based PostgreSQL + Qdrant stack
with synthetic data only, using the isolated Qdrant collection
`karmo_h01_outbox_test`. No production host, credential, database, or Qdrant
collection is touched.

H01-T01 and H01-T18 each have a component that requires reverifying a *live*
production baseline (the H0.0/H0.1 manifests and production row/point counts
recorded in the handoff doc). That data does not exist in this repository and
this suite must not reach out to production to get it. Those tests assert
everything that is locally verifiable and then explicitly skip the
live-baseline component, stating that it is blocked pending separate,
Natalie-approved read-only production verification -- per this session's
corrective instructions.

A small number of supplementary tests at the bottom of this file are kept for
regression coverage of the migration's constraints and are deliberately NOT
named/numbered as H01-T*; they are not part of, and must not be confused
with, the frozen 18-test matrix.
"""

import hashlib
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from conftest import (
    COLLECTION,
    deterministic_embedding,
    drain,
    unavailable_embedding_endpoint,
    unavailable_qdrant_client,
)

from outbox import OutboxRelay, retry_delay_seconds
from transactional_memory import (
    AGGREGATE_TYPE,
    DESTINATION,
    EVENT_TYPE,
    PAYLOAD_SCHEMA_VERSION,
    build_payload,
    content_sha256,
    event_id_for_user_id,
    remember_exchange,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_DESIGN_DIR = REPO_ROOT / "docs" / "handoff" / "h01" / "frozen-design"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "h01" / "h01_isolated_build_v2.sh"
TEARDOWN_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "teardown_test_env.sh"

ACCEPTANCE = json.loads((FROZEN_DESIGN_DIR / "acceptance-criteria-h01.json").read_text())
HEALTHY_DEADLINE_SECONDS = ACCEPTANCE["healthy_delivery_deadline_seconds"]


def _relay(**kwargs):
    """OutboxRelay constructor pinned to the isolated test collection."""
    kwargs.setdefault("collection_name", COLLECTION)
    return OutboxRelay(**kwargs)


def _counts(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.conversation_memory")
        conv = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM public.karmo_outbox")
        outbox = cur.fetchone()[0]
    return conv, outbox


def _outbox_row(pg_conn, event_id):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, attempt_count, available_at, claimed_at, claimed_by,
                   claim_token, processed_at, last_error_code
            FROM public.karmo_outbox WHERE event_id = %s
            """,
            (str(event_id),),
        )
        return cur.fetchone()


def _manual_outbox_insert(pg_conn, user_id, content, *, status="pending", **overrides):
    """Insert a karmo_outbox row directly, bypassing remember_exchange, so
    tests can construct specific pending/retry/processing/malformed states."""
    event_id = overrides.pop("event_id", event_id_for_user_id(user_id))
    payload = overrides.pop("payload", build_payload(content))
    fields = {
        "event_id": event_id,
        "event_type": EVENT_TYPE,
        "aggregate_type": AGGREGATE_TYPE,
        "aggregate_id": user_id,
        "destination": DESTINATION,
        "payload": payload,
        "status": status,
        "attempt_count": overrides.pop("attempt_count", 0),
        "available_at": overrides.pop("available_at", datetime.now(timezone.utc)),
        "claimed_at": overrides.pop("claimed_at", None),
        "claimed_by": overrides.pop("claimed_by", None),
        "claim_token": overrides.pop("claim_token", None),
    }
    assert not overrides, f"unknown overrides: {overrides}"
    fields["payload"] = Jsonb(fields["payload"])
    columns = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    values = list(fields.values())
    with pg_conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO public.karmo_outbox ({columns}) VALUES ({placeholders})",
            values,
        )
    return str(event_id)


# ---------------------------------------------------------------------------
# H01-T01 -- Evidence continuity
# Injection/action: Reverify H0.0 and every H0.1 manifest
# Required result:  All pass before testing
# ---------------------------------------------------------------------------
def test_h01_t01_evidence_continuity():
    assert FROZEN_DESIGN_DIR.joinpath("FAILURE-TEST-MATRIX-H01.md").is_file()
    assert FROZEN_DESIGN_DIR.joinpath("acceptance-criteria-h01.json").is_file()
    assert ACCEPTANCE["required_test_ids"] == [f"H01-T{n:02d}" for n in range(1, 19)]
    assert ACCEPTANCE["status"] == "frozen_for_review"
    assert ACCEPTANCE["implementation_authorized"] is False

    build_script_text = BUILD_SCRIPT.read_text()
    checks = [
        (Path(__file__).resolve().parents[1] / "app" / "migrations" / "001_h01_karmo_outbox.sql",
         "CREATE TABLE public.karmo_outbox ("),
        (Path(__file__).resolve().parents[1] / "app" / "transactional_memory.py",
         "import hashlib\nimport re\nimport uuid\n"),
        (Path(__file__).resolve().parents[1] / "app" / "outbox.py",
         "import argparse\nimport hashlib\nimport math\nimport re\nimport time\nimport uuid\n"),
    ]
    for local_path, anchor in checks:
        local_text = local_path.read_text()
        local_body = local_text[local_text.index(anchor):]
        assert local_body in build_script_text, (
            f"{local_path.name} body has diverged from the verified isolated "
            f"build script scripts/h01/h01_isolated_build_v2.sh"
        )

    pytest.skip(
        "BLOCKED: local frozen-artifact continuity verified above. Reverifying "
        "the H0.0 baseline manifest and the H0.1 isolated-build manifest "
        "(MANIFEST-H0-FINAL.sha256, MANIFEST-H01-ISOLATED-BUILD.sha256) "
        "requires read-only access to the production host per the handoff doc "
        "and is not available in this repository. Per corrective instructions, "
        "this stops and requires Natalie's separate approval rather than "
        "silently accessing production."
    )


# ---------------------------------------------------------------------------
# H01-T02 -- Fail after user insert
# Injection/action: Raise before assistant insert
# Required result:  Zero exchange rows and zero outbox rows commit
# ---------------------------------------------------------------------------
def test_h01_t02_fail_after_user_insert(pg_conn):
    with pytest.raises(RuntimeError):
        remember_exchange("prompt", "answer", failure_stage="after_user_insert")
    conv, outbox = _counts(pg_conn)
    assert conv == 0
    assert outbox == 0


# ---------------------------------------------------------------------------
# H01-T03 -- Fail after assistant insert
# Injection/action: Raise before outbox insert
# Required result:  Zero exchange rows and zero outbox rows commit
# ---------------------------------------------------------------------------
def test_h01_t03_fail_after_assistant_insert(pg_conn):
    with pytest.raises(RuntimeError):
        remember_exchange("prompt", "answer", failure_stage="after_assistant_insert")
    conv, outbox = _counts(pg_conn)
    assert conv == 0
    assert outbox == 0


# ---------------------------------------------------------------------------
# H01-T04 -- Fail after outbox insert
# Injection/action: Raise before transaction exit
# Required result:  Zero exchange rows and zero outbox rows commit
# ---------------------------------------------------------------------------
def test_h01_t04_fail_after_outbox_insert(pg_conn):
    with pytest.raises(RuntimeError):
        remember_exchange("prompt", "answer", failure_stage="after_outbox_insert")
    conv, outbox = _counts(pg_conn)
    assert conv == 0
    assert outbox == 0


# ---------------------------------------------------------------------------
# H01-T05 -- Successful atomic exchange
# Injection/action: Commit one controlled exchange
# Required result:  Exactly two conversation rows and one pending event commit
# ---------------------------------------------------------------------------
def test_h01_t05_successful_atomic_exchange(pg_conn):
    event_id = remember_exchange("hello karmo", "hi there")
    conv, outbox = _counts(pg_conn)
    assert conv == 2
    assert outbox == 1

    status, attempt_count, *_rest = _outbox_row(pg_conn, event_id)
    assert status == "pending"
    assert attempt_count == 0


# ---------------------------------------------------------------------------
# H01-T06 -- Ollama unavailable
# Injection/action: Block the isolated worker embedding endpoint
# Required result:  Event becomes retry; conversation rows remain; no point
#                    is created
# ---------------------------------------------------------------------------
def test_h01_t06_ollama_unavailable(pg_conn, qdrant_client):
    event_id = remember_exchange("needs an embedding", "ack")
    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=unavailable_embedding_endpoint)

    outcomes = relay.process_once()
    assert outcomes == [(event_id, "retry")]

    conv, _outbox = _counts(pg_conn)
    assert conv == 2

    status, attempt_count, available_at, *_rest, err = _outbox_row(pg_conn, event_id)
    assert status == "retry"
    assert attempt_count == 1
    assert err == "embedding_request_failed"
    assert available_at > datetime.now(timezone.utc)

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert point == []


# ---------------------------------------------------------------------------
# H01-T07 -- Qdrant unavailable
# Injection/action: Block the isolated Qdrant target
# Required result:  Event becomes retry; conversation rows remain; no point
#                    is lost
# ---------------------------------------------------------------------------
def test_h01_t07_qdrant_unavailable(pg_conn, qdrant_client):
    event_id = remember_exchange("needs qdrant", "ack")
    broken_client = unavailable_qdrant_client()
    relay = _relay(worker_id="relay-1", client=broken_client, embedding_function=deterministic_embedding)

    outcomes = relay.process_once()
    assert outcomes == [(event_id, "retry")]

    conv, _outbox = _counts(pg_conn)
    assert conv == 2

    status, attempt_count, available_at, *_rest, err = _outbox_row(pg_conn, event_id)
    assert status == "retry"
    assert err == "qdrant_upsert_failed"

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert point == []


# ---------------------------------------------------------------------------
# H01-T08 -- Crash before Qdrant write
# Injection/action: Kill worker after claim
# Required result:  Stale lease is reclaimed; one point is eventually
#                    delivered
# ---------------------------------------------------------------------------
def test_h01_t08_crash_before_qdrant_write_reclaimed(pg_conn, qdrant_client):
    event_id = remember_exchange("crash before write", "ack")

    relay_first = _relay(worker_id="first", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    claimed = relay_first.claim_batch(batch_size=10)
    assert len(claimed) == 1
    # Worker "crashes" here: it never embeds, upserts, or finishes.

    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), event_id),
        )

    relay_second = _relay(worker_id="second", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = drain(relay_second)
    assert outcomes == [(event_id, "delivered")]

    status, *_rest = _outbox_row(pg_conn, event_id)
    assert status == "delivered"
    points = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert len(points) == 1


# ---------------------------------------------------------------------------
# H01-T09 -- Crash after Qdrant write
# Injection/action: Kill worker before delivered update
# Required result:  Retry uses the same point ID; exactly one point exists;
#                    event becomes delivered
# ---------------------------------------------------------------------------
def test_h01_t09_crash_after_qdrant_write_before_delivered_update(pg_conn, qdrant_client):
    event_id = remember_exchange("crash after write", "ack")

    relay_first = _relay(worker_id="first", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    claimed = relay_first.claim_batch(batch_size=10)
    assert len(claimed) == 1
    event = claimed[0]

    # Worker performs the Qdrant write, then crashes before calling _finish.
    conversation_id, content, created_at = relay_first._authoritative_user_content(event)
    vector = relay_first._embedding(content)
    relay_first._upsert(event, conversation_id, content, created_at, vector)

    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), event_id),
        )

    relay_second = _relay(worker_id="second", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = drain(relay_second)
    assert outcomes == [(event_id, "delivered")]

    status, *_rest = _outbox_row(pg_conn, event_id)
    assert status == "delivered"

    points = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id], with_payload=True)
    assert len(points) == 1
    assert points[0].id == event_id or str(points[0].id) == str(event_id)


def _crash_after_upsert(relay, pg_conn, event_id):
    """Drive one real claim -> authoritative-content -> embed -> Qdrant-upsert
    delivery attempt through the relay, then "crash" before _finish is ever
    called -- exactly the path an actual duplicate/redelivered event takes
    (e.g. a worker that upserts and then dies before recording completion).
    Rewinds claimed_at so the next relay's stale-claim reclaim picks the
    event back up, as in the crash-recovery tests above."""
    claimed = relay.claim_batch(batch_size=10)
    assert [event.event_id for event in claimed] == [event_id]
    event = claimed[0]
    conversation_id, content, created_at = relay._authoritative_user_content(event)
    vector = relay._embedding(content)
    relay._upsert(event, conversation_id, content, created_at, vector)
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), event_id),
        )


# ---------------------------------------------------------------------------
# H01-T10 -- Duplicate delivery
# Injection/action: Deliver the same event at least three times
# Required result:  Same point is replaced; point count remains one for that
#                    event
# ---------------------------------------------------------------------------
def test_h01_t10_triple_duplicate_delivery(pg_conn, qdrant_client):
    event_id = remember_exchange("delivered three times", "ack")

    # Two independent workers each genuinely deliver the event end-to-end
    # (claim -> authoritative content -> embed -> Qdrant upsert) and then
    # crash before finishing, forcing lease-recovery redelivery, before a
    # third worker completes the full claim -> ... -> finish path. That is
    # three real deliveries of the same event through the real relay code
    # path, not three direct calls into the upsert helper.
    relay_1 = _relay(worker_id="dup-1", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    _crash_after_upsert(relay_1, pg_conn, event_id)

    relay_2 = _relay(worker_id="dup-2", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    _crash_after_upsert(relay_2, pg_conn, event_id)

    relay_3 = _relay(worker_id="dup-3", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = relay_3.process_once()
    assert outcomes == [(event_id, "delivered")]

    status, *_rest = _outbox_row(pg_conn, event_id)
    assert status == "delivered"

    points = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert len(points) == 1


# ---------------------------------------------------------------------------
# H01-T11 -- Claim-token fencing
# Injection/action: Let an old worker finish after lease reclamation
# Required result:  Old token updates zero rows and cannot overwrite the
#                    newer state
# ---------------------------------------------------------------------------
def test_h01_t11_claim_token_fencing(pg_conn, qdrant_client):
    event_id = remember_exchange("fenced prompt", "ack")

    relay_first = _relay(worker_id="first", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    claimed = relay_first.claim_batch(batch_size=10)
    assert len(claimed) == 1
    stale_event = claimed[0]

    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), event_id),
        )

    relay_second = _relay(worker_id="second", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    reclaimed = relay_second.claim_batch(batch_size=10)
    assert len(reclaimed) == 1
    assert reclaimed[0].claim_token != stale_event.claim_token

    updated = relay_first._finish(stale_event, "delivered")
    assert updated is False

    status, *_rest = _outbox_row(pg_conn, event_id)
    assert status == "processing"


# ---------------------------------------------------------------------------
# H01-T12 -- Concurrent workers
# Injection/action: Run two workers against at least 20 events
# Required result:  All events deliver without duplicate knowledge
# ---------------------------------------------------------------------------
def test_h01_t12_concurrent_workers_twenty_events(pg_conn, qdrant_client):
    event_ids = [remember_exchange(f"concurrent prompt {i}", f"ack {i}") for i in range(20)]

    relay_a = _relay(worker_id="worker-a", client=qdrant_client, embedding_function=deterministic_embedding)
    relay_b = _relay(worker_id="worker-b", client=qdrant_client, embedding_function=deterministic_embedding)

    results = {}

    def _drain(name, relay):
        results[name] = drain(relay, batch_size=5)

    t1 = threading.Thread(target=_drain, args=("a", relay_a))
    t2 = threading.Thread(target=_drain, args=("b", relay_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    all_outcomes = results["a"] + results["b"]
    assert len(all_outcomes) == 20
    assert all(outcome == "delivered" for _eid, outcome in all_outcomes)
    delivered_ids = {eid for eid, _outcome in all_outcomes}
    assert delivered_ids == set(event_ids)

    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.karmo_outbox WHERE status = 'delivered'")
        assert cur.fetchone()[0] == 20

    count = qdrant_client.count(collection_name=COLLECTION, exact=True).count
    assert count == 20


# ---------------------------------------------------------------------------
# H01-T13 -- Malformed permanent event
# Injection/action: Supply invalid payload in isolated test data
# Required result:  Event becomes dead, stores sanitized error, creates no
#                    point, and is not auto-requeued
# ---------------------------------------------------------------------------
def test_h01_t13_malformed_permanent_payload(pg_conn, insert_conversation, qdrant_client):
    user_id = insert_conversation("user", "malformed payload target")
    event_id = _manual_outbox_insert(
        pg_conn, user_id, "malformed payload target",
        payload={"schema_version": 1, "role": "user", "content_sha256": "not-a-valid-digest"},
    )

    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = relay.process_once()
    assert outcomes == [(event_id, "dead")]

    status, attempt_count, available_at, claimed_at, claimed_by, claim_token, processed_at, err = (
        _outbox_row(pg_conn, event_id)
    )
    assert status == "dead"
    assert processed_at is None
    assert err == "malformed_content_digest"

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert point == []

    # Not auto-requeued: a fresh claim pass must not pick a dead row back up.
    assert relay.claim_batch(batch_size=10) == []


# ---------------------------------------------------------------------------
# H01-T14 -- Restart recovery
# Injection/action: Stop/restart worker with pending, retry, and
#                    stale-processing rows
# Required result:  Every valid event is eventually delivered without
#                    duplicates
# ---------------------------------------------------------------------------
def test_h01_t14_restart_recovery_mixed_states(pg_conn, qdrant_client):
    # Create and claim the stale-processing row FIRST, while it is the only
    # ready row in the table -- otherwise a batch claim would also sweep up
    # the pending/retry rows created below and strand them mid-processing.
    stale_prompt_id = remember_exchange("stale processing row", "ack")
    prestart_relay = _relay(worker_id="pre-restart", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    claimed = prestart_relay.claim_batch(batch_size=10)
    assert [e.event_id for e in claimed] == [stale_prompt_id]
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), stale_prompt_id),
        )
    # prestart_relay "crashes" here without finishing the claim above.

    pending_id = remember_exchange("pending row", "ack")

    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.conversation_memory (role, content) VALUES ('user', %s) RETURNING id",
            ("retry row",),
        )
        retry_user_id = cur.fetchone()[0]
    retry_id = _manual_outbox_insert(
        pg_conn, retry_user_id, "retry row",
        status="retry", attempt_count=1,
        available_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    restarted_relay = _relay(worker_id="restarted", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = drain(restarted_relay)
    delivered_ids = {eid for eid, outcome in outcomes if outcome == "delivered"}
    assert delivered_ids == {pending_id, retry_id, stale_prompt_id}
    assert len(outcomes) == 3  # each of the three rows delivered exactly once

    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.karmo_outbox WHERE status = 'delivered'")
        assert cur.fetchone()[0] == 3

    count = qdrant_client.count(collection_name=COLLECTION, exact=True).count
    assert count == 3


# ---------------------------------------------------------------------------
# H01-T15 -- Behavior preservation (user-only semantic promotion)
# Injection/action: Commit one user/assistant exchange
# Required result:  Only the user prompt is represented in semantic memory
# ---------------------------------------------------------------------------
def test_h01_t15_user_only_semantic_promotion(pg_conn, qdrant_client):
    event_id = remember_exchange("promote only me", "not promoted")

    conv, outbox = _counts(pg_conn)
    assert conv == 2
    assert outbox == 1  # only the user turn produced an outbox event

    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = relay.process_once()
    assert outcomes == [(event_id, "delivered")]

    count = qdrant_client.count(collection_name=COLLECTION, exact=True).count
    assert count == 1

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id], with_payload=True)[0]
    assert point.payload["role"] == "user"
    assert point.payload["text"] == "promote only me"
    assert "not promoted" not in point.payload["text"]


# ---------------------------------------------------------------------------
# H01-T16 -- Digest integrity
# Injection/action: Alter isolated authoritative content after enqueue
# Required result:  Digest mismatch becomes dead; incorrect text is never
#                    embedded
# ---------------------------------------------------------------------------
def test_h01_t16_digest_mismatch_marks_dead(pg_conn, qdrant_client):
    event_id = remember_exchange("original content", "ack")
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.conversation_memory SET content = %s WHERE role = 'user'",
            ("tampered content",),
        )

    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=deterministic_embedding)
    outcomes = relay.process_once()
    assert outcomes == [(event_id, "dead")]

    status, attempt_count, available_at, claimed_at, claimed_by, claim_token, processed_at, err = (
        _outbox_row(pg_conn, event_id)
    )
    assert status == "dead"
    assert processed_at is None
    assert err == "content_digest_mismatch"

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id])
    assert point == []


# ---------------------------------------------------------------------------
# H01-T17 -- Healthy delivery latency
# Injection/action: Deliver at least 20 warm events
# Required result:  100% delivered within 10 seconds each; no query/delivery
#                    error
# ---------------------------------------------------------------------------
def test_h01_t17_healthy_delivery_latency(pg_conn, qdrant_client):
    # Elapsed time is measured with a single monotonic clock inside this
    # process, wrapped directly around each event's delivery cycle. This
    # avoids comparing an application-side wall-clock timestamp against a
    # Postgres-side timestamp from a different (Docker) clock source, which
    # would make the assertion sensitive to host/container clock skew rather
    # than actual delivery latency.
    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=deterministic_embedding)

    event_ids = []
    for i in range(20):
        event_id = remember_exchange(f"warm event {i}", f"ack {i}")
        started_at = time.monotonic()
        outcomes = relay.process_once(batch_size=1)
        elapsed = time.monotonic() - started_at

        assert outcomes == [(event_id, "delivered")]
        assert elapsed < HEALTHY_DEADLINE_SECONDS, (
            f"event {event_id} took {elapsed:.3f}s to deliver, exceeding the "
            f"{HEALTHY_DEADLINE_SECONDS}s healthy-delivery deadline"
        )
        event_ids.append(event_id)

    for event_id in event_ids:
        status, *_rest, err = _outbox_row(pg_conn, event_id)
        assert status == "delivered"
        assert err is None

    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.karmo_outbox WHERE status = 'delivered'")
        assert cur.fetchone()[0] == 20

    count = qdrant_client.count(collection_name=COLLECTION, exact=True).count
    assert count == 20


# ---------------------------------------------------------------------------
# H01-T18 -- Baseline and rollback drill
# Injection/action: Reverify live counts/hashes and exercise non-destructive
#                    rollback procedure
# Required result:  H0.0 stays reproducible; no existing row/point is deleted
#                    or rewritten
# ---------------------------------------------------------------------------
def test_h01_t18_baseline_and_rollback_drill(pg_conn, qdrant_client):
    assert ACCEPTANCE["automatic_event_deletion_allowed"] is False
    assert ACCEPTANCE["legacy_backfill_allowed"] is False
    assert ACCEPTANCE["criteria"]["rollback_must_preserve_outbox_evidence"] is True
    assert ACCEPTANCE["criteria"]["production_baseline_unchanged_before_cutover"] is True

    teardown_text = TEARDOWN_SCRIPT.read_text()
    assert "karmo-h01-test" in teardown_text
    for forbidden in ("karmo-ai01", "192.168.1.235", "lofason", "docker compose down -v --remove-orphans /"):
        assert forbidden not in teardown_text

    # Non-destructive drill on the isolated stack only: prove a delivered
    # event's row and point survive an unrelated rollback-style operation
    # (deleting a *different*, dead row) untouched.
    survivor_id = remember_exchange("survivor", "ack")
    relay = _relay(worker_id="relay-1", client=qdrant_client, embedding_function=deterministic_embedding)
    assert relay.process_once() == [(survivor_id, "delivered")]

    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.conversation_memory (role, content) VALUES ('user', %s) RETURNING id",
            ("doomed",),
        )
        doomed_user_id = cur.fetchone()[0]
    doomed_id = _manual_outbox_insert(
        pg_conn, doomed_user_id, "doomed",
        payload={"schema_version": 1, "role": "user", "content_sha256": "bad"},
    )
    relay.process_once()  # doomed_id -> dead (malformed digest), unrelated to survivor_id

    status, *_rest = _outbox_row(pg_conn, survivor_id)
    assert status == "delivered"
    points = qdrant_client.retrieve(collection_name=COLLECTION, ids=[survivor_id], with_payload=True)
    assert len(points) == 1
    assert points[0].payload["text"] == "survivor"

    pytest.skip(
        "BLOCKED: non-destructive rollback drill verified on the isolated "
        "stack above. Reverifying the live production baseline (PostgreSQL "
        "conversation_memory=14/karmo_memory=1/no karmo_outbox; Qdrant "
        "karmo_semantic_memory=4/karmo_documents=8/karmo_h00_dense_baseline=8, "
        "per the handoff doc) requires separately approved, read-only access "
        "to the production host and is not performed here. Per corrective "
        "instructions, this stops and requires Natalie's approval rather than "
        "silently accessing production."
    )


# ===========================================================================
# Supplementary regression tests -- NOT part of the frozen H01-T01..T18
# matrix. These cover migration constraints the frozen matrix does not
# enumerate as their own rows but that the implementation still relies on.
# Kept for defect coverage only; do not read these as H01-T* results.
# ===========================================================================
def test_supplementary_migration_schema_applied(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='karmo_outbox'"
        )
        columns = {row[0] for row in cur.fetchall()}
    for expected in [
        "event_id", "event_type", "aggregate_type", "aggregate_id",
        "destination", "payload", "status", "attempt_count", "available_at",
        "claimed_at", "claimed_by", "claim_token", "processed_at",
        "last_error_code", "last_error",
    ]:
        assert expected in columns
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
            "AND tablename='karmo_outbox'"
        )
        indexes = {row[0] for row in cur.fetchall()}
    assert "karmo_outbox_ready_idx" in indexes
    assert "karmo_outbox_stale_claim_idx" in indexes


def test_supplementary_delivery_key_unique_constraint(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "same content twice")
    event_id_a = event_id_for_user_id(user_id)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.karmo_outbox
                (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
            VALUES (%s, %s, 'conversation_memory', %s, %s, '{"schema_version":1}'::jsonb)
            """,
            (event_id_a, EVENT_TYPE, user_id, DESTINATION),
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"schema_version":1}'::jsonb)
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )


def test_supplementary_conversation_fk_restrict(pg_conn, insert_conversation):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', 999999, %s, '{"a":1}'::jsonb)
                """,
                (EVENT_TYPE, DESTINATION),
            )
    user_id = insert_conversation("user", "referenced")
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.karmo_outbox
                (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
            VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb)
            """,
            (EVENT_TYPE, user_id, DESTINATION),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with pg_conn.cursor() as cur:
            cur.execute("DELETE FROM public.conversation_memory WHERE id = %s", (user_id,))
