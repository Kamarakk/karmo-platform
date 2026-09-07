"""H0.4 production auditor entry point.

Thin CLI wrapper around ``auditor.run_audit``: connects to PostgreSQL using
the existing ``KARMO_DB_PASSWORD`` handling in ``registry_db.py``, reads
``public.document_registry`` (SELECT only), reads the ``karmo_documents``
Qdrant collection (``.scroll()`` only), and prints a concise summary.

This entry point performs no remediation. It calls only
``registry_db.list_registry`` (SELECT) and ``auditor.run_audit``, which is
itself report-only by construction (see ``auditor.py``'s module docstring
and ``test_auditor_is_report_only`` in the frozen H0.4 acceptance suite) --
no PostgreSQL UPDATE/DELETE/INSERT and no Qdrant upsert/set_payload/delete
is reachable from this file, directly or transitively.

Exit code: LEGACY_PROVENANCE_UNVERIFIED findings (see
``reconciliation.check_provenance``) are the explicitly-known, honest state
of a pre-H0.2 vector bootstrapped with the legacy provenance label -- not a
real disagreement -- so they never affect the exit code and are never
suppressed from output. Exit code is 0 when there are no findings of any
OTHER type, including when LEGACY_PROVENANCE_UNVERIFIED findings are the
only findings present (STATUS: CLEAN, or STATUS: CLEAN_WITH_KNOWN_LEGACY_GAPS
when that count is nonzero); 1 when at least one non-legacy integrity
finding is present (STATUS: INTEGRITY_FINDINGS_PRESENT). Both counts are
always printed/included, never hidden behind the exit code. An unhandled
connection/setup error (e.g. KARMO_DB_PASSWORD unset, Qdrant unreachable)
still exits nonzero via the normal Python traceback -- that is a distinct
failure mode from "integrity findings were present," not this script's
remediation concern either way.
"""

import argparse
import json
import sys

from qdrant_client import QdrantClient

import auditor
import reconciliation
import registry_db

COLLECTION_NAME = "karmo_documents"
QDRANT_URL = "http://127.0.0.1:6333"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument(
        "--page-size", type=int, default=reconciliation.DEFAULT_SCROLL_PAGE_SIZE
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full findings list as JSON instead of a text summary.",
    )
    args = parser.parse_args(argv)

    qdrant_client = QdrantClient(url=args.qdrant_url)
    pg_conn = registry_db.get_connection()

    try:
        registry_rows = registry_db.list_registry(pg_conn)
        findings = auditor.run_audit(
            pg_conn, qdrant_client, args.collection, page_size=args.page_size
        )
        summary = auditor.summarize(findings)

        legacy_unverified = [f for f in findings if f["type"] == "LEGACY_PROVENANCE_UNVERIFIED"]
        integrity_findings = [f for f in findings if f["type"] != "LEGACY_PROVENANCE_UNVERIFIED"]

        if integrity_findings:
            status = "INTEGRITY_FINDINGS_PRESENT"
        elif legacy_unverified:
            status = "CLEAN_WITH_KNOWN_LEGACY_GAPS"
        else:
            status = "CLEAN"

        if args.json:
            print(
                json.dumps(
                    {
                        "collection": args.collection,
                        "registry_row_count": len(registry_rows),
                        "finding_count": len(findings),
                        "legacy_provenance_unverified_count": len(legacy_unverified),
                        "integrity_finding_count": len(integrity_findings),
                        "status": status,
                        "summary": summary,
                        "findings": findings,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            print("== H0.4 production integrity audit (report-only) ==")
            print(f"COLLECTION: {args.collection}")
            print(f"REGISTRY_ROWS: {len(registry_rows)}")
            print(f"TOTAL_FINDINGS: {len(findings)}")
            for finding_type in sorted(summary):
                print(f"  {finding_type}: {summary[finding_type]}")
            print(f"LEGACY_PROVENANCE_UNVERIFIED_COUNT: {len(legacy_unverified)}")
            print(f"INTEGRITY_FINDING_COUNT: {len(integrity_findings)}")
            print(f"STATUS: {status}")

        return 1 if integrity_findings else 0
    finally:
        pg_conn.close()


if __name__ == "__main__":
    sys.exit(main())
