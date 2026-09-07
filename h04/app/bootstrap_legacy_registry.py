"""H0.4 one-time, explicit bootstrap of PostgreSQL document_registry rows
for legacy (pre-H0.2) Qdrant vectors.

Scope: this is a report/apply CLI, not an ingest pipeline. It never converts
a document, computes an embedding, or writes/modifies a Qdrant point -- it
only reads existing ``karmo_documents`` payloads (read-only ``.scroll()``,
via ``reconciliation.all_points``), reads existing archived files on disk to
recompute their SHA-256 (via ``archive_integrity.file_hash``), and, only
when explicitly asked, inserts new rows into ``public.document_registry``
via ``registry_db.register_document_version``. It never issues an UPDATE or
DELETE against an existing registry row, and it never touches Qdrant.

Default behavior is report-only: running this script with no flags prints
the full plan (what would be registered, what is refused and why, what is
already registered) and writes nothing. Only ``--apply`` writes.

What counts as "legacy": a Qdrant point whose payload has no ``is_active``
key at all -- the same definition ``docs/handoff/h04/document_memory.py``
already documents ("Production karmo_documents holds pre-H0.2 vectors with
no is_active field at all -- those are legacy active knowledge"). Points
that do carry H0.2/H0.4 lifecycle fields are out of scope here: they are
either already registered by ``document_ingest_h04.py`` at ingest time, or
are a normal H0.4 reconciliation concern for ``run_auditor.py``, not a
bootstrap concern.

Grouping and verification, per legacy document_hash group:

1. Every point in the group must agree on a single ``source_file`` --
   disagreement means the group itself is internally inconsistent data and
   is refused (INCONSISTENT_SOURCE_FILE), not guessed at.
2. If more than one distinct document_hash maps to the same source_file
   among legacy points, none of those groups can be assigned an
   unambiguous document_version -- all are refused
   (AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE) rather than ordered by a
   guess (e.g. ingested_at, which is caller-supplied and not a lifecycle
   guarantee pre-H0.2). A human resolves these manually.
3. The group's chunk_number values must form exactly {1..N} with no gaps
   and no duplicates (N = point count) -- otherwise expected_chunk_count
   cannot be verified (UNVERIFIABLE_CHUNK_COUNT).
4. The archived file (preferring the payload's own ``archive_path``, then
   falling back to ``<processed_dir>/<source_file>``) must exist
   (MISSING_ARCHIVE_FILE) and its recomputed SHA-256 must equal the
   document_hash (ARCHIVED_FILE_HASH_MISMATCH).
5. pipeline_version/embedding_model/chunker_version: if every point in the
   group agrees on a real (non-null) value for a field, that value is used
   verbatim -- never overwritten with a legacy label. Only when every point
   in the group lacks the field entirely does this script fall back to the
   explicit ``LEGACY_PROVENANCE_LABEL`` for that field, never a fabricated
   pipeline/model/chunker identity. Disagreement across points on a field
   that IS present is refused (INCONSISTENT_PROVENANCE), not averaged or
   guessed. A group registered with the legacy label, matched against a
   Qdrant point that still has no value for that field, is reported by
   run_auditor.py as an informational LEGACY_PROVENANCE_UNVERIFIED finding
   (see reconciliation.check_provenance) -- not PROVENANCE_MISMATCH, and
   not a real integrity failure -- since that IS the honest, expected state
   for a chunk that genuinely predates H0.2 provenance tracking.
6. A document_hash already present in document_registry is reported as
   ALREADY_REGISTERED and skipped -- never re-inserted, never updated.

Every group that is registered gets document_version=1 and is_active=True:
version 1 because bootstrap only ever proceeds past step 2 above when
exactly one document_hash exists for a source_file (so there is no prior
version to number against); is_active=True because that is what current
H0.2 retrieval (document_memory.search_documents) already treats a
missing-is_active point as.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from qdrant_client import QdrantClient

import archive_integrity
import reconciliation
import registry_db

COLLECTION_NAME = "karmo_documents"
QDRANT_URL = "http://127.0.0.1:6333"

# Must match document_ingest_h04.PROCESSED. Duplicated as a plain constant
# here rather than imported, so this report/apply CLI never imports (and
# therefore never instantiates the module-level QdrantClient inside) the
# ingest module -- consistent with this script's own no-Qdrant-write scope.
PROCESSED = Path("/home/lofason/karmo-ai/core/documents/processed")

PROVENANCE_FIELDS = ("pipeline_version", "embedding_model", "chunker_version")

# Single source of truth for this string lives in reconciliation.py (the
# module that owns provenance-mismatch semantics and treats this exact
# value, matched against an absent/None Qdrant field, as
# LEGACY_PROVENANCE_UNVERIFIED rather than PROVENANCE_MISMATCH).
LEGACY_PROVENANCE_LABEL = reconciliation.LEGACY_PROVENANCE_LABEL


def _group_legacy_points(points):
    by_hash = defaultdict(list)
    no_hash = []

    for point in points:
        if "is_active" in point.payload:
            continue  # H0.2/H0.4 lifecycle point -- not this script's concern

        document_hash = point.payload.get("document_hash")
        if not document_hash:
            no_hash.append(point)
            continue

        by_hash[document_hash].append(point)

    return by_hash, no_hash


def build_plan(pg_conn, by_hash, no_hash_points, processed_dir):
    ready = []
    refused = []
    already_registered = []

    source_file_hashes = defaultdict(set)
    for document_hash, points in by_hash.items():
        source_files = {p.payload.get("source_file") for p in points}
        if len(source_files) == 1:
            (source_file,) = source_files
            if source_file:
                source_file_hashes[source_file].add(document_hash)

    for point in no_hash_points:
        refused.append(
            {
                "reason": "MISSING_DOCUMENT_HASH",
                "point_id": str(point.id),
                "source_file": point.payload.get("source_file"),
            }
        )

    for document_hash in sorted(by_hash):
        points = by_hash[document_hash]

        if registry_db.get_by_hash(pg_conn, document_hash) is not None:
            already_registered.append(document_hash)
            continue

        source_files = {p.payload.get("source_file") for p in points}
        if len(source_files) != 1 or None in source_files:
            refused.append(
                {
                    "reason": "INCONSISTENT_SOURCE_FILE",
                    "document_hash": document_hash,
                    "source_files": sorted(s for s in source_files if s),
                }
            )
            continue
        (source_file,) = source_files

        conflicting_hashes = source_file_hashes.get(source_file, set())
        if len(conflicting_hashes) > 1:
            refused.append(
                {
                    "reason": "AMBIGUOUS_MULTIPLE_HASHES_FOR_SOURCE_FILE",
                    "document_hash": document_hash,
                    "source_file": source_file,
                    "conflicting_hashes": sorted(conflicting_hashes),
                }
            )
            continue

        expected_chunk_count = len(points)
        chunk_numbers = [p.payload.get("chunk_number") for p in points]
        if (
            any(n is None for n in chunk_numbers)
            or len(set(chunk_numbers)) != expected_chunk_count
            or set(chunk_numbers) != set(range(1, expected_chunk_count + 1))
        ):
            refused.append(
                {
                    "reason": "UNVERIFIABLE_CHUNK_COUNT",
                    "document_hash": document_hash,
                    "source_file": source_file,
                    "chunk_numbers": sorted(n for n in chunk_numbers if n is not None),
                    "point_count": len(points),
                }
            )
            continue

        archive_paths = {p.payload.get("archive_path") for p in points}
        if len(archive_paths) != 1:
            refused.append(
                {
                    "reason": "INCONSISTENT_ARCHIVE_PATH",
                    "document_hash": document_hash,
                    "source_file": source_file,
                    "archive_paths": sorted(a for a in archive_paths if a),
                }
            )
            continue
        (archive_path_field,) = archive_paths

        candidates = []
        if archive_path_field:
            candidates.append(Path(archive_path_field))
        fallback = processed_dir / source_file
        if fallback not in candidates:
            candidates.append(fallback)

        resolved_path = next((c for c in candidates if c.is_file()), None)
        if resolved_path is None:
            refused.append(
                {
                    "reason": "MISSING_ARCHIVE_FILE",
                    "document_hash": document_hash,
                    "source_file": source_file,
                    "attempted_paths": [str(c) for c in candidates],
                }
            )
            continue

        actual_hash = archive_integrity.file_hash(resolved_path)
        if actual_hash != document_hash:
            refused.append(
                {
                    "reason": "ARCHIVED_FILE_HASH_MISMATCH",
                    "document_hash": document_hash,
                    "source_file": source_file,
                    "archive_source_location": str(resolved_path),
                    "actual_sha256": actual_hash,
                }
            )
            continue

        provenance = {}
        inconsistent = False
        for field in PROVENANCE_FIELDS:
            values = {p.payload.get(field) for p in points}
            if len(values) != 1:
                refused.append(
                    {
                        "reason": "INCONSISTENT_PROVENANCE",
                        "document_hash": document_hash,
                        "source_file": source_file,
                        "field": field,
                        "values": sorted(str(v) for v in values),
                    }
                )
                inconsistent = True
                break
            (value,) = values
            provenance[field] = value if value else LEGACY_PROVENANCE_LABEL

        if inconsistent:
            continue

        ready.append(
            {
                "document_id": source_file,
                "document_version": 1,
                "document_hash": document_hash,
                "archive_source_location": str(resolved_path),
                "source_path": str(resolved_path),
                "expected_chunk_count": expected_chunk_count,
                "pipeline_version": provenance["pipeline_version"],
                "embedding_model": provenance["embedding_model"],
                "chunker_version": provenance["chunker_version"],
                "is_active": True,
                "superseded_by": None,
                "deactivated_at": None,
            }
        )

    return {
        "ready": ready,
        "refused": refused,
        "already_registered": sorted(already_registered),
    }


def apply_plan(pg_conn, ready):
    registered = []
    failed = []

    for entry in ready:
        try:
            registry_db.register_document_version(pg_conn, **entry)
            pg_conn.commit()
            registered.append(entry["document_hash"])
        except Exception as error:
            pg_conn.rollback()
            failed.append({"document_hash": entry["document_hash"], "error": str(error)})

    return registered, failed


def print_report(plan):
    print("== H0.4 legacy registry bootstrap: plan ==")

    print(f"READY_TO_REGISTER: {len(plan['ready'])}")
    for entry in plan["ready"]:
        print(
            f"  READY: document_id={entry['document_id']} "
            f"document_hash={entry['document_hash']} "
            f"chunks={entry['expected_chunk_count']} "
            f"archive={entry['archive_source_location']} "
            f"pipeline_version={entry['pipeline_version']} "
            f"embedding_model={entry['embedding_model']} "
            f"chunker_version={entry['chunker_version']}"
        )

    print(f"ALREADY_REGISTERED: {len(plan['already_registered'])}")
    for document_hash in plan["already_registered"]:
        print(f"  ALREADY_REGISTERED: document_hash={document_hash}")

    print(f"REFUSED: {len(plan['refused'])}")
    for item in plan["refused"]:
        print(f"  REFUSED[{item['reason']}]: {item}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--processed-dir", default=str(PROCESSED))
    parser.add_argument(
        "--page-size", type=int, default=reconciliation.DEFAULT_SCROLL_PAGE_SIZE
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write verified legacy groups to public.document_registry. "
            "Omit this flag (the default) to only print the plan -- no "
            "writes, ever, without this flag."
        ),
    )
    args = parser.parse_args(argv)

    qdrant_client = QdrantClient(url=args.qdrant_url)
    pg_conn = registry_db.get_connection()

    try:
        points = reconciliation.all_points(
            qdrant_client, args.collection, page_size=args.page_size
        )
        by_hash, no_hash_points = _group_legacy_points(points)
        plan = build_plan(pg_conn, by_hash, no_hash_points, Path(args.processed_dir))

        print_report(plan)

        if args.apply:
            print()
            print("== APPLYING: writing verified groups to public.document_registry ==")
            registered, failed = apply_plan(pg_conn, plan["ready"])
            for document_hash in registered:
                print(f"REGISTERED: {document_hash}")
            for failure in failed:
                print(f"REGISTER FAILED: {failure['document_hash']} :: {failure['error']}")
            print(f"REGISTERED_COUNT: {len(registered)}")
            print(f"REGISTER_FAILED_COUNT: {len(failed)}")
            return 1 if failed else 0

        print()
        print(
            "DRY RUN ONLY -- no rows written. Re-run with --apply to write "
            "the READY groups above."
        )
        return 0
    finally:
        pg_conn.close()


if __name__ == "__main__":
    sys.exit(main())
