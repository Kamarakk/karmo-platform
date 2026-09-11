from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import PlantStatus, PlantUnit, PurchaseBatch, Sale


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
    realized_revenue_on_known_costs = Decimal("0")
    matched_sales_with_known_cost = 0
    for unit in units:
        sale = sales_by_unit.get(unit.unit_id)
        if sale and unit.allocated_landed_cost is not None:
            realized_profit_values.append(sale.sale_price - unit.allocated_landed_cost)
            realized_revenue_on_known_costs += sale.sale_price
            matched_sales_with_known_cost += 1
    realized_gross_profit = _money_sum(realized_profit_values)
    realized_gross_margin = (
        realized_gross_profit / realized_revenue_on_known_costs
        if realized_gross_profit is not None and realized_revenue_on_known_costs != 0
        else None
    )

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

    active_inventory = [
        unit
        for unit in units
        if unit.unit_id not in sales_by_unit
        and unit.status not in (PlantStatus.SOLD, PlantStatus.LOST, PlantStatus.GIVEAWAY)
    ]
    known_capital_tied_up = _money_sum(
        unit.allocated_landed_cost for unit in active_inventory
    )
    active_inventory_with_unknown_cost = sum(
        1 for unit in active_inventory if unit.allocated_landed_cost is None
    )

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
        "realized_revenue_on_known_costs": (
            realized_revenue_on_known_costs if matched_sales_with_known_cost else None
        ),
        "realized_gross_profit_on_known_costs": realized_gross_profit,
        "realized_gross_margin_on_known_costs": realized_gross_margin,
        "sell_through_rate": sell_through,
        "loss_rate": loss_rate,
        "average_realized_sale_price": avg_sale_price,
        "average_days_to_sale": avg_days_to_sale,
        "active_inventory_units": len(active_inventory),
        "known_capital_tied_up": known_capital_tied_up,
        "active_inventory_units_with_unknown_cost": active_inventory_with_unknown_cost,
        "by_channel": dict(by_channel),
        "by_cultivar": dict(by_cultivar),
    }


def summarize_suppliers(
    batches: Iterable[PurchaseBatch], units: Iterable[PlantUnit], sales: Iterable[Sale]
) -> dict:
    """Summarize supplier outcomes without inventing unknown cost or loss facts."""
    batches = list(batches)
    units = list(units)
    sales = list(sales)
    batch_by_id = {batch.batch_id: batch for batch in batches}
    sale_by_unit = {sale.unit_id: sale for sale in sales}

    suppliers = defaultdict(
        lambda: {
            "units": 0,
            "sold": 0,
            "lost": 0,
            "revenue": Decimal("0"),
            "known_unit_cost": Decimal("0"),
            "units_with_known_cost": 0,
            "realized_revenue_on_known_costs": Decimal("0"),
            "realized_known_cost_basis": Decimal("0"),
            "realized_profit_on_known_costs": Decimal("0"),
            "sold_units_with_known_cost": 0,
            "known_cost_lost": Decimal("0"),
            "lost_units_with_known_cost": 0,
            "days_to_sale": [],
        }
    )

    for unit in units:
        batch = batch_by_id.get(unit.batch_id)
        supplier = batch.supplier if batch and batch.supplier else "UNKNOWN"
        bucket = suppliers[supplier]
        bucket["units"] += 1
        if unit.allocated_landed_cost is not None:
            bucket["known_unit_cost"] += unit.allocated_landed_cost
            bucket["units_with_known_cost"] += 1
        if unit.status == PlantStatus.LOST:
            bucket["lost"] += 1
            if unit.allocated_landed_cost is not None:
                bucket["known_cost_lost"] += unit.allocated_landed_cost
                bucket["lost_units_with_known_cost"] += 1
        sale = sale_by_unit.get(unit.unit_id)
        if sale:
            bucket["sold"] += 1
            bucket["revenue"] += sale.sale_price
            if unit.allocated_landed_cost is not None:
                bucket["realized_revenue_on_known_costs"] += sale.sale_price
                bucket["realized_known_cost_basis"] += unit.allocated_landed_cost
                bucket["realized_profit_on_known_costs"] += sale.sale_price - unit.allocated_landed_cost
                bucket["sold_units_with_known_cost"] += 1
            if unit.acquired_date and sale.sale_date:
                bucket["days_to_sale"].append((sale.sale_date - unit.acquired_date).days)

    result = {}
    for supplier, bucket in suppliers.items():
        units_count = bucket["units"]
        sold_with_cost = bucket["sold_units_with_known_cost"]
        lost_with_cost = bucket["lost_units_with_known_cost"]
        matched_revenue = bucket["realized_revenue_on_known_costs"]
        matched_cost = bucket["realized_known_cost_basis"]
        matched_profit = bucket["realized_profit_on_known_costs"]
        lost_cost = bucket["known_cost_lost"]
        days_to_sale = bucket.pop("days_to_sale")

        bucket["sell_through_rate"] = (
            Decimal(bucket["sold"]) / Decimal(units_count) if units_count else None
        )
        bucket["loss_rate"] = (
            Decimal(bucket["lost"]) / Decimal(units_count) if units_count else None
        )
        bucket["realized_revenue_on_known_costs"] = matched_revenue if sold_with_cost else None
        bucket["realized_known_cost_basis"] = matched_cost if sold_with_cost else None
        bucket["realized_profit_on_known_costs"] = matched_profit if sold_with_cost else None
        bucket["realized_gross_margin_on_known_costs"] = (
            matched_profit / matched_revenue
            if sold_with_cost and matched_revenue != 0
            else None
        )
        bucket["realized_return_on_known_costs"] = (
            matched_profit / matched_cost
            if sold_with_cost and matched_cost != 0
            else None
        )
        bucket["known_cost_lost"] = lost_cost if lost_with_cost else None

        known_outcome_cost_basis = (
            (matched_cost if sold_with_cost else Decimal("0"))
            + (lost_cost if lost_with_cost else Decimal("0"))
        )
        known_outcome_net_profit = (
            (matched_profit if sold_with_cost else Decimal("0"))
            - (lost_cost if lost_with_cost else Decimal("0"))
        )
        has_known_outcome = bool(sold_with_cost or lost_with_cost)
        bucket["known_outcome_cost_basis"] = (
            known_outcome_cost_basis if has_known_outcome else None
        )
        bucket["known_outcome_net_profit"] = (
            known_outcome_net_profit if has_known_outcome else None
        )
        bucket["known_outcome_return_on_cost"] = (
            known_outcome_net_profit / known_outcome_cost_basis
            if has_known_outcome and known_outcome_cost_basis != 0
            else None
        )
        bucket["average_days_to_sale"] = (
            sum(days_to_sale) / len(days_to_sale) if days_to_sale else None
        )
        result[supplier] = bucket
    return result


