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

# Explicit, clearly-labeled provenance value bootstrap_legacy_registry.py
# writes to a document_registry row when the pre-H0.2 Qdrant points it
# verified never carried a given provenance field at all (see that script's
# module docstring). Defined here, the module that owns provenance-mismatch
# semantics, and imported by bootstrap_legacy_registry.py, so there is one
# source of truth for the exact string both sides compare against.
LEGACY_PROVENANCE_LABEL = "legacy-unknown-pre-h0.2"

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
    """Compare registry provenance against each point's actual payload.

    One deliberate exception to a straight equality check: when the
    registry explicitly recorded ``LEGACY_PROVENANCE_LABEL`` for a field
    (bootstrap_legacy_registry.py's honest label for "this pre-H0.2 vector
    never had this field") and the Qdrant point genuinely has no value for
    that field either (``None`` -- absent, not merely different), that is
    the expected, known-legacy state, not a real disagreement. It is
    reported as ``LEGACY_PROVENANCE_UNVERIFIED`` -- still surfaced, never
    silently dropped -- so the auditor and its callers can treat it as an
    informational/known-legacy condition rather than a true integrity
    failure. Any other disagreement, including a legacy-labeled row against
    a point that DOES carry some other concrete value, is still a genuine
    ``PROVENANCE_MISMATCH``.
    """
    findings = []

    for point in points:
        for field in PROVENANCE_FIELDS:
            actual_value = point.payload.get(field)
            expected_value = row[field]

            if actual_value == expected_value:
                continue

            if expected_value == LEGACY_PROVENANCE_LABEL and actual_value is None:
                findings.append(
                    {
                        "type": "LEGACY_PROVENANCE_UNVERIFIED",
                        "point_id": str(point.id),
                        "field": field,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
                continue

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

    Two independent checks, both frozen H0.4 requirements -- the detection
    *intent* is frozen; the definition of "Qdrant-active" below was
    corrected (2026-09-09) to actually match that intent rather than
    silently drifting from it, per the same "fix and revalidate" precedent
    already used for this file's pagination-ceiling correction:

    - MULTIPLE_ACTIVE_VERSIONS: more than one registry row for this
      document_id is marked is_active.
    - ACTIVE_STATE_MISMATCH: the set of document_hash values Qdrant treats
      as active for this document_id disagrees with the registry's. A
      point counts as Qdrant-active when its payload has ``is_active=True``
      OR the ``is_active`` field is absent entirely -- this is not a
      legacy-only carve-out, it is the exact, single definition of
      "active" ``document_memory.search_documents`` already uses in
      production (see ``docs/handoff/h04/document_memory.py``: "the filter
      treats is_active=True and a missing is_active field as active, and
      excludes only is_active=False"). Only an explicit ``is_active=False``
      excludes a point. Before this correction, a legacy-bootstrapped
      document (registry is_active=True, Qdrant points with no is_active
      field at all -- the same class of pre-H0.2 point
      ``check_provenance``'s ``LEGACY_PROVENANCE_UNVERIFIED`` already
      accounts for) was permanently, spuriously reported as mismatched,
      even though production retrieval already treats it as fully active
      and consistent. The correction also *newly catches* a real gap the
      old definition silently missed: a document the registry marks
      ``is_active=False`` (superseded) whose Qdrant points still lack an
      explicit ``is_active=False`` -- production retrieval would still
      surface those points as active, which is a genuine inconsistency the
      old, narrower definition never reported.
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
        if point.payload.get("is_active") is not False
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
