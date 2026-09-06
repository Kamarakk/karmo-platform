set +e
set +u
set +o pipefail

(
set -euo pipefail
umask 077

PREP_DIR="/home/lofason/karmo-ai/hardening/h0.1/implementation-prep-20260903T044818Z"
IMPLEMENTATION_DIR="/home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z"
WORK_APP="$IMPLEMENTATION_DIR/app"
VENV_PYTHON="/home/lofason/karmo-ai/core/venv/bin/python"
BUILD_DIR="$IMPLEMENTATION_DIR/h01-build-v1"
MIGRATIONS_DIR="$WORK_APP/migrations"
TESTS_DIR="$WORK_APP/tests"
BUILD_MANIFEST="$BUILD_DIR/MANIFEST-H01-ISOLATED-BUILD.sha256"
BUILD_MANIFEST_TMP="$BUILD_DIR/.MANIFEST-H01-ISOLATED-BUILD.sha256.tmp.$$"

trap 'rm -f -- "$BUILD_MANIFEST_TMP"' EXIT

case "$IMPLEMENTATION_DIR" in
  /home/lofason/karmo-ai/hardening/h0.1/implementation-20260903T044818Z) ;;
  *) printf 'STOP: unexpected H0.1 implementation directory.\n'; exit 1 ;;
esac

test -d "$WORK_APP"
test -x "$VENV_PYTHON"
test -f "$PREP_DIR/MANIFEST-H01-IMPLEMENTATION-PREP-RECOVERY.sha256"
test -f "$IMPLEMENTATION_DIR/ORIGIN-APP-HASHES.sha256"
test -f "$IMPLEMENTATION_DIR/ORIGIN-APP-INVENTORY.txt"
test ! -e "$BUILD_DIR"
test ! -e "$MIGRATIONS_DIR/001_h01_karmo_outbox.sql"
test ! -e "$WORK_APP/transactional_memory.py"
test ! -e "$WORK_APP/outbox.py"
test ! -e "$TESTS_DIR/test_h01_static_contract.py"
test ! -e "$TESTS_DIR/test_h01_pure_contract.py"
test ! -e "$WORK_APP/karmo.py.pre-h01-isolated-build"

(
  cd "$PREP_DIR"
  sha256sum -c MANIFEST-H01-IMPLEMENTATION-PREP-RECOVERY.sha256 >/dev/null
)
(
  cd "$WORK_APP"
  sha256sum -c "$IMPLEMENTATION_DIR/ORIGIN-APP-HASHES.sha256" >/dev/null
)

mkdir -p -- "$BUILD_DIR" "$MIGRATIONS_DIR" "$TESTS_DIR"

tee "$BUILD_DIR/SCOPE.txt" >/dev/null <<'SCOPE'
phase=H0.1 Transactional Outbox
activity=isolated implementation build and static/pure validation
workspace_only=YES
production_database_writes=NONE
production_schema_changes=NONE
production_qdrant_writes=NONE
live_application_changes=NONE
container_restarts=NONE
service_installation=NONE
runtime_integration_execution=NONE
next_gate=isolated database and Qdrant failure-matrix test harness
SCOPE

tee "$MIGRATIONS_DIR/001_h01_karmo_outbox.sql" >/dev/null <<'SQL'
-- KARMO H0.1 Transactional Outbox v1
-- Isolated build artifact only. Do not apply to production without the H0.1 cutover gate.

CREATE TABLE public.karmo_outbox (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id BIGINT NOT NULL,
    destination TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TIMESTAMPTZ,
    claimed_at TIMESTAMPTZ,
    claimed_by TEXT,
    claim_token UUID,
    processed_at TIMESTAMPTZ,
    last_error_code TEXT,
    last_error TEXT,

    CONSTRAINT karmo_outbox_conversation_fk
        FOREIGN KEY (aggregate_id)
        REFERENCES public.conversation_memory(id)
        ON DELETE RESTRICT,

    CONSTRAINT karmo_outbox_delivery_key
        UNIQUE (event_type, aggregate_type, aggregate_id, destination),

    CONSTRAINT karmo_outbox_status_check
        CHECK (status IN ('pending', 'processing', 'retry', 'delivered', 'dead')),

    CONSTRAINT karmo_outbox_attempt_count_check
        CHECK (attempt_count >= 0),

    CONSTRAINT karmo_outbox_nonempty_identity_check
        CHECK (
            length(event_type) BETWEEN 1 AND 128
            AND length(aggregate_type) BETWEEN 1 AND 128
            AND length(destination) BETWEEN 1 AND 256
        ),

    CONSTRAINT karmo_outbox_payload_object_check
        CHECK (jsonb_typeof(payload) = 'object'),

    CONSTRAINT karmo_outbox_claim_state_check
        CHECK (
            (status = 'processing' AND claimed_at IS NOT NULL AND claimed_by IS NOT NULL AND claim_token IS NOT NULL)
            OR
            (status <> 'processing' AND claimed_at IS NULL AND claimed_by IS NULL AND claim_token IS NULL)
        ),

    CONSTRAINT karmo_outbox_processed_state_check
        CHECK (
            (status = 'delivered' AND processed_at IS NOT NULL)
            OR
            (status <> 'delivered' AND processed_at IS NULL)
        )
);

