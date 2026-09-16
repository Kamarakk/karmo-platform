from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping


def _rank_known(
    summary: Mapping[str, Mapping[str, Any]],
    field: str,
    *,
    descending: bool = True,
) -> list[dict[str, Any]]:
    """Rank only entities with a known value for ``field``.

    Missing historical facts remain excluded rather than being coerced to zero.
    Ties are broken by entity identity so repeated runs are deterministic.
    """
    rows = [
        {"name": name, field: values.get(field)}
        for name, values in summary.items()
        if values.get(field) is not None
    ]
    if descending:
        rows.sort(key=lambda row: (-row[field], row["name"]))
    else:
        rows.sort(key=lambda row: (row[field], row["name"]))
    return rows


def summarize_decision_rankings(
    *,
    unit_summary: Mapping[str, Mapping[str, Any]],
    cultivar_summary: Mapping[str, Mapping[str, Any]],
    supplier_summary: Mapping[str, Mapping[str, Any]],
    batch_summary: Mapping[str, Mapping[str, Any]],
    channel_summary: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Expose deterministic rankings for the Phase 1 release questions.

    Rankings use only already-derived known facts. They do not impute missing
    cost, date, fee, shipping, or outcome values.
    """
    profitable_units = {
        unit_id: {"realized_profit_on_known_cost": values.get("realized_profit_on_known_cost")}
        for unit_id, values in unit_summary.items()
    }
    longest_cultivars = {
        name: {"average_days_to_sale": values.get("average_days_to_sale")}
        for name, values in cultivar_summary.items()
    }
    supplier_returns = {
        name: {"known_outcome_return_on_cost": values.get("known_outcome_return_on_cost")}
        for name, values in supplier_summary.items()
    }
    purchase_losses = {
        name: {"known_cost_lost": values.get("known_cost_lost")}
        for name, values in batch_summary.items()
    }
    channel_profit = {
        name: {"known_net_profit_on_known_costs": values.get("known_net_profit_on_known_costs")}
        for name, values in channel_summary.items()
    }

    return {
        "plants_by_realized_profit": _rank_known(
            profitable_units, "realized_profit_on_known_cost", descending=True
        ),
        "purchase_batches_by_known_loss_cost": _rank_known(
            purchase_losses, "known_cost_lost", descending=True
        ),
        "suppliers_by_known_outcome_return": _rank_known(
            supplier_returns, "known_outcome_return_on_cost", descending=True
        ),
        "cultivars_by_average_days_to_sale": _rank_known(
            longest_cultivars, "average_days_to_sale", descending=True
        ),
        "channels_by_known_net_profit": _rank_known(
            channel_profit, "known_net_profit_on_known_costs", descending=True
        ),
    }
