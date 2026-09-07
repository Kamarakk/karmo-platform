"""H0.4 auditor: report-only cross-store integrity check.

Orchestrates archive_integrity.py and reconciliation.py over every row in
the PostgreSQL document registry and the actual Qdrant collection state,
and returns a flat list of finding dicts.

REPORT-ONLY BY CONSTRUCTION: this module calls only read APIs --
registry_db.list_registry / list_by_document_id (SELECT), Qdrant .scroll
(read), and archive_integrity.check_archive (filesystem read). It contains
no UPDATE/DELETE/INSERT against document_registry, no upsert/set_payload/
delete against Qdrant, and no filesystem write. It must never gain such a
call: detecting and reporting inconsistencies is the full frozen H0.4
scope for this module. Automatic repair is out of scope by design.
"""

from collections import defaultdict

import archive_integrity
import reconciliation
import registry_db


def run_audit(pg_conn, qdrant_client, collection_name, *, page_size=reconciliation.DEFAULT_SCROLL_PAGE_SIZE):
    rows = registry_db.list_registry(pg_conn)
    known_hashes = {row["document_hash"] for row in rows}

    rows_by_document_id = defaultdict(list)
    for row in rows:
        rows_by_document_id[row["document_id"]].append(row)

    findings = []
    points_by_hash = {}

    for row in rows:
        identity = {
            "document_id": row["document_id"],
            "document_version": row["document_version"],
            "document_hash": row["document_hash"],
        }

        archive_finding = archive_integrity.check_archive(row)
        if archive_finding:
            findings.append({**archive_finding, **identity})

        points = reconciliation.actual_chunk_points(
            qdrant_client, collection_name, row["document_hash"], page_size=page_size
        )
        points_by_hash[row["document_hash"]] = points

        for finding in reconciliation.check_chunk_counts(row, points):
            findings.append({**finding, **identity})

        for finding in reconciliation.check_provenance(row, points):
            findings.append({**finding, **identity})

    findings.extend(
        reconciliation.find_orphan_vectors(
            qdrant_client, collection_name, known_hashes, page_size=page_size
        )
    )

    for document_id, doc_rows in rows_by_document_id.items():
        doc_points = []
        for row in doc_rows:
            doc_points.extend(points_by_hash[row["document_hash"]])
        findings.extend(
            reconciliation.check_active_version_state(document_id, doc_rows, doc_points)
        )

    return findings


def summarize(findings):
    counts = defaultdict(int)
    for finding in findings:
        counts[finding["type"]] += 1
    return dict(counts)
