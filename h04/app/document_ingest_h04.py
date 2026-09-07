"""H0.4 production-faithful H0.2 document ingest, with PostgreSQL
document_registry integration.

This file starts from the exact current H0.2 production ingest reference
(``docs/handoff/h04/document_ingest.py``, byte-identical to the current main
branch's ``h02/app/document_ingest.py``) and changes nothing about its
Qdrant behavior: same Docling ``DocumentConverter``/``HybridChunker``, same
``semantic_memory.get_embedding`` call, same SHA-256 document identity, same
UUID5 chunk ids, same ``karmo_documents`` collection, same H0.2
active/superseded lifecycle (upsert new points, then ``set_payload`` the
prior active points inactive), same inbox/processed/failed archive
handling. No H0.3 hybrid retrieval is introduced anywhere in this module.

The only addition is PostgreSQL ``public.document_registry`` bookkeeping
(``h04/app/registry_db.py``), and it is added at the boundary where it can
be added without touching any Qdrant read/write call:

- ``ingest_document`` gains exactly one behavioral change: on a successful
  ingest it now returns a plain dict describing exactly what it just wrote
  to Qdrant (document identity, expected chunk count, the same
  pipeline_version/embedding_model/chunker_version already stamped on every
  point payload, and which prior document_hash(es) it superseded), instead
  of implicitly returning ``None``. Every Qdrant call inside the function --
  what gets upserted, what gets superseded, in what order -- is unchanged.
  A skipped duplicate still returns ``False``; a failed ingest still raises
  before there is anything to register.
- ``process_inbox`` performs the PostgreSQL registration only after the
  file has actually been moved to its final ``PROCESSED`` location, so
  ``archive_source_location`` always reflects the archived path, never the
  temporary inbox path.

document_registry is the H0.4 authoritative expected-state registry, so a
failed registry write is never treated as harmless. The write ordering is
fixed and one-directional -- convert/chunk/embed, then Qdrant upsert, then
archive move, then the registry lifecycle write -- and nothing earlier in
that chain is ever undone if a later step fails:

- If PostgreSQL/``KARMO_DB_PASSWORD`` is unavailable, or the registry
  lifecycle write itself fails, Qdrant ingestion and the archive move are
  NOT rolled back, undone, or repaired -- those already succeeded and stay
  exactly as they are, preserving the evidence ``run_auditor.py`` needs to
  detect the gap (an unregistered document_hash with real Qdrant chunks and
  a real archived file).
- The failure is reported loudly, per document, as "INTEGRITY INCOMPLETE /
  REGISTRY FAILED" -- never printed or logged as if the document completed
  successfully.
- ``process_inbox`` tracks whether any registry write failed this run and
  returns ``False`` if so; ``python document_ingest_h04.py`` exits nonzero
  in that case, so the failure is visible to whatever runs this job (cron,
  systemd, CI), not silently swallowed.
- The registry lifecycle write itself (new-version insert + prior-version
  deactivation) is one PostgreSQL transaction: both statements commit
  together via ``_commit_registry_lifecycle``, or neither does -- see that
  function for detail.

Inheritance & forward compatibility correction: ``active_points_for_document``
inherited H0.2's fixed ``limit=10000`` Qdrant scroll ceiling with the offset
discarded -- the same class of bug already fixed in
``reconciliation.py``'s ``_scroll_all`` before H0.4 was accepted. A logical
document with more than 10000 active chunks would have had only the first
10000 superseded, silently leaving the rest ``is_active=True`` in Qdrant.
Replaced with a local ``_scroll_all`` that follows ``next_page_offset``
until exhausted, mirroring ``reconciliation._scroll_all``'s shape without
importing it (the ingest pipeline stays independent of the audit module).
No other production-path H0.4 file (``bootstrap_legacy_registry.py``,
``run_auditor.py``, ``reconciliation.py``, ``registry_db.py``,
``auditor.py``) has an equivalent fixed-ceiling gap -- see PR #6 for the
review.

This module never automatically deletes a Qdrant vector, moves an archived
file back out of PROCESSED, or retries/repairs a registry gap on its own.
"""

