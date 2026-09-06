"""KARMO H0.1 isolated failure matrix: H01-T01 through H01-T18.

Exercises the frozen, verbatim-copied H0.1 artifacts (test/h01/app/
migrations/001_h01_karmo_outbox.sql, transactional_memory.py, outbox.py)
against a local, isolated, Docker-based PostgreSQL + Qdrant stack with
synthetic data only. No production host, credential, database, or Qdrant
collection is touched.

Each test is derived directly from a behavior the frozen design already
claims for itself (the failure_stage hooks in remember_exchange, the CHECK/
FK/UNIQUE constraints in the migration, and the claim/lease/fencing/retry
semantics documented in outbox.py) -- nothing here introduces a new
requirement or changes frozen scope.
"""

import threading
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from conftest import COLLECTION, deterministic_embedding

from outbox import OutboxRelay, PermanentDeliveryError, retry_delay_seconds
from transactional_memory import (
    DESTINATION,
    EVENT_TYPE,
    event_id_for_user_id,
    remember_exchange,
)


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
            (event_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# T01 -- migration structural contract
# ---------------------------------------------------------------------------
def test_h01_t01_migration_schema_applied(pg_conn):
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


# ---------------------------------------------------------------------------
# T02 -- remember_exchange happy path
# ---------------------------------------------------------------------------
def test_h01_t02_remember_exchange_happy_path(pg_conn):
    event_id = remember_exchange("hello karmo", "hi there")
    conv, outbox = _counts(pg_conn)
    assert conv == 2
    assert outbox == 1

    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, role, content FROM public.conversation_memory ORDER BY id")
        rows = cur.fetchall()
    assert rows[0][1:] == ("user", "hello karmo")
    assert rows[1][1:] == ("assistant", "hi there")
    user_id = rows[0][0]

    assert event_id == str(event_id_for_user_id(user_id))
    row = _outbox_row(pg_conn, event_id)
    status, attempt_count, *_rest = row
    assert status == "pending"
    assert attempt_count == 0


# ---------------------------------------------------------------------------
# T03/T04/T05 -- atomic rollback at each failure_stage hook
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "failure_stage",
    ["after_user_insert", "after_assistant_insert", "after_outbox_insert"],
)
def test_h01_t03_t04_t05_remember_exchange_rolls_back(pg_conn, failure_stage):
    with pytest.raises(RuntimeError):
        remember_exchange("prompt", "answer", failure_stage=failure_stage)
    conv, outbox = _counts(pg_conn)
    assert conv == 0
    assert outbox == 0


# ---------------------------------------------------------------------------
# T06 -- deterministic event identity + delivery-key uniqueness
# ---------------------------------------------------------------------------
def test_h01_t06_deterministic_identity_and_unique_delivery_key(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "same content twice")
    event_id_a = event_id_for_user_id(user_id)
    event_id_b = event_id_for_user_id(user_id)
    assert event_id_a == event_id_b

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


# ---------------------------------------------------------------------------
# T07 -- status check constraint
# ---------------------------------------------------------------------------
def test_h01_t07_status_check_rejects_invalid_status(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "x")
    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload, status)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb, 'bogus')
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )


# ---------------------------------------------------------------------------
# T08 -- claim-state check constraint
# ---------------------------------------------------------------------------
def test_h01_t08_claim_state_check(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "x")

    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload, status)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb, 'processing')
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )

    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload,
                     status, claimed_at, claimed_by, claim_token)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb,
                        'pending', CURRENT_TIMESTAMP, 'w1', gen_random_uuid())
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )


# ---------------------------------------------------------------------------
# T09 -- processed-state check constraint
# ---------------------------------------------------------------------------
def test_h01_t09_processed_state_check(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "x")

    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload, status)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb, 'delivered')
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )

    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload,
                     status, processed_at)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '{"a":1}'::jsonb,
                        'pending', CURRENT_TIMESTAMP)
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )


# ---------------------------------------------------------------------------
# T10 -- payload object check constraint
# ---------------------------------------------------------------------------
def test_h01_t10_payload_object_check(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "x")
    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
                VALUES (gen_random_uuid(), %s, 'conversation_memory', %s, %s, '[1,2,3]'::jsonb)
                """,
                (EVENT_TYPE, user_id, DESTINATION),
            )


# ---------------------------------------------------------------------------
# T11 -- nonempty/bounded identity check constraint
# ---------------------------------------------------------------------------
def test_h01_t11_nonempty_identity_check(pg_conn, insert_conversation):
    user_id = insert_conversation("user", "x")
    with pytest.raises(psycopg.errors.CheckViolation):
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.karmo_outbox
                    (event_id, event_type, aggregate_type, aggregate_id, destination, payload)
                VALUES (gen_random_uuid(), '', 'conversation_memory', %s, %s, '{"a":1}'::jsonb)
                """,
                (user_id, DESTINATION),
            )


# ---------------------------------------------------------------------------
# T12 -- FK + ON DELETE RESTRICT
# ---------------------------------------------------------------------------
def test_h01_t12_conversation_fk_enforced(pg_conn, insert_conversation):
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


