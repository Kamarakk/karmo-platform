"""H0.4 acceptance workflow: one concise isolated suite, not overlapping
test suites, per the frozen H0.4 testing instruction.

Runs against the real isolated Postgres + Qdrant stack (h04/docker-compose.yml).
Each test demonstrates detection of exactly one frozen corruption/inconsistency
scenario, plus the auditor's report-only guarantee and the backup ->
corruption -> restore -> integrity-verification recovery workflow.
"""

import uuid

import auditor
import recovery
import registry_db
from qdrant_client.models import PointStruct

from conftest import (
    COLLECTION_NAME,
    DEFAULT_CHUNKER_VERSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PIPELINE_VERSION,
    PG_CONTAINER,
    PG_DB,
    PG_PASSWORD,
    PG_USER,
    VECTOR_SIZE,
    _deterministic_embedding,
)


def test_healthy_consistent_document_has_no_findings(make_document, qdrant_client, pg_conn):
    make_document("healthy_policy.md")

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    assert findings == []


def test_missing_archived_file_detected(make_document, qdrant_client, pg_conn):
    doc = make_document("missing_file_policy.md")
    doc["archive_path"].unlink()

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "MISSING_ARCHIVED_FILE"]
    assert len(matches) == 1
    assert matches[0]["document_hash"] == doc["document_hash"]


def test_archived_file_hash_mismatch_detected(make_document, qdrant_client, pg_conn):
    doc = make_document("tampered_policy.md")
    doc["archive_path"].write_text("this content was silently changed on disk", encoding="utf-8")

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "ARCHIVED_FILE_HASH_MISMATCH"]
    assert len(matches) == 1
    assert matches[0]["expected_sha256"] == doc["document_hash"]
    assert matches[0]["actual_sha256"] != doc["document_hash"]


def test_missing_qdrant_vector_detected(make_document, qdrant_client, pg_conn):
    doc = make_document("thin_policy.md", num_chunks=3)
    qdrant_client.delete(collection_name=COLLECTION_NAME, points_selector=[doc["point_ids"][0]])

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "MISSING_VECTOR"]
    assert len(matches) == 1
    assert matches[0]["chunk_number"] == 1
    assert matches[0]["document_hash"] == doc["document_hash"]


def test_orphan_qdrant_vector_detected(make_document, qdrant_client, pg_conn):
    make_document("registered_policy.md")
    orphan_hash = "0" * 64
    orphan_id = str(uuid.uuid4())
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=orphan_id,
                vector=_deterministic_embedding("orphan chunk, no registry row"),
                payload={"document_hash": orphan_hash, "document_id": "ghost.md", "chunk_number": 1},
            )
        ],
    )

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "ORPHAN_VECTOR"]
    assert len(matches) == 1
    assert matches[0]["point_id"] == orphan_id
    assert matches[0]["document_hash"] == orphan_hash


def test_incorrect_expected_chunk_count_detected(make_document, qdrant_client, pg_conn):
    doc = make_document("undercount_policy.md", num_chunks=3)
    extra_text = f"{doc['document_hash']} extra chunk beyond expected_chunk_count"
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=_deterministic_embedding(extra_text),
                payload={
                    "document_hash": doc["document_hash"],
                    "document_id": doc["document_id"],
                    "chunk_number": 4,
                    "is_active": True,
                    "pipeline_version": doc["pipeline_version"],
                    "embedding_model": doc["embedding_model"],
                    "chunker_version": doc["chunker_version"],
                },
            )
        ],
    )

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "INCORRECT_EXPECTED_CHUNK_COUNT"]
    assert len(matches) == 1
    assert matches[0]["expected_chunk_count"] == 3
    assert matches[0]["actual_chunk_count"] == 4
    assert matches[0]["extra_chunk_numbers"] == [4]
    assert not any(f["type"] == "MISSING_VECTOR" for f in findings)


def test_multiple_active_versions_detected(make_document, qdrant_client, pg_conn):
    v1 = make_document("relapsed_policy.md", document_version=1, is_active=True)
    v2 = make_document("relapsed_policy.md", document_version=2, is_active=True)

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "MULTIPLE_ACTIVE_VERSIONS"]
    assert len(matches) == 1
    assert matches[0]["document_id"] == "relapsed_policy.md"
    assert sorted(matches[0]["active_hashes"]) == sorted([v1["document_hash"], v2["document_hash"]])