import hashlib
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from semantic_memory import get_embedding

import registry_db

COLLECTION_NAME = "karmo_documents"
QDRANT_URL = "http://127.0.0.1:6333"

client = QdrantClient(url=QDRANT_URL)

# H0.2 lifecycle metadata constants. is_active/document_version/
# superseded_by/created_at/deactivated_at are runtime values set per point
# below. pipeline_version/embedding_model/chunker_version identify which
# code path and model produced a point, for audit -- derived from what is
# actually imported/running in this module rather than a hardcoded guess.
# These are the exact values written into every Qdrant point payload below,
# and are reused verbatim for the document_registry row for the same
# version, so the H0.4 auditor's PROVENANCE_MISMATCH check never fires for
# a document ingested through this module.
PIPELINE_VERSION = "h02-document-ingest-v1"
EMBEDDING_MODEL = "semantic_memory.get_embedding"

try:
    import docling as _docling

    _DOCLING_VERSION = getattr(_docling, "__version__", "unknown")
except Exception:  # pragma: no cover - docling is a hard import above; this
    _DOCLING_VERSION = "unknown"  # only guards the optional __version__ read

CHUNKER_VERSION = f"docling.chunking.HybridChunker=={_DOCLING_VERSION}"


def file_hash(path):
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def chunk_id(document_hash, number, text):
    identity = f"{document_hash}:{number}:{text}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def document_id_for_path(path):
    """Stable logical document identity across versions (H0.2).

    Derived from the existing production path semantics rather than a new
    identity scheme: ``path.name`` is already what this module uses as
    ``source_file`` and for processed/failed archive naming (see
    ``archive_destination`` below). Re-ingesting a file with the same name
    but new content is therefore recognized as a new version of the same
    logical document.
    """
    return path.name


def archive_destination(directory, path, document_hash):
    destination = directory / path.name

    if not destination.exists():
        return destination

    return directory / f"{path.stem}__{document_hash[:12]}{path.suffix}"



def document_exists(document_hash):
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="document_hash",
                    match=MatchValue(value=document_hash),
                )
            ]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )

    return bool(points)


DEFAULT_SCROLL_PAGE_SIZE = 1000


def _scroll_all(scroll_filter, *, page_size=DEFAULT_SCROLL_PAGE_SIZE):
    """Read every point matching scroll_filter, following Qdrant's
    next_page_offset until it is None -- never a single bounded call. Same
    "loop until exhausted" shape as reconciliation._scroll_all (kept local
    rather than imported so the ingest pipeline has no dependency on the
    audit module); page_size bounds one round-trip's response size only,
    never the total number of points read.
    """
    points = []
    offset = None

    while True:
        batch, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
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


def active_points_for_document(document_id):
    """All currently-active points for a logical document (H0.2 lifecycle).

    Used only to find the prior version to supersede; normal retrieval
    filtering lives in document_memory.search_documents. Paginates through
    the full result set -- a document version with more active chunks than
    one page must still be superseded in full, not silently truncated at a
    fixed ceiling (see AGENTS.md/CLAUDE.md inheritance & forward
    compatibility rule).
    """
    return _scroll_all(
        Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="is_active", match=MatchValue(value=True)),
            ]
        )
    )


