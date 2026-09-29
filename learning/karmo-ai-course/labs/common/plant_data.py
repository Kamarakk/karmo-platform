"""Read-only access to your real BloomBoss unit data (the EMgarden invoice CSV).

Default location is your KARMO checkout. Override with:
    export BLOOMBOSS_CSV=/path/to/file.csv
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

DEFAULT_CSV = Path.home() / "KARMO-DEV/docs/bloomboss/historical_data/emgarden_invoice_2026040040.csv"
CSV_PATH = Path(os.environ.get("BLOOMBOSS_CSV", str(DEFAULT_CSV)))


def load_units() -> list:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(
            f"BloomBoss data not found at {CSV_PATH}. Set BLOOMBOSS_CSV to the CSV path."
        )
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def list_cultivars() -> list:
    return sorted({row["cultivar"] for row in load_units()})


def _money(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def cultivar_summary(cultivar: str) -> dict:
    """Counts, cost and sales for one cultivar. Partial names match (case-insensitive)."""
    wanted = (cultivar or "").strip().lower()
    rows = [r for r in load_units() if wanted and wanted in r["cultivar"].lower()]
    if not rows:
        return {"found": False, "cultivar": cultivar, "known_cultivars": list_cultivars()}
    sold = [r for r in rows if r["status"] == "sold"]
    by_status = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {
        "found": True,
        "cultivar": rows[0]["cultivar"],
        "units": len(rows),
        "by_status": by_status,
        "landed_cost_per_unit": round(_money(rows[0]["allocated_landed_cost"]), 2),
        "units_sold": len(sold),
        "revenue": round(sum(_money(r["sale_price"]) for r in sold), 2),
    }
