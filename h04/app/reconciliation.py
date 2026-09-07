"""H0.4 PostgreSQL <-> Qdrant reconciliation rules.

Every function here is read-only against Qdrant (scroll/query only, never
upsert/set_payload/delete) and takes PostgreSQL registry rows as already-
fetched plain dicts (see registry_db.list_registry / list_by_document_id) so
this module never opens its own database connection. Qdrant remains vector
retrieval storage; PostgreSQL remains the authoritative expected state that
Qdrant's actual state is compared against.
"""

from qdrant_client.models import FieldCondition, Filter, MatchValue

PROVENANCE_FIELDS = ("pipeline_version", "embedding_model", "chunker_version")

# Page size for each individual scroll call. This bounds one round-trip's
# response size only -- it is not a cap on how many points reconciliation
# examines. _scroll_all below follows next_page_offset until Qdrant reports
# none left, so the whole applicable collection is read regardless of point
# count.
DEFAULT_SCROLL_PAGE_SIZE = 1000


def _scroll_all(qdrant_client, collection_name, *, scroll_filter=None, page_size=DEFAULT_SCROLL_PAGE_SIZE):
    """Read every point matching scroll_filter (or the whole collection, if
    scroll_filter is None), following Qdrant's scroll pagination to
    completion. Read-only: .scroll() only, never a write API."""
    points = []
    offset = None

    while True:
        batch, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points.extend(batch)

        if next_offset is None:
            break

        offset = next_offset

    return points


def actual_chunk_points(qdrant_client, collection_name, document_hash, *, page_size=DEFAULT_SCROLL_PAGE_SIZE):
    return _scroll_all(
        qdrant_client,
        collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="document_hash", match=MatchValue(value=document_hash))]
        ),
        page_size=page_size,
    )


def all_points(qdrant_client, collection_name, *, page_size=DEFAULT_SCROLL_PAGE_SIZE):
    points = _scroll_all(qdrant_client, collection_name, page_size=page_size)
    return points


def check_chunk_counts(row, points):
    """Compare expected_chunk_count against the actual chunk_number set.

    A chunk_number in [1, expected_chunk_count] that has no matching point
    is a MISSING_VECTOR. A chunk_number backed by more than one point is a
    DUPLICATE_VECTOR (counted by distinct chunk_number, not by point count,
    so this does not also collapse into MISSING_VECTOR). A point whose
    chunk_number falls outside that range, or an actual point count that
    otherwise disagrees with what was expected, is
    INCORRECT_EXPECTED_CHUNK_COUNT -- distinct from ORPHAN_VECTOR, which is
    a point belonging to a document_hash with no registry row at all.
    """
    expected = set(range(1, row["expected_chunk_count"] + 1))
    chunk_numbers = [point.payload.get("chunk_number") for point in points]
    distinct = set(chunk_numbers)

    findings = []

    for chunk_number in sorted(expected - distinct):
        findings.append({"type": "MISSING_VECTOR", "chunk_number": chunk_number})

    for chunk_number in sorted(n for n in distinct if chunk_numbers.count(n) > 1):
        findings.append(
            {
                "type": "DUPLICATE_VECTOR",
                "chunk_number": chunk_number,
                "point_count": chunk_numbers.count(chunk_number),
            }
        )

    extra = sorted(n for n in (distinct - expected) if n is not None)
    if extra or len(points) != row["expected_chunk_count"]:
        findings.append(
            {
                "type": "INCORRECT_EXPECTED_CHUNK_COUNT",
                "expected_chunk_count": row["expected_chunk_count"],
                "actual_chunk_count": len(points),
                "extra_chunk_numbers": extra,
            }
        )

    return findings


def check_provenance(row, points):
    findings = []

    for point in points:
        for field in PROVENANCE_FIELDS:
            actual_value = point.payload.get(field)
            expected_value = row[field]
            if actual_value != expected_value:
                findings.append(
                    {
                        "type": "PROVENANCE_MISMATCH",
                        "point_id": str(point.id),
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )

    return findings


def find_orphan_vectors(qdrant_client, collection_name, known_hashes, *, page_size=DEFAULT_SCROLL_PAGE_SIZE):
    """Points whose document_hash has no corresponding registry row."""
    orphans = []

    for point in all_points(qdrant_client, collection_name, page_size=page_size):
        document_hash = point.payload.get("document_hash")
        if document_hash not in known_hashes:
            orphans.append(
                {
                    "type": "ORPHAN_VECTOR",
                    "point_id": str(point.id),
                    "document_hash": document_hash,
                    "document_id": point.payload.get("document_id"),
                }
            )

    return orphans


def check_active_version_state(document_id, registry_rows, points):
    """Detect invalid active-version state for one logical document.

    Two independent checks, both frozen H0.4 requirements:
    - MULTIPLE_ACTIVE_VERSIONS: more than one registry row for this
      document_id is marked is_active.
    - ACTIVE_STATE_MISMATCH: the set of document_hash values Qdrant marks
      is_active for this document_id disagrees with the registry's.
    """
    findings = []

    active_rows = [row for row in registry_rows if row["is_active"]]
    if len(active_rows) > 1:
        findings.append(
            {
                "type": "MULTIPLE_ACTIVE_VERSIONS",
                "document_id": document_id,
                "active_hashes": sorted(row["document_hash"] for row in active_rows),
            }
        )

    registry_active_hashes = {row["document_hash"] for row in active_rows}
    qdrant_active_hashes = {
        point.payload.get("document_hash")
        for point in points
        if point.payload.get("is_active") is True
    }

    if registry_active_hashes != qdrant_active_hashes:
        findings.append(
            {
                "type": "ACTIVE_STATE_MISMATCH",
                "document_id": document_id,
                "registry_active_hashes": sorted(registry_active_hashes),
                "qdrant_active_hashes": sorted(qdrant_active_hashes),
            }
        )

    return findings