def ingest_document(file_path, archive_path=None):
    path = Path(file_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(path)

    document_hash = file_hash(path)
    document_id = document_id_for_path(path)

    if document_exists(document_hash):
        print(f"SKIPPED DUPLICATE: {path.name}")
        print(f"Document hash: {document_hash}")
        return False

    previous_active = active_points_for_document(document_id)
    document_version = (
        previous_active[0].payload.get("document_version", 0) + 1
        if previous_active
        else 1
    )

    ingested_at = datetime.now(timezone.utc).isoformat()

    print(f"Processing: {path.name}")
    print(f"Document hash: {document_hash}")

    result = DocumentConverter().convert(str(path))
    chunker = HybridChunker()
    chunks = list(chunker.chunk(result.document))

    print(f"Chunks found: {len(chunks)}")

    points = []

    for number, chunk in enumerate(chunks, start=1):
        text = chunker.contextualize(chunk)

        if not text.strip():
            continue

        vector = get_embedding(text)

        points.append(
            PointStruct(
                id=chunk_id(document_hash, number, text),
                vector=vector,
                payload={
                    "text": text,
                    "source_file": path.name,
                    "source_path": str(archive_path) if archive_path else str(path),
                    "intake_path": str(path),
                    "archive_path": str(archive_path) if archive_path else None,
                    "document_type": path.suffix.lower(),
                    "document_hash": document_hash,
                    "chunk_number": number,
                    "ingested_at": ingested_at,
                    "document_id": document_id,
                    "document_version": document_version,
                    "is_active": True,
                    "superseded_by": None,
                    "created_at": ingested_at,
                    "deactivated_at": None,
                    "pipeline_version": PIPELINE_VERSION,
                    "embedding_model": EMBEDDING_MODEL,
                    "chunker_version": CHUNKER_VERSION,
                },
            )
        )

        print(f"Prepared chunk {number}/{len(chunks)}")

    if not points:
        raise RuntimeError("Document produced no usable chunks.")

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    if previous_active:
        superseded_version = previous_active[0].payload.get("document_version")
        client.set_payload(
            collection_name=COLLECTION_NAME,
            payload={
                "is_active": False,
                "deactivated_at": ingested_at,
                "superseded_by": document_hash,
            },
            points=[point.id for point in previous_active],
        )
        print(
            f"SUPERSEDED: {len(previous_active)} chunk(s) from document_version "
            f"{superseded_version} of {document_id}"
        )

    print(f"INGESTED: {path.name}")
    print(f"CHUNKS UPSERTED: {len(points)}")
    print(f"Document version: {document_version}")

    # H0.4 addition only: report exactly the facts this call already wrote
    # to Qdrant, above, so process_inbox can register the same facts in
    # PostgreSQL once the final archive path is known. Nothing above this
    # line differs from docs/handoff/h04/document_ingest.py.
    return {
        "document_id": document_id,
        "document_version": document_version,
        "document_hash": document_hash,
        "expected_chunk_count": len(points),
        "pipeline_version": PIPELINE_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "chunker_version": CHUNKER_VERSION,
        "ingested_at": ingested_at,
        "superseded_document_hashes": sorted(
            {
                point.payload.get("document_hash")
                for point in previous_active
                if point.payload.get("document_hash")
            }
        ),
    }


INBOX = Path("/home/lofason/karmo-ai/core/documents/inbox")
PROCESSED = Path("/home/lofason/karmo-ai/core/documents/processed")
FAILED = Path("/home/lofason/karmo-ai/core/documents/failed")


class RegistryLifecycleError(RuntimeError):
    """Raised when the H0.4 PostgreSQL registry lifecycle write (new-version
    insert + prior-version deactivation) could not be committed for an
    otherwise-successful H0.2 ingest.

    Qdrant already has the new points and the archive already has the final
    file by the time this can be raised -- this signals that
    document_registry is now missing/out of sync with that already-real
    state, not that the ingest itself was invalid or should be undone.
    Nothing upstream of the registry write is touched when this is raised.
    """


def _commit_registry_lifecycle(pg_conn, registration, archive_path):
    """Atomically write the PostgreSQL side of one successful H0.2 ingest:
    insert the new active registry row, deactivate whichever
    document_hash(es) Qdrant just superseded, and commit both together on
    one transaction.

    Both statements run on ``pg_conn`` without an intervening commit, so
    they share one PostgreSQL transaction; either both take effect
    (``pg_conn.commit()`` below) or neither does. Any failure anywhere in
    this function rolls back that transaction and re-raises as
    ``RegistryLifecycleError`` -- the caller decides how to report the
    fail-closed condition, but no partial registry state is ever left
    committed.

    Only ever called with a successful ``registration`` dict -- never for a
    skipped duplicate (``False``) or a failed ingest (exception raised
    before ``ingest_document`` returns).
    """
    try:
        registry_db.register_document_version(
            pg_conn,
            document_id=registration["document_id"],
            document_version=registration["document_version"],
            document_hash=registration["document_hash"],
            archive_source_location=str(archive_path),
            expected_chunk_count=registration["expected_chunk_count"],
            pipeline_version=registration["pipeline_version"],
            embedding_model=registration["embedding_model"],
            chunker_version=registration["chunker_version"],
            is_active=True,
            superseded_by=None,
            source_path=str(archive_path),
            deactivated_at=None,
        )

        for superseded_hash in registration["superseded_document_hashes"]:
            registry_db.deactivate_document_version(
                pg_conn,
                superseded_hash,
                superseded_by=registration["document_hash"],
                deactivated_at=registration["ingested_at"],
            )

        pg_conn.commit()
    except Exception as error:
        pg_conn.rollback()
        raise RegistryLifecycleError(
            "document_registry lifecycle write failed for "
            f"{registration['document_id']} v{registration['document_version']} "
            f"(document_hash={registration['document_hash']}): {error}"
        ) from error


def _report_registry_incomplete(registration, reason):
    """Fail-closed reporting for one document whose Qdrant ingest and
    archive move already succeeded but whose registry lifecycle write did
    not. Never called for a document that is actually fully registered."""
    print(
        "INTEGRITY INCOMPLETE / REGISTRY FAILED: "
        f"{registration['document_id']} v{registration['document_version']} "
        f"(document_hash={registration['document_hash']}): {reason}"
    )
    print(
        "Qdrant vectors and the archived file for this version are NOT "
        "being modified, deleted, or moved back. document_registry does "
        "not yet reflect this version -- run_auditor.py will detect this "
        "gap until it is reconciled. No automatic repair is performed."
    )


def process_inbox():
    """Returns True if the run completed with no registry-lifecycle
    integrity gaps, False otherwise. ``__main__`` below exits nonzero on
    False so a failed registry write is visible to whatever runs this job.
    This return value does not track H0.2 per-file FAILED routing (that is
    unchanged, pre-existing H0.2 behavior, reported via ERROR/MOVED TO
    FAILED prints as before) -- only the new PostgreSQL fail-closed
    guarantee described in this module's docstring.
    """
    files = [p for p in INBOX.iterdir() if p.is_file()]

    if not files:
        print("INBOX EMPTY")
        return True

    pg_conn = None
    try:
        pg_conn = registry_db.get_connection()
    except Exception as error:
        print(f"DOCUMENT_REGISTRY UNAVAILABLE: {error}")
        print(
            "H0.2 Qdrant ingest below still runs (this module never blocks "
            "Qdrant ingestion on PostgreSQL availability), but every "
            "document successfully ingested this run will be reported as "
            "INTEGRITY INCOMPLETE / REGISTRY FAILED below, and this run "
            "will exit nonzero."
        )

    had_registry_failures = False

    try:
        for path in files:
            try:
                document_hash = file_hash(path)

                destination = archive_destination(
                    PROCESSED,
                    path,
                    document_hash,
                )

                registration = ingest_document(
                    path,
                    archive_path=destination,
                )

                shutil.move(str(path), str(destination))
                print(f"MOVED TO PROCESSED: {destination.name}")

                if registration:
                    if pg_conn is None:
                        _report_registry_incomplete(
                            registration,
                            "document_registry connection unavailable this run",
                        )
                        had_registry_failures = True
                    else:
                        try:
                            _commit_registry_lifecycle(pg_conn, registration, destination)
                            print(
                                "REGISTERED IN DOCUMENT_REGISTRY: "
                                f"{registration['document_id']} "
                                f"v{registration['document_version']}"
                            )
                        except RegistryLifecycleError as error:
                            _report_registry_incomplete(registration, str(error))
                            had_registry_failures = True

            except Exception as error:
                document_hash = file_hash(path)

                destination = archive_destination(
                    FAILED,
                    path,
                    document_hash,
                )

                shutil.move(str(path), str(destination))
                print(f"MOVED TO FAILED: {destination.name}")
                print(f"ERROR: {error}")
    finally:
        if pg_conn is not None:
            pg_conn.close()

    return not had_registry_failures


if __name__ == "__main__":
    sys.exit(0 if process_inbox() else 1)
