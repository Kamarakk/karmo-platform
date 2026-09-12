from datetime import date
from decimal import Decimal

from bloomboss.models import Provenance
from bloomboss.palmstreet import PalmstreetSaleCandidate
from bloomboss.palmstreet_quality import summarize_palmstreet_candidate_quality


def _candidate(**overrides):
    values = {
        "external_order_id": "P100",
        "external_line_item_id": "L1",
        "item_title": "Alocasia",
        "quantity": 1,
        "sale_price": Decimal("100.00"),
        "sale_date": date(2026, 9, 1),
        "selling_fees": Decimal("10.00"),
        "shipping_cost": Decimal("8.00"),
        "provenance": Provenance(
            source_type="palmstreet_csv",
            source_ref="orders.csv:row:2",
            confidence="reported",
        ),
    }
    values.update(overrides)
    return PalmstreetSaleCandidate(**values)


def test_quality_summary_preserves_missing_fields_as_missing():
    summary = summarize_palmstreet_candidate_quality(
        [
            _candidate(),
            _candidate(
                external_order_id="P101",
                external_line_item_id=None,
                selling_fees=None,
                shipping_cost=None,
            ),
        ]
    )

    assert summary["row_count"] == 2
    assert summary["field_known_counts"]["external_line_item_id"] == 1
    assert summary["field_coverage"]["external_line_item_id"] == Decimal("0.5")
    assert summary["rows_with_reconciliation_identity"] == 1
    assert summary["reconciliation_identity_coverage"] == Decimal("0.5")
    assert summary["rows_with_complete_realized_financials"] == 1
    assert summary["complete_realized_financials_coverage"] == Decimal("0.5")


def test_empty_quality_summary_does_not_invent_zero_percent_coverage():
    summary = summarize_palmstreet_candidate_quality([])

    assert summary["row_count"] == 0
    assert summary["field_coverage"]["sale_price"] is None
    assert summary["reconciliation_identity_coverage"] is None
    assert summary["complete_realized_financials_coverage"] is None