CREATE INDEX karmo_outbox_ready_idx
    ON public.karmo_outbox (available_at, created_at, event_id)
    WHERE status IN ('pending', 'retry');

CREATE INDEX karmo_outbox_stale_claim_idx
    ON public.karmo_outbox (claimed_at, event_id)
    WHERE status = 'processing';
SQL

tee "$WORK_APP/transactional_memory.py" >/dev/null <<'PY'
"""H0.1 transactional conversation exchange producer.

This module is not wired to production until the H0.1 cutover gate.  It stores
the two conversation turns and one user-semantic outbox event atomically.
"""

import hashlib
import re
import uuid

from psycopg.types.json import Jsonb

from memory import get_connection


OUTBOX_NAMESPACE = uuid.UUID("30f34a29-d3d9-5222-8dfa-01d9ba8524d6")
OUTBOX_NAMESPACE_NAME = "urn:karmo:outbox:v1"
EVENT_TYPE = "semantic_memory.upsert.v1"
AGGREGATE_TYPE = "conversation_memory"
DESTINATION = "qdrant:karmo_semantic_memory"
PAYLOAD_SCHEMA_VERSION = 1
_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _schema_name(schema):
    if not isinstance(schema, str) or not _SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError("schema must be a simple PostgreSQL identifier")
    return schema


def event_id_for_user_id(user_id):
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")
    canonical_name = (
        f"conversation_memory:{user_id}:{EVENT_TYPE}:{DESTINATION}"
    )
    return uuid.uuid5(OUTBOX_NAMESPACE, canonical_name)


def content_sha256(content):
    if not isinstance(content, str):
        raise TypeError("content must be text")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_payload(prompt):
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "role": "user",
        "content_sha256": content_sha256(prompt),
    }


def remember_exchange(prompt, answer, *, schema="public", failure_stage=None):
    """Atomically persist a new exchange and one pending user-semantic event.

    ``failure_stage`` exists solely for isolated H0.1 transaction tests.  A
    raised exception remains inside the connection context, so all inserts roll
    back together.
    """

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty text")
    if not isinstance(answer, str):
        raise TypeError("answer must be text")

    schema = _schema_name(schema)
    conversation_table = f"{schema}.conversation_memory"
    outbox_table = f"{schema}.karmo_outbox"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {conversation_table} (role, content)
                VALUES (%s, %s)
                RETURNING id, created_at
                """,
                ("user", prompt),
            )
            user_id, _created_at = cur.fetchone()

            if failure_stage == "after_user_insert":
                raise RuntimeError("isolated failure after user insert")

            cur.execute(
                f"""
                INSERT INTO {conversation_table} (role, content)
                VALUES (%s, %s)
                RETURNING id
                """,
                ("assistant", answer),
            )
            cur.fetchone()

            if failure_stage == "after_assistant_insert":
                raise RuntimeError("isolated failure after assistant insert")

            event_id = event_id_for_user_id(user_id)
            cur.execute(
                f"""
                INSERT INTO {outbox_table} (
                    event_id,
                    event_type,
                    aggregate_type,
                    aggregate_id,
                    destination,
                    payload
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    EVENT_TYPE,
                    AGGREGATE_TYPE,
                    user_id,
                    DESTINATION,
                    Jsonb(build_payload(prompt)),
                ),
            )

            if failure_stage == "after_outbox_insert":
                raise RuntimeError("isolated failure after outbox insert")

    return str(event_id)
PY

tee "$WORK_APP/outbox.py" >/dev/null <<'PY'
"""H0.1 transactional-outbox relay.

The relay claims durable events in PostgreSQL, performs external embedding and
Qdrant work outside database locks, then fences state completion by event ID and
claim token.  It is built here for isolated validation only.
"""

