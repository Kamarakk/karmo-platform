"""H0.4 registry repair acceptance: one test per scenario named in
docs/plans/KARMO_FOUNDATION_COMPLETION_PLAN.md Workload 3 -- healthy
repair, ambiguous/refuse case, already-registered no-op, and
report-only-by-default (proven by write-call injection, same technique as
test_auditor_is_report_only). Runs against the real isolated Postgres +
Qdrant stack (h04/docker-compose.yml), never against auditor.py or
reconciliation.py's own frozen suite.
"""

import hashlib
import uuid

import auditor
import registry_db
import registry_repair
from qdrant_client.models import PointStruct

from conftest import (
    COLLECTION_NAME,
    DEFAULT_CHUNKER_VERSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PIPELINE_VERSION,
    _deterministic_embedding,
)


def _upsert_orphan_points(qdrant_client, *, document_id, document_hash, num_chunks=3, **overrides):
    """Write Qdrant points shaped exactly like a real H0.4 ingest
    (document_ingest_h04.ingest_document's payload) for a document_hash
    that has no document_registry row -- i.e. the ORPHAN_VECTOR gap this
    tool repairs. No registry row is written here on purpose."""
    point_ids = []
    for chunk_number in range(1, num_chunks + 1):
        text = f"orphan {document_id} chunk {chunk_number} {uuid.uuid4()}"
        point_id = str(uuid.uuid4())
        point_ids.append(point_id)
        payload = {
            "text": text,
            "document_id": document_id,
            "document_version": 1,
            "document_hash": document_hash,
            "chunk_number": chunk_number,
            "archive_path": f"/tmp/does-not-matter/{document_id}",
            "source_path": f"/tmp/does-not-matter/{document_id}",
            "is_active": True,
            "superseded_by": None,
            "deactivated_at": None,
            "pipeline_version": DEFAULT_PIPELINE_VERSION,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "chunker_version": DEFAULT_CHUNKER_VERSION,
        }
        payload.update(overrides)
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(id=point_id, vector=_deterministic_embedding(text), payload=payload)
            ],
        )
    return point_ids


def test_healthy_orphan_repaired_and_no_longer_reported(qdrant_client, pg_conn, archive_root):
    document_id = "orphan_healthy.md"
    archive_path = archive_root / document_id
    # The repair tool recomputes SHA-256 from the archived file, so
    # document_hash must be derived from real archived content, not a
    # fixed placeholder.
    content = f"real synthetic content for {document_id}"
    archive_path.write_text(content, encoding="utf-8")
    document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    _upsert_orphan_points(
        qdrant_client,
        document_id=document_id,
        document_hash=document_hash,
        num_chunks=3,
        archive_path=str(archive_path),
        source_path=str(archive_path),
    )

    known_hashes = {row["document_hash"] for row in registry_db.list_registry(pg_conn)}
    assert document_hash not in known_hashes

    findings_before = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)
    assert any(
        f["type"] == "ORPHAN_VECTOR" and f["document_hash"] == document_hash
        for f in findings_before
    )

    plan = registry_repair.build_plan(pg_conn, qdrant_client, COLLECTION_NAME, known_hashes)
    assert plan["refused"] == []
    ready_hashes = {entry["document_hash"] for entry in plan["ready"]}
    assert document_hash in ready_hashes

    registered, failed = registry_repair.apply_plan(pg_conn, plan["ready"])
    assert failed == []
    assert document_hash in registered

    row = registry_db.get_by_hash(pg_conn, document_hash)
    assert row is not None
    assert row["document_id"] == document_id
    assert row["expected_chunk_count"] == 3
    assert row["is_active"] is True

    findings_after = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME)
    assert not any(f["type"] == "ORPHAN_VECTOR" for f in findings_after)


