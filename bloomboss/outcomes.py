from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import PlantStatus, PlantUnit, Sale


def _matched_outcome_bucket() -> dict:
    return {
        "units": 0,
        "sold": 0,
        "lost": 0,
        "revenue": Decimal("0"),
        "sold_units_with_known_cost": 0,
        "realized_revenue_on_known_costs": Decimal("0"),
        "realized_profit_on_known_costs": Decimal("0"),
        "known_cost_lost": Decimal("0"),
        "lost_units_with_known_cost": 0,
        "days_to_sale": [],
    }


def _finalize(bucket: dict) -> dict:
    units = bucket["units"]
    sold_with_cost = bucket["sold_units_with_known_cost"]
    lost_with_cost = bucket["lost_units_with_known_cost"]
    matched_revenue = bucket["realized_revenue_on_known_costs"]
    matched_profit = bucket["realized_profit_on_known_costs"]
    days = bucket.pop("days_to_sale")
    bucket["sell_through_rate"] = Decimal(bucket["sold"]) / Decimal(units) if units else None
    bucket["loss_rate"] = Decimal(bucket["lost"]) / Decimal(units) if units else None
    bucket["realized_revenue_on_known_costs"] = matched_revenue if sold_with_cost else None
    bucket["realized_profit_on_known_costs"] = matched_profit if sold_with_cost else None
    bucket["realized_gross_margin_on_known_costs"] = (
        matched_profit / matched_revenue if sold_with_cost and matched_revenue != 0 else None
    )
    bucket["known_cost_lost"] = bucket["known_cost_lost"] if lost_with_cost else None
    bucket["average_days_to_sale"] = sum(days) / len(days) if days else None
    return bucket


def summarize_cultivars(units: Iterable[PlantUnit], sales: Iterable[Sale]) -> dict:
    """Compare cultivar economics using only matched known cost facts."""
    units = list(units)
    sale_by_unit = {sale.unit_id: sale for sale in sales}
    buckets = defaultdict(_matched_outcome_bucket)

    for unit in units:
        bucket = buckets[unit.cultivar]
        bucket["units"] += 1
        sale = sale_by_unit.get(unit.unit_id)
        if unit.status == PlantStatus.LOST:
            bucket["lost"] += 1
            if unit.allocated_landed_cost is not None:
                bucket["known_cost_lost"] += unit.allocated_landed_cost
                bucket["lost_units_with_known_cost"] += 1
        if sale:
            bucket["sold"] += 1
            bucket["revenue"] += sale.sale_price
            if unit.allocated_landed_cost is not None:
                bucket["sold_units_with_known_cost"] += 1
                bucket["realized_revenue_on_known_costs"] += sale.sale_price
                bucket["realized_profit_on_known_costs"] += sale.sale_price - unit.allocated_landed_cost
            if unit.acquired_date and sale.sale_date:
                bucket["days_to_sale"].append((sale.sale_date - unit.acquired_date).days)

    return {name: _finalize(bucket) for name, bucket in buckets.items()}


def summarize_channels(units: Iterable[PlantUnit], sales: Iterable[Sale]) -> dict:
    """Compare realized channel outcomes without imputing missing cost basis."""
    units_by_id = {unit.unit_id: unit for unit in units}
    buckets = defaultdict(_matched_outcome_bucket)

    for sale in sales:
        bucket = buckets[sale.channel]
        bucket["sold"] += 1
        bucket["units"] += 1
        bucket["revenue"] += sale.sale_price
        unit = units_by_id.get(sale.unit_id)
        if unit and unit.allocated_landed_cost is not None:
            bucket["sold_units_with_known_cost"] += 1
            bucket["realized_revenue_on_known_costs"] += sale.sale_price
            bucket["realized_profit_on_known_costs"] += sale.sale_price - unit.allocated_landed_cost
        if unit and unit.acquired_date and sale.sale_date:
            bucket["days_to_sale"].append((sale.sale_date - unit.acquired_date).days)

    result = {}
    for channel, bucket in buckets.items():
        bucket["average_realized_sale_price"] = (
            bucket["revenue"] / Decimal(bucket["sold"]) if bucket["sold"] else None
        )
        result[channel] = _finalize(bucket)
    return result
