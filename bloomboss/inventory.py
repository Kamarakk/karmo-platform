from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from .models import PlantStatus, PlantUnit, Sale


def _dataset_cutoff(units: list[PlantUnit], sales: list[Sale]) -> date | None:
    """Return the latest known business date without consulting wall-clock time."""
    known_dates = [unit.acquired_date for unit in units if unit.acquired_date]
    known_dates.extend(sale.sale_date for sale in sales if sale.sale_date)
    return max(known_dates) if known_dates else None


def summarize_inventory_exposure(
    units: Iterable[PlantUnit], sales: Iterable[Sale]
) -> dict:
    """Show which unsold units still tie up known capital in the historical dataset.

    The analysis is deterministic: inventory age is measured only to the latest
    date present in the source dataset, never to today's date. Unknown cost or
    acquisition dates stay unknown rather than being inferred.
    """
    units = list(units)
    sales = list(sales)
    sold_unit_ids = {sale.unit_id for sale in sales}
    cutoff = _dataset_cutoff(units, sales)

    active_units = [
        unit
        for unit in units
        if unit.unit_id not in sold_unit_ids
        and unit.status not in (PlantStatus.SOLD, PlantStatus.LOST, PlantStatus.GIVEAWAY)
    ]

    rows = []
    known_capital = Decimal("0")
    known_cost_count = 0
    for unit in active_units:
        if unit.allocated_landed_cost is not None:
            known_capital += unit.allocated_landed_cost
            known_cost_count += 1

        days_held = None
        if cutoff is not None and unit.acquired_date is not None:
            days_held = (cutoff - unit.acquired_date).days

        rows.append(
            {
                "unit_id": unit.unit_id,
                "cultivar": unit.cultivar,
                "status": unit.status.value,
                "acquired_date": unit.acquired_date,
                "allocated_landed_cost": unit.allocated_landed_cost,
                "days_held_to_dataset_cutoff": days_held,
            }
        )

    def sort_key(row: dict) -> tuple:
        cost = row["allocated_landed_cost"]
        days = row["days_held_to_dataset_cutoff"]
        return (
            cost is None,
            -(cost or Decimal("0")),
            days is None,
            -(days or 0),
            row["unit_id"],
        )

    rows.sort(key=sort_key)

    return {
        "dataset_cutoff_date": cutoff,
        "active_inventory_units": len(active_units),
        "active_inventory_units_with_known_cost": known_cost_count,
        "active_inventory_units_with_unknown_cost": len(active_units) - known_cost_count,
        "known_capital_tied_up": known_capital if known_cost_count else None,
        "units": rows,
    }