# ---------------------------------------------------------------------------
# T13 -- concurrent claim_batch never double-claims (FOR UPDATE SKIP LOCKED)
# ---------------------------------------------------------------------------
def test_h01_t13_concurrent_claim_no_double_claim():
    for i in range(6):
        remember_exchange(f"prompt {i}", f"answer {i}")

    relay_a = OutboxRelay(worker_id="worker-a", client=object(), embedding_function=lambda c: [])
    relay_b = OutboxRelay(worker_id="worker-b", client=object(), embedding_function=lambda c: [])

    results = {}

    def _claim(name, relay):
        results[name] = relay.claim_batch(batch_size=10)

    t1 = threading.Thread(target=_claim, args=("a", relay_a))
    t2 = threading.Thread(target=_claim, args=("b", relay_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    ids_a = {e.event_id for e in results["a"]}
    ids_b = {e.event_id for e in results["b"]}
    assert ids_a.isdisjoint(ids_b)
    assert len(ids_a) + len(ids_b) == 6


# ---------------------------------------------------------------------------
# T14 -- stale claim reclaim past lease_seconds
# ---------------------------------------------------------------------------
def test_h01_t14_stale_claim_is_reclaimed(pg_conn):
    remember_exchange("stale prompt", "stale answer")

    relay_first = OutboxRelay(
        worker_id="first", lease_seconds=1, client=object(), embedding_function=lambda c: []
    )
    claimed = relay_first.claim_batch(batch_size=10)
    assert len(claimed) == 1
    event_id = claimed[0].event_id
    first_token = claimed[0].claim_token

    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), event_id),
        )

    relay_second = OutboxRelay(
        worker_id="second", lease_seconds=1, client=object(), embedding_function=lambda c: []
    )
    reclaimed = relay_second.claim_batch(batch_size=10)
    assert len(reclaimed) == 1
    assert reclaimed[0].event_id == event_id
    assert reclaimed[0].claim_token != first_token
    assert reclaimed[0].attempt_count == 2


# ---------------------------------------------------------------------------
# T15 -- process_once happy path: delivered + Qdrant point written
# ---------------------------------------------------------------------------
def test_h01_t15_process_once_delivers(pg_conn, qdrant_client):
    event_id = remember_exchange("deliver me", "ack")
    relay = OutboxRelay(
        worker_id="relay-1",
        client=qdrant_client,
        embedding_function=deterministic_embedding,
    )
    outcomes = relay.process_once()
    assert outcomes == [(event_id, "delivered")]

    status, attempt_count, available_at, claimed_at, claimed_by, claim_token, processed_at, err = (
        _outbox_row(pg_conn, event_id)
    )
    assert status == "delivered"
    assert processed_at is not None
    assert claimed_at is None and claimed_by is None and claim_token is None
    assert err is None

    point = qdrant_client.retrieve(collection_name=COLLECTION, ids=[event_id], with_payload=True)
    assert len(point) == 1
    assert point[0].payload["text"] == "deliver me"


# ---------------------------------------------------------------------------
# T16 -- permanent failure path: content digest mismatch -> dead, no point
# ---------------------------------------------------------------------------
def test_h01_t16_permanent_failure_marks_dead(pg_conn, qdrant_client):
    event_id = remember_exchange("original content", "ack")
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.conversation_memory SET content = %s WHERE role = 'user'",
            ("tampered content",),
        )

    relay = OutboxRelay(
        worker_id="relay-1",
        client=qdrant_client,
        embedding_function=deterministic_embedding,
    )
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
# T17 -- transient failure path: retry with backoff, not immediately reclaimable
# ---------------------------------------------------------------------------
def test_h01_t17_transient_failure_retries_with_backoff(pg_conn, qdrant_client):
    event_id = remember_exchange("flaky embedding", "ack")

    def _boom(content):
        raise RuntimeError("embedding service unavailable")

    relay = OutboxRelay(worker_id="relay-1", client=qdrant_client, embedding_function=_boom)
    outcomes = relay.process_once()
    assert outcomes == [(event_id, "retry")]

    status, attempt_count, available_at, claimed_at, claimed_by, claim_token, processed_at, err = (
        _outbox_row(pg_conn, event_id)
    )
    assert status == "retry"
    assert attempt_count == 1
    assert err == "embedding_request_failed"
    assert available_at > datetime.now(timezone.utc)

    expected_delay = retry_delay_seconds(attempt_count)
    assert expected_delay == 5

    relay_immediate = OutboxRelay(
        worker_id="relay-2", client=qdrant_client, embedding_function=deterministic_embedding
    )
    assert relay_immediate.claim_batch(batch_size=10) == []


# ---------------------------------------------------------------------------
# T18 -- fencing: a stale worker cannot complete after its claim was reclaimed
# ---------------------------------------------------------------------------
def test_h01_t18_stale_claim_token_is_fenced(pg_conn, qdrant_client):
    remember_exchange("fenced prompt", "ack")

    relay_first = OutboxRelay(
        worker_id="first", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding
    )
    claimed = relay_first.claim_batch(batch_size=10)
    assert len(claimed) == 1
    stale_event = claimed[0]

    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.karmo_outbox SET claimed_at = %s WHERE event_id = %s",
            (datetime.now(timezone.utc) - timedelta(seconds=10), stale_event.event_id),
        )

    relay_second = OutboxRelay(
        worker_id="second", lease_seconds=1, client=qdrant_client, embedding_function=deterministic_embedding
    )
    reclaimed = relay_second.claim_batch(batch_size=10)
    assert len(reclaimed) == 1
    assert reclaimed[0].claim_token != stale_event.claim_token

    fenced = not relay_first._finish(stale_event, "delivered")
    assert fenced is True

    status, *_rest = _outbox_row(pg_conn, stale_event.event_id)
    assert status == "processing"
