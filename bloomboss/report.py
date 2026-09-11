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
    """Convert a snapshot value to deterministic JSON-safe primitives."""
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
    """Return a stable, human-inspectable report without changing source data."""
    return {
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
        },
        "business_summary": _json_value(snapshot.business_summary),
        "supplier_summary": _json_value(snapshot.supplier_summary),
        "quality_summary": _json_value(snapshot.quality_summary),
        "relationship_issues": _json_value(snapshot.relationship_issues),
    }


def render_history_report(path: str | Path) -> str:
    """Inspect a canonical CSV and render deterministic pretty JSON."""
    report = snapshot_report(inspect_history_csv(path))
    return json.dumps(report, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect BloomBoss historical CSV data without modifying it."
    )
    parser.add_argument("source", help="Path to the canonical BloomBoss history CSV")
    args = parser.parse_args(argv)
    print(render_history_report(args.source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