def test_ambiguous_group_is_refused_not_guessed(qdrant_client, pg_conn, archive_root):
    document_id = "orphan_ambiguous.md"
    content = f"real synthetic content for {document_id}"
    archive_path = archive_root / document_id
    archive_path.write_text(content, encoding="utf-8")
    document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    point_ids = _upsert_orphan_points(
        qdrant_client,
        document_id=document_id,
        document_hash=document_hash,
        num_chunks=2,
        archive_path=str(archive_path),
        source_path=str(archive_path),
    )
    # One of the two points in this document_hash group now disagrees on
    # pipeline_version -- genuinely ambiguous, must be refused rather than
    # picking either value.
    qdrant_client.set_payload(
        collection_name=COLLECTION_NAME,
        payload={"pipeline_version": "pipeline-b"},
        points=[point_ids[0]],
    )

    known_hashes = {row["document_hash"] for row in registry_db.list_registry(pg_conn)}
    plan = registry_repair.build_plan(pg_conn, qdrant_client, COLLECTION_NAME, known_hashes)

    assert plan["ready"] == []
    refused_reasons = {
        item["reason"] for item in plan["refused"] if item.get("document_hash") == document_hash
    }
    assert "INCONSISTENT_PROVENANCE" in refused_reasons

    assert registry_db.get_by_hash(pg_conn, document_hash) is None


def test_already_registered_group_is_a_noop_on_rerun(qdrant_client, pg_conn, archive_root):
    document_id = "orphan_rerun.md"
    content = f"real synthetic content for {document_id}"
    archive_path = archive_root / document_id
    archive_path.write_text(content, encoding="utf-8")
    document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    _upsert_orphan_points(
        qdrant_client,
        document_id=document_id,
        document_hash=document_hash,
        num_chunks=2,
        archive_path=str(archive_path),
        source_path=str(archive_path),
    )

    known_hashes = {row["document_hash"] for row in registry_db.list_registry(pg_conn)}
    first_plan = registry_repair.build_plan(pg_conn, qdrant_client, COLLECTION_NAME, known_hashes)
    registered, failed = registry_repair.apply_plan(pg_conn, first_plan["ready"])
    assert failed == []
    assert document_hash in registered

    # Re-run reusing the same (now-stale) known_hashes set, as if this were
    # a concurrent/retried invocation racing the first apply -- this is
    # exactly the race build_plan's own get_by_hash re-check guards
    # against (the orphan-detection filter alone would already exclude a
    # freshly-recomputed known_hashes set, so it would never prove this
    # guard runs at all).
    second_plan = registry_repair.build_plan(
        pg_conn, qdrant_client, COLLECTION_NAME, known_hashes
    )

    assert document_hash not in {entry["document_hash"] for entry in second_plan["ready"]}
    assert document_hash in second_plan["already_registered"]

    registered_again, failed_again = registry_repair.apply_plan(pg_conn, second_plan["ready"])
    assert registered_again == []
    assert failed_again == []

    row = registry_db.get_by_hash(pg_conn, document_hash)
    assert row is not None  # unchanged, not duplicated or re-inserted


def test_build_plan_is_report_only_by_default(qdrant_client, pg_conn, monkeypatch, archive_root):
    """build_plan (the code path main() runs without --apply) must detect a
    real repairable gap using only read APIs -- proven by making every
    mutating API on both stores raise if called, then asserting plan
    generation still runs to completion and still reports the READY
    group. Mirrors test_auditor_is_report_only's technique."""
    document_id = "orphan_guarded.md"
    content = f"real synthetic content for {document_id}"
    archive_path = archive_root / document_id
    archive_path.write_text(content, encoding="utf-8")
    document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    _upsert_orphan_points(
        qdrant_client,
        document_id=document_id,
        document_hash=document_hash,
        num_chunks=1,
        archive_path=str(archive_path),
        source_path=str(archive_path),
    )

    def _forbidden(*args, **kwargs):
        raise AssertionError("build_plan must not call Qdrant write APIs")

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
                raise AssertionError(f"build_plan must not execute non-SELECT SQL: {query}")
            return self._real.execute(query, *args, **kwargs)

        def fetchall(self):
            return self._real.fetchall()

        def fetchone(self):
            return self._real.fetchone()

    monkeypatch.setattr(pg_conn, "cursor", lambda *a, **kw: GuardedCursor(original_cursor(*a, **kw)))

    known_hashes = set()  # no SELECT needed to know this -- keeps this test focused on build_plan's own guard, not registry_db's
    plan = registry_repair.build_plan(pg_conn, qdrant_client, COLLECTION_NAME, known_hashes)

    ready_hashes = {entry["document_hash"] for entry in plan["ready"]}
    assert document_hash in ready_hashes
    assert registry_db.get_by_hash(pg_conn, document_hash) is None  # still unwritten -- report-only