def summarize_batches(
    batches: Iterable[PurchaseBatch], units: Iterable[PlantUnit], sales: Iterable[Sale]
) -> dict:
    """Expose purchase-level outcomes so losing batches are visible without imputation."""
    batches = list(batches)
    units = list(units)
    sales = list(sales)
    batch_by_id = {batch.batch_id: batch for batch in batches}
    sale_by_unit = {sale.unit_id: sale for sale in sales}

    result = {}
    for batch_id, batch in batch_by_id.items():
        batch_units = [unit for unit in units if unit.batch_id == batch_id]
        revenue = Decimal("0")
        realized_profit = Decimal("0")
        realized_revenue_on_known_costs = Decimal("0")
        realized_known_cost_basis = Decimal("0")
        lost_known_cost = Decimal("0")
        sold = 0
        lost = 0
        sold_with_known_cost = 0
        lost_with_known_cost = 0
        days_to_sale = []

        for unit in batch_units:
            sale = sale_by_unit.get(unit.unit_id)
            if unit.status == PlantStatus.LOST:
                lost += 1
                if unit.allocated_landed_cost is not None:
                    lost_known_cost += unit.allocated_landed_cost
                    lost_with_known_cost += 1
            if sale:
                sold += 1
                revenue += sale.sale_price
                if unit.allocated_landed_cost is not None:
                    realized_profit += sale.sale_price - unit.allocated_landed_cost
                    realized_revenue_on_known_costs += sale.sale_price
                    realized_known_cost_basis += unit.allocated_landed_cost
                    sold_with_known_cost += 1
                if unit.acquired_date and sale.sale_date:
                    days_to_sale.append((sale.sale_date - unit.acquired_date).days)

        unit_count = len(batch_units)
        known_outcome_cost_basis = (
            (realized_known_cost_basis if sold_with_known_cost else Decimal("0"))
            + (lost_known_cost if lost_with_known_cost else Decimal("0"))
        )
        known_outcome_net_profit = (
            (realized_profit if sold_with_known_cost else Decimal("0"))
            - (lost_known_cost if lost_with_known_cost else Decimal("0"))
        )
        has_known_outcome = bool(sold_with_known_cost or lost_with_known_cost)

        result[batch_id] = {
            "cultivar": batch.cultivar,
            "supplier": batch.supplier,
            "units": unit_count,
            "sold": sold,
            "lost": lost,
            "revenue": revenue,
            "sell_through_rate": Decimal(sold) / Decimal(unit_count) if unit_count else None,
            "loss_rate": Decimal(lost) / Decimal(unit_count) if unit_count else None,
            "known_landed_cost_total": batch.known_landed_cost_total,
            "sold_units_with_known_cost": sold_with_known_cost,
            "realized_revenue_on_known_costs": (
                realized_revenue_on_known_costs if sold_with_known_cost else None
            ),
            "realized_known_cost_basis": (
                realized_known_cost_basis if sold_with_known_cost else None
            ),
            "realized_profit_on_known_costs": (
                realized_profit if sold_with_known_cost else None
            ),
            "realized_gross_margin_on_known_costs": (
                realized_profit / realized_revenue_on_known_costs
                if sold_with_known_cost and realized_revenue_on_known_costs != 0
                else None
            ),
            "realized_return_on_known_costs": (
                realized_profit / realized_known_cost_basis
                if sold_with_known_cost and realized_known_cost_basis != 0
                else None
            ),
            "lost_units_with_known_cost": lost_with_known_cost,
            "known_cost_lost": lost_known_cost if lost_with_known_cost else None,
            "known_outcome_cost_basis": (
                known_outcome_cost_basis if has_known_outcome else None
            ),
            "known_outcome_net_profit": (
                known_outcome_net_profit if has_known_outcome else None
            ),
            "known_outcome_return_on_cost": (
                known_outcome_net_profit / known_outcome_cost_basis
                if has_known_outcome and known_outcome_cost_basis != 0
                else None
            ),
            "average_days_to_sale": (
                sum(days_to_sale) / len(days_to_sale) if days_to_sale else None
            ),
        }

    return result
