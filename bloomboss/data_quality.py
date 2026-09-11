from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .models import ListingHistoryEvent, PlantStatus, PlantUnit, PurchaseBatch, Sale


def _ratio(known: int, total: int) -> Decimal | None:
    if total == 0:
        return None
    return Decimal(known) / Decimal(total)


def summarize_history_quality(
    batches: Iterable[PurchaseBatch],
    units: Iterable[PlantUnit],
    sales: Iterable[Sale],
) -> dict:
    """Report historical-data completeness without filling missing values."""
    batches = list(batches)
    units = list(units)
    sales = list(sales)
    sold_units = {sale.unit_id for sale in sales}

    batch_supplier_known = sum(1 for batch in batches if batch.supplier)
    batch_purchase_date_known = sum(1 for batch in batches if batch.purchase_date is not None)
    batch_quantity_known = sum(1 for batch in batches if batch.quantity is not None)
    batch_landed_cost_known = sum(1 for batch in batches if batch.known_landed_cost_total is not None)
    unit_cost_known = sum(1 for unit in units if unit.allocated_landed_cost is not None)
    unit_acquired_date_known = sum(1 for unit in units if unit.acquired_date is not None)
    unit_status_known = sum(1 for unit in units if unit.status != PlantStatus.UNKNOWN)
    sale_date_known = sum(1 for sale in sales if sale.sale_date is not None)
    sale_fees_known = sum(1 for sale in sales if sale.selling_fees is not None)
    sale_shipping_known = sum(1 for sale in sales if sale.shipping_cost is not None)
    sale_net_revenue_known = sum(1 for sale in sales if sale.known_net_revenue is not None)
    sold_units_with_cost = sum(1 for unit in units if unit.unit_id in sold_units and unit.allocated_landed_cost is not None)

    return {
        "batch_count": len(batches), "unit_count": len(units), "sale_count": len(sales),
        "coverage": {
            "batch_supplier": _ratio(batch_supplier_known, len(batches)),
            "batch_purchase_date": _ratio(batch_purchase_date_known, len(batches)),
            "batch_quantity": _ratio(batch_quantity_known, len(batches)),
            "batch_full_landed_cost": _ratio(batch_landed_cost_known, len(batches)),
            "unit_allocated_landed_cost": _ratio(unit_cost_known, len(units)),
            "unit_acquired_date": _ratio(unit_acquired_date_known, len(units)),
            "unit_status": _ratio(unit_status_known, len(units)),
            "sale_date": _ratio(sale_date_known, len(sales)),
            "sale_selling_fees": _ratio(sale_fees_known, len(sales)),
            "sale_outbound_shipping": _ratio(sale_shipping_known, len(sales)),
            "sale_net_revenue": _ratio(sale_net_revenue_known, len(sales)),
            "sold_unit_cost_basis": _ratio(sold_units_with_cost, len(sold_units)),
        },
        "missing_counts": {
            "batch_supplier": len(batches) - batch_supplier_known,
            "batch_purchase_date": len(batches) - batch_purchase_date_known,
            "batch_quantity": len(batches) - batch_quantity_known,
            "batch_full_landed_cost": len(batches) - batch_landed_cost_known,
            "unit_allocated_landed_cost": len(units) - unit_cost_known,
            "unit_acquired_date": len(units) - unit_acquired_date_known,
            "unit_status": len(units) - unit_status_known,
            "sale_date": len(sales) - sale_date_known,
            "sale_selling_fees": len(sales) - sale_fees_known,
            "sale_outbound_shipping": len(sales) - sale_shipping_known,
            "sale_net_revenue": len(sales) - sale_net_revenue_known,
            "sold_unit_cost_basis": len(sold_units) - sold_units_with_cost,
        },
    }


def summarize_listing_quality(listings: Iterable[ListingHistoryEvent]) -> dict:
    """Report completeness of optional listing evidence without inference."""
    listings = list(listings)
    listed_date_known = sum(1 for item in listings if item.listed_date is not None)
    unlisted_date_known = sum(1 for item in listings if item.unlisted_date is not None)
    asking_price_known = sum(1 for item in listings if item.asking_price is not None)
    total = len(listings)
    return {
        "listing_count": total,
        "coverage": {
            "listed_date": _ratio(listed_date_known, total),
            "unlisted_date": _ratio(unlisted_date_known, total),
            "asking_price": _ratio(asking_price_known, total),
        },
        "missing_counts": {
            "listed_date": total - listed_date_known,
            "unlisted_date": total - unlisted_date_known,
            "asking_price": total - asking_price_known,
        },
    }