def test_provenance_version_mismatch_detected(make_document, qdrant_client, pg_conn):
    doc = make_document("reprocessed_policy.md")
    qdrant_client.set_payload(
        collection_name=COLLECTION_NAME,
        payload={"pipeline_version": "legacy-pipeline-v0"},
        points=[doc["point_ids"][0]],
    )

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    matches = [f for f in findings if f["type"] == "PROVENANCE_MISMATCH"]
    assert len(matches) == 1
    assert matches[0]["field"] == "pipeline_version"
    assert matches[0]["expected"] == DEFAULT_PIPELINE_VERSION
    assert matches[0]["actual"] == "legacy-pipeline-v0"


def test_auditor_is_report_only(make_document, qdrant_client, pg_conn, monkeypatch):
    """The auditor must detect a real inconsistency using only read APIs --
    proven here by making every mutating API on both stores raise if
    called, then asserting the audit still runs to completion and still
    reports the finding."""
    doc = make_document("guarded_policy.md", num_chunks=3)
    qdrant_client.delete(collection_name=COLLECTION_NAME, points_selector=[doc["point_ids"][0]])

    def _forbidden(*args, **kwargs):
        raise AssertionError("auditor must not call Qdrant write APIs")

    monkeypatch.setattr(qdrant_client, "upsert", _forbidden)
    monkeypatch.setattr(qdrant_client, "set_payload", _forbidden)
    monkeypatch.setattr(qdrant_client, "delete", _forbidden)
    monkeypatch.setattr(qdrant_client, "delete_collection", _forbidden)

    original_cursor = pg_conn.cursor

    class GuardedCursor:
        def __init__(self, real_cursor):
            self._real = real_cursor

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def execute(self, query, *args, **kwargs):
            if not query.strip().lower().startswith("select"):
                raise AssertionError(f"auditor must not execute non-SELECT SQL: {query}")
            return self._real.execute(query, *args, **kwargs)

        def fetchall(self):
            return self._real.fetchall()

        def fetchone(self):
            return self._real.fetchone()

    monkeypatch.setattr(pg_conn, "cursor", lambda *a, **kw: GuardedCursor(original_cursor(*a, **kw)))

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)

    assert any(f["type"] == "MISSING_VECTOR" for f in findings)


def test_backup_snapshot_corruption_restore_integrity_workflow(
    make_document, qdrant_client, pg_conn, tmp_path
):
    """Isolated backup -> corruption/change -> restore -> integrity
    verification workflow (frozen H0.4 recovery requirement)."""
    doc = make_document("recoverable_policy.md", num_chunks=3)
    assert auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME) == []
    # run_audit only issues SELECTs but still leaves pg_conn "idle in
    # transaction" holding a read lock on document_registry until the
    # transaction ends. The restore below runs `DROP TABLE` (via pg_dump
    # --clean) on that same table from a separate connection (docker exec
    # psql), which blocks indefinitely on that lock if it is not released
    # first -- roll back after every read-only audit call in this test.
    pg_conn.rollback()

    # 1. Qdrant snapshot procedure.
    snapshot = recovery.create_qdrant_snapshot(qdrant_client, COLLECTION_NAME)
    assert snapshot is not None
    assert snapshot.name in {s.name for s in recovery.list_qdrant_snapshots(qdrant_client, COLLECTION_NAME)}

    # 2. PostgreSQL backup + verification.
    dump_path = tmp_path / "document_registry.sql"
    recovery.pg_dump_to_file(
        PG_CONTAINER, db=PG_DB, user=PG_USER, password=PG_PASSWORD, dest_path=dump_path
    )
    assert recovery.verify_backup_file(dump_path)

    # 3. Corruption/change: delete one vector (Qdrant) and mutate one
    #    provenance field in place (PostgreSQL) -- one corruption per store.
    qdrant_client.delete(collection_name=COLLECTION_NAME, points_selector=[doc["point_ids"][0]])
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE public.document_registry SET pipeline_version = %s WHERE document_hash = %s",
            ("corrupted-pipeline-v0", doc["document_hash"]),
        )
    pg_conn.commit()

    findings_after_corruption = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)
    assert any(f["type"] == "MISSING_VECTOR" for f in findings_after_corruption)
    assert any(f["type"] == "PROVENANCE_MISMATCH" for f in findings_after_corruption)
    pg_conn.rollback()  # release the read lock before the DDL-bearing restore below

    # 4. Controlled restore: Qdrant from snapshot, PostgreSQL from verified dump.
    recovery.recover_qdrant_snapshot(qdrant_client, COLLECTION_NAME, snapshot.name)
    recovery.pg_restore_from_file(
        PG_CONTAINER, db=PG_DB, user=PG_USER, password=PG_PASSWORD, src_path=dump_path
    )

    # 5. Recovered-data integrity verification: same auditor, same rules,
    #    now reports nothing -- restore reproduced the pre-corruption state.
    pg_conn.commit()
    findings_after_restore = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)
    assert findings_after_restore == []
