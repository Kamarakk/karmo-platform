from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .palmstreet import PalmstreetSaleCandidate


_FIELDS = (
    "external_line_item_id",
    "item_title",
    "quantity",
    "sale_price",
    "sale_date",
    "selling_fees",
    "shipping_cost",
)


def summarize_palmstreet_candidate_quality(
    candidates: Iterable[PalmstreetSaleCandidate],
) -> dict:
    """Summarize staged Palmstreet evidence without inventing missing facts.

    Coverage is intentionally descriptive only. It helps an operator decide whether
    a real export is rich enough for canonical reconciliation; it does not promote
    staged rows into BloomBoss sales or treat missing values as zero.
    """
    rows = list(candidates)
    row_count = len(rows)

    field_known_counts = {
        field: sum(getattr(row, field) is not None for row in rows)
        for field in _FIELDS
    }
    field_coverage = {
        field: (
            Decimal(count) / Decimal(row_count)
            if row_count
            else None
        )
        for field, count in field_known_counts.items()
    }

    rows_with_reconciliation_identity = sum(
        row.external_line_item_id is not None for row in rows
    )
    rows_with_realized_financials = sum(
        row.sale_price is not None
        and row.selling_fees is not None
        and row.shipping_cost is not None
        for row in rows
    )

    return {
        "row_count": row_count,
        "field_known_counts": field_known_counts,
        "field_coverage": field_coverage,
        "rows_with_reconciliation_identity": rows_with_reconciliation_identity,
        "reconciliation_identity_coverage": (
            Decimal(rows_with_reconciliation_identity) / Decimal(row_count)
            if row_count
            else None
        ),
        "rows_with_complete_realized_financials": rows_with_realized_financials,
        "complete_realized_financials_coverage": (
            Decimal(rows_with_realized_financials) / Decimal(row_count)
            if row_count
            else None
        ),
    }