import argparse
import hashlib
import math
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from memory import get_connection
# Kept local so importing this module for pure-contract tests does not create
# a semantic-memory client.  The real embedding function is loaded lazily only
# when a relay instance is constructed for an explicitly authorized run.
DEFAULT_COLLECTION_NAME = "karmo_semantic_memory"
DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
DEFAULT_VECTOR_SIZE = 768
from transactional_memory import (
    AGGREGATE_TYPE,
    DESTINATION,
    EVENT_TYPE,
    PAYLOAD_SCHEMA_VERSION,
    content_sha256,
    event_id_for_user_id,
)


DEFAULT_BATCH_SIZE = 10
DEFAULT_LEASE_SECONDS = 300
RETRY_INITIAL_SECONDS = 5
RETRY_CAP_SECONDS = 3600
_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PermanentDeliveryError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class TransientDeliveryError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: int
    destination: str
    payload: dict
    attempt_count: int
    created_at: datetime
    claim_token: str


def _schema_name(schema):
    if not isinstance(schema, str) or not _SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError("schema must be a simple PostgreSQL identifier")
    return schema


def retry_delay_seconds(attempt_count):
    exponent = min(max(attempt_count - 1, 0), 10)
    return min(RETRY_CAP_SECONDS, RETRY_INITIAL_SECONDS * (2 ** exponent))


def sanitized_error_code(error):
    if isinstance(error, (PermanentDeliveryError, TransientDeliveryError)):
        return error.code
    return "unexpected_" + type(error).__name__.lower()[:80]


