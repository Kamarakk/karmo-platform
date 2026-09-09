"""H0.4 registry integrity repair: construct a missing document_registry row
for an ORPHAN_VECTOR finding, strictly from the Qdrant payload's own
recorded metadata.

Scope: this is a report/apply CLI, not an ingest pipeline, and not a
replacement for bootstrap_legacy_registry.py. It targets exactly the gap
docs/evidence/h04/H04_INVARIANT_IMPACT_REVIEW.md documented as deferred,
future work: an H0.4-lifecycle document whose Qdrant upsert succeeded but
whose document_registry write did not (RegistryLifecycleError in
document_ingest_h04.py -- "INTEGRITY INCOMPLETE / REGISTRY FAILED"),
detected today, report-only, as ORPHAN_VECTOR by reconciliation.py /
auditor.py. It never converts a document, computes an embedding, or writes
or modifies a Qdrant point -- it only reads existing document_registry rows
(read-only, via registry_db.list_registry / get_by_hash), reads existing
Qdrant points for orphaned document_hash values (read-only .scroll(), via
reconciliation.find_orphan_vectors / actual_chunk_points), reads existing
archived files on disk to recompute their SHA-256 (via
archive_integrity.file_hash), and, only when explicitly asked, inserts new
rows into public.document_registry via
registry_db.register_document_version. It never issues an UPDATE or DELETE
against an existing registry row, and it never touches Qdrant.

Default behavior is report-only: running this script with no flags prints
the full plan (what would be registered, what is refused and why, what is
already registered) and writes nothing. Only --apply writes.

Distinct from bootstrap_legacy_registry.py: bootstrap targets legacy
(pre-H0.2) Qdrant points that never carried is_active/document_version at
all, and defaults every registered group to document_version=1 because
there is no prior version to number against. This tool targets normal
H0.4-lifecycle points -- they already carry is_active, document_version,
pipeline_version, embedding_model, chunker_version, and archive_path on
every point payload, written verbatim by document_ingest_h04.py at ingest
time (see that module's ingest_document) -- so this tool never assumes
version 1 and never falls back to a legacy-provenance label: every field
the registry row needs must already be present, consistent, and verifiable
on the orphaned points themselves, or the group is refused. A genuinely
legacy point (no is_active key at all) that somehow reaches this tool is
refused (INCONSISTENT_IS_ACTIVE, since payload.get("is_active") is None),
never mis-registered -- that case remains bootstrap_legacy_registry.py's
separate scope.

Grouping and verification, per orphaned document_hash:

1. Every point in the group must agree on a single document_id
   (INCONSISTENT_DOCUMENT_ID) and a single document_version
   (INCONSISTENT_DOCUMENT_VERSION) -- disagreement means the group itself
   is internally inconsistent data and is refused, not guessed at.
2. The group's chunk_number values must form exactly {1..N} with no gaps
   and no duplicates (N = point count) -- otherwise expected_chunk_count
   cannot be verified (UNVERIFIABLE_CHUNK_COUNT).
3. Every point must carry the same non-null archive_path
   (MISSING_ARCHIVE_PATH if absent, INCONSISTENT_ARCHIVE_PATH if the group
   disagrees) -- taken strictly from the payload's own archive_path field,
   never guessed from document_id or a processed-directory fallback. If a
   point also carries source_path, it must agree with archive_path
   (INCONSISTENT_SOURCE_PATH) -- document_ingest_h04.py always writes both
   fields to the same value for a normal ingest, so disagreement is itself
   a sign the group is not what it appears to be.
4. The archived file at that archive_path must exist (MISSING_ARCHIVE_FILE)
   and its recomputed SHA-256 must equal the document_hash
   (ARCHIVED_FILE_HASH_MISMATCH).
5. pipeline_version/embedding_model/chunker_version must each be a single
   non-null, agreeing value across every point in the group
   (MISSING_PROVENANCE_FIELD if any point lacks the field,
   INCONSISTENT_PROVENANCE if points disagree) -- used verbatim, never
   defaulted or fabricated. Unlike bootstrap_legacy_registry.py, there is no
   legacy-label fallback here.
6. is_active must be a single agreeing value across the group
   (INCONSISTENT_IS_ACTIVE). When is_active is False, deactivated_at must
   also be a single, non-null, agreeing value (MISSING_DEACTIVATED_AT) --
   the same constraint public.document_registry itself enforces
   (document_registry_deactivated_state_check) -- and superseded_by, if
   present on any point, must agree across the group
   (INCONSISTENT_SUPERSEDED_BY).
7. A document_hash already present in document_registry (re-checked here,
   not only inferred from the orphan-finding step that selected it) is
   reported as ALREADY_REGISTERED and skipped -- never re-inserted, never
   updated. Matters because repair may be re-run after a partial apply or
   after something else has since closed the gap (I-04).
8. A point with no document_hash at all is refused (MISSING_DOCUMENT_HASH)
   -- it cannot be registered under any hash.

Every group that is registered uses exactly the document_id,
document_version, is_active, superseded_by, deactivated_at, and provenance
fields already agreed by its own points -- nothing here invents a value
document_ingest_h04.py did not already write.
"""

