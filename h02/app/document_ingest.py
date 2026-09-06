import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from semantic_memory import get_embedding

COLLECTION_NAME = "karmo_documents"
QDRANT_URL = "http://127.0.0.1:6333"

client = QdrantClient(url=QDRANT_URL)

# H0.2 lifecycle metadata constants. is_active/document_version/
# superseded_by/created_at/deactivated_at are runtime values set per point
# below. pipeline_version/embedding_model/chunker_version identify which
# code path and model produced a point, for audit -- derived from what is
# actually imported/running in this module rather than a hardcoded guess.
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


def active_points_for_document(document_id):
    """All currently-active points for a logical document (H0.2 lifecycle).

    Used only to find the prior version to supersede; normal retrieval
    filtering lives in document_memory.search_documents.
    """
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="is_active", match=MatchValue(value=True)),
            ]
        ),
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    return points


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


INBOX = Path("/home/lofason/karmo-ai/core/documents/inbox")
PROCESSED = Path("/home/lofason/karmo-ai/core/documents/processed")
FAILED = Path("/home/lofason/karmo-ai/core/documents/failed")


def process_inbox():
    files = [p for p in INBOX.iterdir() if p.is_file()]

    if not files:
        print("INBOX EMPTY")
        return

    for path in files:
        try:
            document_hash = file_hash(path)

            destination = archive_destination(
                PROCESSED,
                path,
                document_hash,
            )

            ingest_document(
                path,
                archive_path=destination,
            )

            shutil.move(str(path), str(destination))
            print(f"MOVED TO PROCESSED: {destination.name}")

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


if __name__ == "__main__":
    process_inbox()
