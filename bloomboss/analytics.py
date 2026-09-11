from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import PlantStatus, PlantUnit, Sale


def _money_sum(values):
    total = Decimal("0")
    known = False
    for value in values:
        if value is not None:
            total += value
            known = True
    return total if known else None


def summarize_business(units: Iterable[PlantUnit], sales: Iterable[Sale]) -> dict:
    units = list(units)
    sales = list(sales)
    sales_by_unit = {sale.unit_id: sale for sale in sales}

    revenue = _money_sum(s.sale_price for s in sales)
    landed_cost = _money_sum(u.allocated_landed_cost for u in units)

    realized_profit_values = []
    for unit in units:
        sale = sales_by_unit.get(unit.unit_id)
        if sale and unit.allocated_landed_cost is not None:
            realized_profit_values.append(sale.sale_price - unit.allocated_landed_cost)
    realized_gross_profit = _money_sum(realized_profit_values)

    sold_count = sum(1 for u in units if u.status == PlantStatus.SOLD or u.unit_id in sales_by_unit)
    lost_count = sum(1 for u in units if u.status == PlantStatus.LOST)
    total_units = len(units)

    sell_through = (Decimal(sold_count) / Decimal(total_units)) if total_units else None
    loss_rate = (Decimal(lost_count) / Decimal(total_units)) if total_units else None
    avg_sale_price = (revenue / Decimal(len(sales))) if sales and revenue is not None else None

    days_to_sale = []
    for unit in units:
        sale = sales_by_unit.get(unit.unit_id)
        if sale and unit.acquired_date and sale.sale_date:
            days_to_sale.append((sale.sale_date - unit.acquired_date).days)
    avg_days_to_sale = (sum(days_to_sale) / len(days_to_sale)) if days_to_sale else None

    by_channel = defaultdict(lambda: {"sales": 0, "revenue": Decimal("0")})
    for sale in sales:
        by_channel[sale.channel]["sales"] += 1
        by_channel[sale.channel]["revenue"] += sale.sale_price

    by_cultivar = defaultdict(lambda: {"units": 0, "sold": 0, "lost": 0, "revenue": Decimal("0")})
    for unit in units:
        bucket = by_cultivar[unit.cultivar]
        bucket["units"] += 1
        if unit.status == PlantStatus.LOST:
            bucket["lost"] += 1
        sale = sales_by_unit.get(unit.unit_id)
        if sale:
            bucket["sold"] += 1
            bucket["revenue"] += sale.sale_price

    return {
        "unit_count": total_units,
        "sale_count": len(sales),
        "total_revenue": revenue,
        "known_landed_cost": landed_cost,
        "realized_gross_profit_on_known_costs": realized_gross_profit,
        "sell_through_rate": sell_through,
        "loss_rate": loss_rate,
        "average_realized_sale_price": avg_sale_price,
        "average_days_to_sale": avg_days_to_sale,
        "by_channel": dict(by_channel),
        "by_cultivar": dict(by_cultivar),
    }