import argparse
import sys
from pathlib import Path

from qdrant_client import QdrantClient

import archive_integrity
import reconciliation
import registry_db

COLLECTION_NAME = "karmo_documents"
QDRANT_URL = "http://127.0.0.1:6333"

PROVENANCE_FIELDS = ("pipeline_version", "embedding_model", "chunker_version")


def _orphan_document_hashes(qdrant_client, collection_name, known_hashes, *, page_size):
    orphan_findings = reconciliation.find_orphan_vectors(
        qdrant_client, collection_name, known_hashes, page_size=page_size
    )
    hashless = [f for f in orphan_findings if not f["document_hash"]]
    hashes = sorted({f["document_hash"] for f in orphan_findings if f["document_hash"]})
    return hashes, hashless


def build_plan(
    pg_conn,
    qdrant_client,
    collection_name,
    known_hashes,
    *,
    page_size=reconciliation.DEFAULT_SCROLL_PAGE_SIZE,
):
    ready = []
    refused = []
    already_registered = []

    orphan_hashes, hashless_findings = _orphan_document_hashes(
        qdrant_client, collection_name, known_hashes, page_size=page_size
    )

    for finding in hashless_findings:
        refused.append(
            {
                "reason": "MISSING_DOCUMENT_HASH",
                "point_id": finding["point_id"],
                "document_id": finding.get("document_id"),
            }
        )

    for document_hash in orphan_hashes:
        if registry_db.get_by_hash(pg_conn, document_hash) is not None:
            already_registered.append(document_hash)
            continue

        points = reconciliation.actual_chunk_points(
            qdrant_client, collection_name, document_hash, page_size=page_size
        )
        if not points:
            # Named as an orphan by the detecting read, but nothing is
            # actually here to repair from any more this run (e.g. deleted
            # in between) -- not actionable, not a refusal either.
            continue

        document_ids = {p.payload.get("document_id") for p in points}
        if len(document_ids) != 1 or None in document_ids:
            refused.append(
                {
                    "reason": "INCONSISTENT_DOCUMENT_ID",
                    "document_hash": document_hash,
                    "document_ids": sorted(d for d in document_ids if d),
                }
            )
            continue
        (document_id,) = document_ids

        document_versions = {p.payload.get("document_version") for p in points}
        if len(document_versions) != 1 or None in document_versions:
            refused.append(
                {
                    "reason": "INCONSISTENT_DOCUMENT_VERSION",
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "document_versions": sorted(
                        v for v in document_versions if v is not None
                    ),
                }
            )
            continue
        (document_version,) = document_versions

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
                    "document_id": document_id,
                    "chunk_numbers": sorted(n for n in chunk_numbers if n is not None),
                    "point_count": len(points),
                }
            )
            continue

        archive_paths = {p.payload.get("archive_path") for p in points}
        if len(archive_paths) != 1 or None in archive_paths or "" in archive_paths:
            refused.append(
                {
                    "reason": (
                        "MISSING_ARCHIVE_PATH"
                        if archive_paths <= {None, ""}
                        else "INCONSISTENT_ARCHIVE_PATH"
                    ),
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "archive_paths": sorted(a for a in archive_paths if a),
                }
            )
            continue
        (archive_path_field,) = archive_paths

        source_paths = {
            p.payload.get("source_path") for p in points if p.payload.get("source_path")
        }
        if source_paths and source_paths != {archive_path_field}:
            refused.append(
                {
                    "reason": "INCONSISTENT_SOURCE_PATH",
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "archive_path": archive_path_field,
                    "source_paths": sorted(source_paths),
                }
            )
            continue

        resolved_path = Path(archive_path_field)
        if not resolved_path.is_file():
            refused.append(
                {
                    "reason": "MISSING_ARCHIVE_FILE",
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "archive_source_location": str(resolved_path),
                }
            )
            continue

        actual_hash = archive_integrity.file_hash(resolved_path)
        if actual_hash != document_hash:
            refused.append(
                {
                    "reason": "ARCHIVED_FILE_HASH_MISMATCH",
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "archive_source_location": str(resolved_path),
                    "actual_sha256": actual_hash,
                }
            )
            continue

        provenance = {}
        inconsistent = False
        for field in PROVENANCE_FIELDS:
            values = {p.payload.get(field) for p in points}
            if None in values:
                refused.append(
                    {
                        "reason": "MISSING_PROVENANCE_FIELD",
                        "document_hash": document_hash,
                        "document_id": document_id,
                        "field": field,
                    }
                )
                inconsistent = True
                break
            if len(values) != 1:
                refused.append(
                    {
                        "reason": "INCONSISTENT_PROVENANCE",
                        "document_hash": document_hash,
                        "document_id": document_id,
                        "field": field,
                        "values": sorted(str(v) for v in values),
                    }
                )
                inconsistent = True
                break
            (value,) = values
            provenance[field] = value

        if inconsistent:
            continue

        is_active_values = {p.payload.get("is_active") for p in points}
        if len(is_active_values) != 1 or None in is_active_values:
            refused.append(
                {
                    "reason": "INCONSISTENT_IS_ACTIVE",
                    "document_hash": document_hash,
                    "document_id": document_id,
                    "is_active_values": sorted(str(v) for v in is_active_values),
                }
            )
            continue
        (is_active,) = is_active_values

        deactivated_at = None
        superseded_by = None
        if not is_active:
            deactivated_ats = {p.payload.get("deactivated_at") for p in points}
            if len(deactivated_ats) != 1 or None in deactivated_ats:
                refused.append(
                    {
                        "reason": "MISSING_DEACTIVATED_AT",
                        "document_hash": document_hash,
                        "document_id": document_id,
                    }
                )
                continue
            (deactivated_at,) = deactivated_ats

            superseded_bys = {
                p.payload.get("superseded_by")
                for p in points
                if p.payload.get("superseded_by")
            }
            if len(superseded_bys) > 1:
                refused.append(
                    {
                        "reason": "INCONSISTENT_SUPERSEDED_BY",
                        "document_hash": document_hash,
                        "document_id": document_id,
                        "superseded_by_values": sorted(superseded_bys),
                    }
                )
                continue
            superseded_by = next(iter(superseded_bys), None)

        ready.append(
            {
                "document_id": document_id,
                "document_version": document_version,
                "document_hash": document_hash,
                "archive_source_location": archive_path_field,
                "source_path": archive_path_field,
                "expected_chunk_count": expected_chunk_count,
                "pipeline_version": provenance["pipeline_version"],
                "embedding_model": provenance["embedding_model"],
                "chunker_version": provenance["chunker_version"],
                "is_active": is_active,
                "superseded_by": superseded_by,
                "deactivated_at": deactivated_at,
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
    print("== H0.4 registry integrity repair: plan ==")

    print(f"READY_TO_REGISTER: {len(plan['ready'])}")
    for entry in plan["ready"]:
        print(
            f"  READY: document_id={entry['document_id']} "
            f"document_version={entry['document_version']} "
            f"document_hash={entry['document_hash']} "
            f"chunks={entry['expected_chunk_count']} "
            f"is_active={entry['is_active']} "
            f"archive={entry['archive_source_location']}"
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
    parser.add_argument(
        "--page-size", type=int, default=reconciliation.DEFAULT_SCROLL_PAGE_SIZE
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write verified orphan groups to public.document_registry. "
            "Omit this flag (the default) to only print the plan -- no "
            "writes, ever, without this flag."
        ),
    )
    args = parser.parse_args(argv)

    qdrant_client = QdrantClient(url=args.qdrant_url)
    pg_conn = registry_db.get_connection()

    try:
        known_hashes = {row["document_hash"] for row in registry_db.list_registry(pg_conn)}
        plan = build_plan(
            pg_conn, qdrant_client, args.collection, known_hashes, page_size=args.page_size
        )

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
