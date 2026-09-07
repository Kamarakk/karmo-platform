"""Targeted regression test for the H0.4 production-scale pagination fix.

Separate from the frozen H0.4 acceptance suite
(test_h04_integrity_reconciliation.py) -- this proves one specific fix
(reconciliation._scroll_all following Qdrant's next_page_offset instead of
a single bounded scroll call), not a reconciliation-rule scenario, so it is
kept out of the "one concise acceptance workflow" file.
"""

import hashlib

import auditor
import registry_db
from qdrant_client.models import PointStruct

from conftest import (
    COLLECTION_NAME,
    DEFAULT_CHUNKER_VERSION,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_PIPELINE_VERSION,
    _deterministic_embedding,
)


def test_reconciliation_paginates_across_multiple_scroll_pages(
    pg_conn, qdrant_client, archive_root, monkeypatch
):
    """Register 3 healthy documents (point ids 1-3) plus one unregistered
    orphan point (id 4). With page_size=2, the 4-point collection cannot be
    read in a single scroll call, and integer point ids scroll back in
    ascending id order, so the orphan at id=4 is only reachable on the
    second page. This proves reconciliation follows Qdrant's
    next_page_offset to completion rather than stopping after one bounded
    scroll call, and still finds an inconsistency that lives past page 1.
    """
    hashes = []

    for n in range(1, 4):
        content = f"h04 pagination fixture document {n}"
        path = archive_root / f"paged_{n}.txt"
        path.write_text(content, encoding="utf-8")
        document_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        hashes.append(document_hash)

        registry_db.register_document_version(
            pg_conn,
            document_id=f"paged_{n}.md",
            document_version=1,
            document_hash=document_hash,
            archive_source_location=str(path),
            expected_chunk_count=1,
            pipeline_version=DEFAULT_PIPELINE_VERSION,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            chunker_version=DEFAULT_CHUNKER_VERSION,
        )
    pg_conn.commit()

    points = [
        PointStruct(
            id=n,
            vector=_deterministic_embedding(f"paged chunk {n}"),
            payload={
                "document_hash": hashes[n - 1],
                "document_id": f"paged_{n}.md",
                "chunk_number": 1,
                "is_active": True,
                "pipeline_version": DEFAULT_PIPELINE_VERSION,
                "embedding_model": DEFAULT_EMBEDDING_MODEL,
                "chunker_version": DEFAULT_CHUNKER_VERSION,
            },
        )
        for n in range(1, 4)
    ]

    orphan_hash = "f" * 64
    points.append(
        PointStruct(
            id=4,
            vector=_deterministic_embedding("orphan point on a later scroll page"),
            payload={
                "document_hash": orphan_hash,
                "document_id": "ghost_paged.md",
                "chunk_number": 1,
            },
        )
    )

    qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

    real_scroll = qdrant_client.scroll
    unfiltered_call_count = {"n": 0}

    def counting_scroll(*args, **kwargs):
        if kwargs.get("scroll_filter") is None:
            unfiltered_call_count["n"] += 1
        return real_scroll(*args, **kwargs)

    monkeypatch.setattr(qdrant_client, "scroll", counting_scroll)

    findings = auditor.run_audit(pg_conn, qdrant_client, COLLECTION_NAME, page_size=2)

    # More than one collection-wide (unfiltered) scroll call means the
    # 4-point collection was not read in a single limit=2 page -- pagination
    # actually ran to completion rather than truncating at the first page.
    assert unfiltered_call_count["n"] > 1

    orphan_findings = [f for f in findings if f["type"] == "ORPHAN_VECTOR"]
    assert len(orphan_findings) == 1
    assert orphan_findings[0]["point_id"] == "4"
    assert orphan_findings[0]["document_hash"] == orphan_hash

    # The three registered, healthy documents on page 1 must not be
    # misreported just because reconciliation had to page past them.
    assert not any(f["type"] != "ORPHAN_VECTOR" for f in findings)
