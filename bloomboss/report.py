from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .history import HistoricalImportSnapshot, inspect_history_csv


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def snapshot_report(snapshot: HistoricalImportSnapshot) -> dict[str, Any]:
    report = {
        "source": {
            "name": snapshot.source_name,
            "sha256": snapshot.source_sha256,
            "size_bytes": snapshot.source_size_bytes,
        },
        "record_counts": {
            "batches": len(snapshot.batches),
            "units": len(snapshot.units),
            "sales": len(snapshot.sales),
            "relationship_issues": len(snapshot.relationship_issues),
            "listings": len(snapshot.listings),
            "listing_relationship_issues": len(snapshot.listing_relationship_issues),
            "propagations": len(snapshot.propagations),
            "propagation_relationship_issues": len(snapshot.propagation_relationship_issues),
        },
        "business_summary": _json_value(snapshot.business_summary),
        "supplier_summary": _json_value(snapshot.supplier_summary),
        "batch_summary": _json_value(snapshot.batch_summary),
        "unit_outcome_summary": _json_value(snapshot.unit_outcome_summary),
        "cultivar_summary": _json_value(snapshot.cultivar_summary),
        "channel_summary": _json_value(snapshot.channel_summary),
        "inventory_exposure_summary": _json_value(snapshot.inventory_exposure_summary),
        "decision_rankings": _json_value(snapshot.decision_rankings),
        "quality_summary": _json_value(snapshot.quality_summary),
        "relationship_issues": _json_value(snapshot.relationship_issues),
    }
    if snapshot.listing_source_name is not None:
        report["listing_source"] = {
            "name": snapshot.listing_source_name,
            "sha256": snapshot.listing_source_sha256,
            "size_bytes": snapshot.listing_source_size_bytes,
        }
        report["listing_quality_summary"] = _json_value(snapshot.listing_quality_summary)
        report["listing_activity_summary"] = _json_value(snapshot.listing_activity_summary)
        report["listing_relationship_issues"] = _json_value(snapshot.listing_relationship_issues)
    if snapshot.propagation_source_name is not None:
        report["propagation_source"] = {
            "name": snapshot.propagation_source_name,
            "sha256": snapshot.propagation_source_sha256,
            "size_bytes": snapshot.propagation_source_size_bytes,
        }
        report["propagations"] = _json_value(snapshot.propagations)
        report["propagation_relationship_issues"] = _json_value(
            snapshot.propagation_relationship_issues
        )
    return report


def render_history_report(
    path: str | Path,
    *,
    listing_path: str | Path | None = None,
    propagation_path: str | Path | None = None,
) -> str:
    report = snapshot_report(
        inspect_history_csv(
            path,
            listing_path=listing_path,
            propagation_path=propagation_path,
        )
    )
    return json.dumps(report, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect BloomBoss historical CSV data without modifying it.")
    parser.add_argument("source", help="Path to the canonical BloomBoss history CSV")
    parser.add_argument("--listings", help="Optional path to historical listing evidence CSV")
    parser.add_argument("--propagations", help="Optional path to historical propagation evidence CSV")
    args = parser.parse_args(argv)
    print(
        render_history_report(
            args.source,
            listing_path=args.listings,
            propagation_path=args.propagations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
