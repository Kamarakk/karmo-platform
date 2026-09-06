"""Single acceptance pass for the H0.2 production-faithful deployable
modules (h02/app/document_ingest.py, h02/app/document_memory.py).

Docling and the production embedding path are exercised through their real
call sites in the deployable modules; only the heavy external dependencies
themselves (docling, semantic_memory) are stood in for via sys.modules, per
conftest.py -- the deployable source is untouched. One test, one pass, no
repeated/looping suite.
"""

import hashlib

V1_TEXT = "Employees may take unlimited paid leave with manager approval."
V2_TEXT = "Employees receive twenty-five days of paid leave per calendar year."


def test_h02_deployable_lifecycle(lifecycle_modules, tmp_path):
    document_ingest, document_memory = lifecycle_modules

    v1_dir = tmp_path / "v1"
    v2_dir = tmp_path / "v2"
    v1_dir.mkdir()
    v2_dir.mkdir()
    v1_path = v1_dir / "policy_handbook.md"
    v2_path = v2_dir / "policy_handbook.md"
    v1_path.write_text(V1_TEXT, encoding="utf-8")
    v2_path.write_text(V2_TEXT, encoding="utf-8")

    # document_id is derived from path.name (existing production path
    # semantics) -- same filename, later content -> new version of the same
    # logical document.
    assert document_ingest.document_id_for_path(v1_path) == "policy_handbook.md"
    assert document_ingest.document_id_for_path(v2_path) == "policy_handbook.md"

    v1_hash = document_ingest.file_hash(v1_path)
    assert v1_hash == hashlib.sha256(V1_TEXT.encode("utf-8")).hexdigest()

    document_ingest.ingest_document(v1_path)
    document_ingest.ingest_document(v2_path)

    # identical content re-ingested under the same name is still recognized
    # as a duplicate and skipped -- existing production dedup behavior.
    assert document_ingest.ingest_document(v1_path) is False

    history = document_memory.get_document_history("policy_handbook.md")
    assert len(history) == 2  # both versions present -- nothing deleted

    v1_point, v2_point = history
    assert v1_point.payload["document_version"] == 1
    assert v1_point.payload["document_hash"] == v1_hash
    assert v1_point.payload["is_active"] is False
    assert v1_point.payload["deactivated_at"] is not None
    assert v1_point.payload["superseded_by"] == v2_point.payload["document_hash"]
    assert v1_point.payload["created_at"] is not None
    assert v1_point.payload["pipeline_version"] == document_ingest.PIPELINE_VERSION
    assert v1_point.payload["embedding_model"] == document_ingest.EMBEDDING_MODEL
    assert v1_point.payload["chunker_version"] == document_ingest.CHUNKER_VERSION

    assert v2_point.payload["document_version"] == 2
    assert v2_point.payload["is_active"] is True
    assert v2_point.payload["superseded_by"] is None
    assert v2_point.payload["deactivated_at"] is None

    # normal retrieval returns only the active v2 version
    results = document_memory.search_documents(V2_TEXT, limit=10)
    assert len(results) > 0
    assert all(result["is_active"] for result in results)
    assert all(result["document_version"] == 2 for result in results)
    result_texts = {result["text"] for result in results}
    assert V2_TEXT in result_texts
    assert V1_TEXT not in result_texts