class OutboxRelay:
    def __init__(
        self,
        *,
        worker_id,
        schema="public",
        collection_name=DEFAULT_COLLECTION_NAME,
        destination=DESTINATION,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        vector_size=DEFAULT_VECTOR_SIZE,
        client=None,
        embedding_function=None,
    ):
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if not isinstance(lease_seconds, int) or lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if not isinstance(vector_size, int) or vector_size <= 0:
            raise ValueError("vector_size must be positive")

        self.worker_id = worker_id
        self.schema = _schema_name(schema)
        self.collection_name = collection_name
        self.destination = destination
        self.lease_seconds = lease_seconds
        self.vector_size = vector_size
        self.client = client or QdrantClient(url=DEFAULT_QDRANT_URL)
        if embedding_function is None:
            from semantic_memory import get_embedding
            embedding_function = get_embedding
        self.embedding_function = embedding_function

    @property
    def _outbox_table(self):
        return f"{self.schema}.karmo_outbox"

    @property
    def _conversation_table(self):
        return f"{self.schema}.conversation_memory"

    def claim_batch(self, batch_size=DEFAULT_BATCH_SIZE):
        if not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")

        claim_token = uuid.uuid4()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH candidate AS (
                        SELECT event_id
                        FROM {self._outbox_table}
                        WHERE
                            (
                                status IN ('pending', 'retry')
                                AND available_at <= CURRENT_TIMESTAMP
                            )
                            OR
                            (
                                status = 'processing'
                                AND claimed_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                            )
                        ORDER BY available_at, created_at, event_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE {self._outbox_table} AS outbox
                    SET status = 'processing',
                        attempt_count = outbox.attempt_count + 1,
                        claimed_at = CURRENT_TIMESTAMP,
                        claimed_by = %s,
                        claim_token = %s,
                        last_attempt_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error_code = NULL,
                        last_error = NULL
                    FROM candidate
                    WHERE outbox.event_id = candidate.event_id
                    RETURNING outbox.event_id, outbox.event_type,
                        outbox.aggregate_type, outbox.aggregate_id,
                        outbox.destination, outbox.payload,
                        outbox.attempt_count, outbox.created_at,
                        outbox.claim_token
                    """,
                    (self.lease_seconds, batch_size, self.worker_id, claim_token),
                )
                rows = cur.fetchall()

        return [
            OutboxEvent(
                event_id=str(row[0]),
                event_type=row[1],
                aggregate_type=row[2],
                aggregate_id=row[3],
                destination=row[4],
                payload=row[5],
                attempt_count=row[6],
                created_at=row[7],
                claim_token=str(row[8]),
            )
            for row in rows
        ]

    def _authoritative_user_content(self, event):
        if event.event_type != EVENT_TYPE:
            raise PermanentDeliveryError("unsupported_event_type")
        if event.aggregate_type != AGGREGATE_TYPE:
            raise PermanentDeliveryError("unsupported_aggregate_type")
        if event.destination != self.destination:
            raise PermanentDeliveryError("unsupported_destination")
        if str(event_id_for_user_id(event.aggregate_id)) != event.event_id:
            raise PermanentDeliveryError("event_identity_mismatch")
        if not isinstance(event.payload, dict):
            raise PermanentDeliveryError("malformed_payload")
        if event.payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
            raise PermanentDeliveryError("unsupported_payload_schema")
        if event.payload.get("role") != "user":
            raise PermanentDeliveryError("payload_role_mismatch")

        expected_digest = event.payload.get("content_sha256")
        if not isinstance(expected_digest, str) or not _SHA256_PATTERN.fullmatch(expected_digest):
            raise PermanentDeliveryError("malformed_content_digest")

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, role, content, created_at
                    FROM {self._conversation_table}
                    WHERE id = %s
                    """,
                    (event.aggregate_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise PermanentDeliveryError("authoritative_row_missing")
        conversation_id, role, content, created_at = row
        if role != "user":
            raise PermanentDeliveryError("authoritative_role_mismatch")
        if not isinstance(content, str) or not content.strip():
            raise PermanentDeliveryError("authoritative_content_empty")
        if content_sha256(content) != expected_digest:
            raise PermanentDeliveryError("content_digest_mismatch")
        return conversation_id, content, created_at

    def _embedding(self, content):
        try:
            vector = self.embedding_function(content)
        except Exception as error:
            raise TransientDeliveryError("embedding_request_failed") from error

        if not isinstance(vector, (list, tuple)):
            raise PermanentDeliveryError("embedding_not_sequence")
        if len(vector) != self.vector_size:
            raise PermanentDeliveryError("embedding_dimension_mismatch")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
            raise PermanentDeliveryError("embedding_non_finite")
        return list(vector)

    def _upsert(self, event, conversation_id, content, created_at, vector):
        point = PointStruct(
            id=event.event_id,
            vector=vector,
            payload={
                "text": content,
                "role": "user",
                "event_id": event.event_id,
                "conversation_id": conversation_id,
                "event_type": event.event_type,
                "schema_version": PAYLOAD_SCHEMA_VERSION,
                "created_at": created_at.isoformat(),
            },
        )
        try:
            result = self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
                wait=True,
            )
        except Exception as error:
            raise TransientDeliveryError("qdrant_upsert_failed") from error

        if result is None or "completed" not in str(getattr(result, "status", "completed")).lower():
            raise TransientDeliveryError("qdrant_upsert_incomplete")

    def _finish(self, event, status, *, error_code=None, delay_seconds=None):
        if status not in {"delivered", "retry", "dead"}:
            raise ValueError("invalid finish status")
        if status == "retry" and delay_seconds is None:
            raise ValueError("retry requires delay_seconds")

        if status == "delivered":
            statement = f"""
                UPDATE {self._outbox_table}
                SET status = 'delivered', processed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP, claimed_at = NULL,
                    claimed_by = NULL, claim_token = NULL,
                    last_error_code = NULL, last_error = NULL
                WHERE event_id = %s AND claim_token = %s AND status = 'processing'
                RETURNING event_id
            """
            parameters = (event.event_id, event.claim_token)
        elif status == "retry":
            statement = f"""
                UPDATE {self._outbox_table}
                SET status = 'retry', available_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    updated_at = CURRENT_TIMESTAMP, claimed_at = NULL,
                    claimed_by = NULL, claim_token = NULL,
                    processed_at = NULL, last_error_code = %s, last_error = %s
                WHERE event_id = %s AND claim_token = %s AND status = 'processing'
                RETURNING event_id
            """
            parameters = (delay_seconds, error_code, error_code, event.event_id, event.claim_token)
        else:
            statement = f"""
                UPDATE {self._outbox_table}
                SET status = 'dead', updated_at = CURRENT_TIMESTAMP,
                    claimed_at = NULL, claimed_by = NULL, claim_token = NULL,
                    processed_at = NULL, last_error_code = %s, last_error = %s
                WHERE event_id = %s AND claim_token = %s AND status = 'processing'
                RETURNING event_id
            """
            parameters = (error_code, error_code, event.event_id, event.claim_token)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(statement, parameters)
                return cur.fetchone() is not None

    def process_once(self, batch_size=DEFAULT_BATCH_SIZE):
        outcomes = []
        for event in self.claim_batch(batch_size):
            try:
                conversation_id, content, created_at = self._authoritative_user_content(event)
                vector = self._embedding(content)
                self._upsert(event, conversation_id, content, created_at, vector)
            except PermanentDeliveryError as error:
                fenced = not self._finish(event, "dead", error_code=error.code)
                outcomes.append((event.event_id, "fenced" if fenced else "dead"))
            except Exception as error:
                code = sanitized_error_code(error)
                delay = retry_delay_seconds(event.attempt_count)
                fenced = not self._finish(event, "retry", error_code=code, delay_seconds=delay)
                outcomes.append((event.event_id, "fenced" if fenced else "retry"))
            else:
                fenced = not self._finish(event, "delivered")
                outcomes.append((event.event_id, "fenced" if fenced else "delivered"))
        return outcomes


def main():
    parser = argparse.ArgumentParser(description="KARMO H0.1 outbox relay")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    parser.add_argument("--worker-id", default=f"foreground-{uuid.uuid4()}")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()

    relay = OutboxRelay(worker_id=args.worker_id)
    if args.once:
        relay.process_once(args.batch_size)
        return
    while True:
        relay.process_once(args.batch_size)
        time.sleep(max(args.sleep_seconds, 0.1))


if __name__ == "__main__":
    main()
PY

python3 - "$WORK_APP/karmo.py" <<'PY_PATCH'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
original = path.read_text(encoding="utf-8")
updated = original

old_import = "from memory import initialize_memory, remember_turn, recent_turns\n"
new_import = "from memory import initialize_memory, recent_turns\nfrom transactional_memory import remember_exchange\n"
if old_import not in updated:
    raise SystemExit("expected memory import is missing")
updated = updated.replace(old_import, new_import, 1)

old_semantic_import = "    remember_semantic,\n"
if old_semantic_import not in updated:
    raise SystemExit("expected semantic import is missing")
updated = updated.replace(old_semantic_import, "", 1)

old_calls = '''        # PostgreSQL stores full conversation
        remember_turn("user", prompt)
        remember_turn("assistant", answer)

        # Semantic memory stores USER statements only.
        # Model answers and retrieved documents are NOT
        # automatically promoted into semantic memory.
        remember_semantic(
            prompt,
            role="user",
        )
'''
new_calls = '''        # H0.1 atomically stores the full exchange and queues only
        # the authoritative user prompt for asynchronous semantic delivery.
        remember_exchange(prompt, answer)
'''
if old_calls not in updated:
    raise SystemExit("expected v0.5 write block is missing")
updated = updated.replace(old_calls, new_calls, 1)

backup = path.with_name("karmo.py.pre-h01-isolated-build")
backup.write_text(original, encoding="utf-8")
path.write_text(updated, encoding="utf-8")
PY_PATCH

tee "$TESTS_DIR/test_h01_static_contract.py" >/dev/null <<'PY'
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def require(condition, message):
    if not condition:
        raise AssertionError(message)

migration = (ROOT / "migrations" / "001_h01_karmo_outbox.sql").read_text(encoding="utf-8")
producer = (ROOT / "transactional_memory.py").read_text(encoding="utf-8")
relay = (ROOT / "outbox.py").read_text(encoding="utf-8")
runtime = (ROOT / "karmo.py").read_text(encoding="utf-8")

for token in [
    "CREATE TABLE public.karmo_outbox",
    "FOREIGN KEY (aggregate_id)",
    "UNIQUE (event_type, aggregate_type, aggregate_id, destination)",
    "status IN ('pending', 'processing', 'retry', 'delivered', 'dead')",
    "karmo_outbox_ready_idx",
    "karmo_outbox_stale_claim_idx",
]:
    require(token in migration, f"migration missing: {token}")

for token in [
    'OUTBOX_NAMESPACE = uuid.UUID("30f34a29-d3d9-5222-8dfa-01d9ba8524d6")',
    'EVENT_TYPE = "semantic_memory.upsert.v1"',
    'DESTINATION = "qdrant:karmo_semantic_memory"',
    "INSERT INTO {conversation_table}",
    "INSERT INTO {outbox_table}",
    "RETURNING id, created_at",
    "Jsonb(build_payload(prompt))",
]:
    require(token in producer, f"producer missing: {token}")

for token in [
    "FOR UPDATE SKIP LOCKED",
    "claim_token",
    "wait=True",
    "content_digest_mismatch",
    "embedding_dimension_mismatch",
    "retry_delay_seconds",
    "CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')",
]:
    require(token in relay, f"relay missing: {token}")

require("remember_exchange(prompt, answer)" in runtime, "runtime does not use atomic exchange")
require("remember_turn(" not in runtime, "runtime still calls independent remember_turn")
require("remember_semantic(" not in runtime, "runtime still calls direct semantic memory")
print("h01_static_contract=PASS")
PY

tee "$TESTS_DIR/test_h01_pure_contract.py" >/dev/null <<'PY'
import hashlib
import uuid

from transactional_memory import (
    DESTINATION,
    EVENT_TYPE,
    OUTBOX_NAMESPACE,
    build_payload,
    content_sha256,
    event_id_for_user_id,
)
from outbox import retry_delay_seconds

user_id = 410
expected = uuid.uuid5(
    OUTBOX_NAMESPACE,
    f"conversation_memory:{user_id}:{EVENT_TYPE}:{DESTINATION}",
)
assert event_id_for_user_id(user_id) == expected
assert content_sha256("KARMO") == hashlib.sha256(b"KARMO").hexdigest()
assert build_payload("KARMO") == {
    "schema_version": 1,
    "role": "user",
    "content_sha256": hashlib.sha256(b"KARMO").hexdigest(),
}
assert retry_delay_seconds(1) == 5
assert retry_delay_seconds(2) == 10
assert retry_delay_seconds(99) == 3600
print("h01_pure_contract=PASS")
PY

"$VENV_PYTHON" -m py_compile \
  "$WORK_APP/transactional_memory.py" \
  "$WORK_APP/outbox.py" \
  "$WORK_APP/karmo.py" \
  "$TESTS_DIR/test_h01_static_contract.py" \
  "$TESTS_DIR/test_h01_pure_contract.py"

"$VENV_PYTHON" "$TESTS_DIR/test_h01_static_contract.py" > "$BUILD_DIR/static-contract.txt"
PYTHONPATH="$WORK_APP" "$VENV_PYTHON" "$TESTS_DIR/test_h01_pure_contract.py" > "$BUILD_DIR/pure-contract.txt"

grep -qx 'h01_static_contract=PASS' "$BUILD_DIR/static-contract.txt"
grep -qx 'h01_pure_contract=PASS' "$BUILD_DIR/pure-contract.txt"

{
  printf 'h01_isolated_build=PASS\n'
  printf 'recovery_manifest=PASS\n'
  printf 'workspace_origin_before_build=PASS\n'
  printf 'migration_artifact=migrations/001_h01_karmo_outbox.sql\n'
  printf 'producer_module=transactional_memory.py\n'
  printf 'relay_module=outbox.py\n'
  printf 'runtime_path=remember_exchange_only\n'
  printf 'static_contract=PASS\n'
  printf 'pure_contract=PASS\n'
  printf 'production_database_writes=0\n'
  printf 'production_schema_changes=0\n'
  printf 'production_qdrant_writes=0\n'
  printf 'live_application_changes=0\n'
  printf 'container_restarts=0\n'
  printf 'service_installations=0\n'
} > "$BUILD_DIR/build-summary.txt"

(
  cd "$IMPLEMENTATION_DIR"
  find . -type f \
    ! -name 'MANIFEST-H01-ISOLATED-BUILD.sha256' \
    ! -name '.MANIFEST-H01-ISOLATED-BUILD.sha256.tmp.*' \
    -print0 | sort -z | xargs -0 sha256sum
) > "$BUILD_MANIFEST_TMP"
mv -- "$BUILD_MANIFEST_TMP" "$BUILD_MANIFEST"

find "$BUILD_DIR" -type f -exec chmod 0444 {} +
chmod 0444 "$BUILD_MANIFEST"
(
  cd "$IMPLEMENTATION_DIR"
  sha256sum -c "$BUILD_MANIFEST" >/dev/null
)

printf 'H0.1 ISOLATED IMPLEMENTATION BUILD COMPLETE\n'
printf 'implementation_directory=%s\n' "$IMPLEMENTATION_DIR"
printf 'working_application=%s\n' "$WORK_APP"
printf 'build_directory=%s\n' "$BUILD_DIR"
sed -n '1,40p' "$BUILD_DIR/build-summary.txt"
printf 'build_manifest=%s\n' "$BUILD_MANIFEST"
printf 'build_manifest_check=PASS\n'
printf 'STOP HERE FOR H0.1 ISOLATED TEST-HARNESS REVIEW\n'

trap - EXIT
)
