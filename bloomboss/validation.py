from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import PlantStatus, PlantUnit, PurchaseBatch, Sale


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    entity_id: str
    message: str


def validate_history_relationships(
    batches: Iterable[PurchaseBatch],
    units: Iterable[PlantUnit],
    sales: Iterable[Sale],
) -> list[ValidationIssue]:
    """Validate relationships between canonical historical records.

    Historical blanks remain valid unknowns. This validator only reports
    contradictions or broken references that would make analytics misleading.
    It performs no writes and does not repair data automatically.
    """
    batches = list(batches)
    units = list(units)
    sales = list(sales)

    issues: list[ValidationIssue] = []
    batch_by_id = {batch.batch_id: batch for batch in batches}
    unit_by_id = {unit.unit_id: unit for unit in units}
    sales_by_unit: dict[str, list[Sale]] = {}

    for unit in units:
        batch = batch_by_id.get(unit.batch_id)
        if batch is None:
            issues.append(
                ValidationIssue(
                    "UNIT_BATCH_MISSING",
                    unit.unit_id,
                    f"unit references missing batch {unit.batch_id!r}",
                )
            )
        elif batch.cultivar != unit.cultivar:
            issues.append(
                ValidationIssue(
                    "CULTIVAR_CONFLICT",
                    unit.unit_id,
                    f"unit cultivar {unit.cultivar!r} conflicts with batch cultivar {batch.cultivar!r}",
                )
            )

    for sale in sales:
        unit = unit_by_id.get(sale.unit_id)
        if unit is None:
            issues.append(
                ValidationIssue(
                    "SALE_UNIT_MISSING",
                    sale.sale_id,
                    f"sale references missing unit {sale.unit_id!r}",
                )
            )
            continue
        sales_by_unit.setdefault(sale.unit_id, []).append(sale)
        if unit.status in (PlantStatus.LOST, PlantStatus.GIVEAWAY):
            issues.append(
                ValidationIssue(
                    "SALE_STATUS_CONFLICT",
                    sale.sale_id,
                    f"sale exists for unit with status {unit.status.value!r}",
                )
            )
        if unit.acquired_date and sale.sale_date and sale.sale_date < unit.acquired_date:
            issues.append(
                ValidationIssue(
                    "SALE_BEFORE_ACQUISITION",
                    sale.sale_id,
                    "sale date is earlier than the unit acquisition date",
                )
            )

    for unit_id, unit_sales in sales_by_unit.items():
        if len(unit_sales) > 1:
            issues.append(
                ValidationIssue(
                    "MULTIPLE_SALES_FOR_UNIT",
                    unit_id,
                    f"unit has {len(unit_sales)} sale records",
                )
            )

    return issues
