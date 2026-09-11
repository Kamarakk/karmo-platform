from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import ListingHistoryEvent, PlantStatus, PlantUnit, PurchaseBatch, Sale


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
    units_by_batch: dict[str, list[PlantUnit]] = {}
    sales_by_unit: dict[str, list[Sale]] = {}

    for unit in units:
        units_by_batch.setdefault(unit.batch_id, []).append(unit)
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

    for batch in batches:
        if batch.quantity is None:
            continue
        reconstructed_units = len(units_by_batch.get(batch.batch_id, []))
        if reconstructed_units != batch.quantity:
            issues.append(
                ValidationIssue(
                    "BATCH_QUANTITY_RECONSTRUCTION_GAP",
                    batch.batch_id,
                    (
                        f"batch quantity is {batch.quantity}, but historical reconstruction "
                        f"contains {reconstructed_units} inventory unit records"
                    ),
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


def validate_listing_relationships(
    listings: Iterable[ListingHistoryEvent],
    units: Iterable[PlantUnit],
    sales: Iterable[Sale],
) -> list[ValidationIssue]:
    """Validate listing evidence against canonical inventory/sale facts.

    Listing history remains a separate evidence stream. This function only
    reports unambiguous cross-record contradictions: broken unit references,
    a listing that starts before a known acquisition date, or a listing that
    starts after a known sale date. Unknown dates remain valid unknowns.
    """
    listings = list(listings)
    units = list(units)
    sales = list(sales)

    issues: list[ValidationIssue] = []
    unit_by_id = {unit.unit_id: unit for unit in units}
    sale_dates_by_unit: dict[str, list] = {}
    for sale in sales:
        if sale.sale_date is not None:
            sale_dates_by_unit.setdefault(sale.unit_id, []).append(sale.sale_date)

    for listing in listings:
        unit = unit_by_id.get(listing.unit_id)
        if unit is None:
            issues.append(
                ValidationIssue(
                    "LISTING_UNIT_MISSING",
                    listing.listing_id,
                    f"listing references missing unit {listing.unit_id!r}",
                )
            )
            continue

        if (
            listing.listed_date is not None
            and unit.acquired_date is not None
            and listing.listed_date < unit.acquired_date
        ):
            issues.append(
                ValidationIssue(
                    "LISTING_BEFORE_ACQUISITION",
                    listing.listing_id,
                    "listing date is earlier than the unit acquisition date",
                )
            )

        if listing.listed_date is not None:
            known_sale_dates = sale_dates_by_unit.get(listing.unit_id, [])
            if known_sale_dates and listing.listed_date > min(known_sale_dates):
                issues.append(
                    ValidationIssue(
                        "LISTING_AFTER_SALE",
                        listing.listing_id,
                        "listing date is later than the unit's known sale date",
                    )
                )

    return issues