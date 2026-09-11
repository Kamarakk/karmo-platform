from datetime import date
from decimal import Decimal

from bloomboss.models import PlantStatus, PlantUnit, Sale
from bloomboss.outcomes import summarize_channels, summarize_cultivars


def test_cultivar_outcomes_use_matched_known_costs_only():
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("80"), date(2026, 1, 1)),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("60"), date(2026, 1, 1)),
        PlantUnit("U3", "B2", "Pink Plumbea", PlantStatus.SOLD, None, date(2026, 1, 2)),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("200"), date(2026, 1, 11)),
        Sale("S2", "U3", "Palmstreet", Decimal("150"), date(2026, 1, 22)),
    ]

    summary = summarize_cultivars(units, sales)["Pink Plumbea"]

    assert summary["revenue"] == Decimal("350")
    assert summary["realized_profit_on_known_costs"] == Decimal("120")
    assert summary["realized_gross_margin_on_known_costs"] == Decimal("0.6")
    assert summary["known_cost_lost"] == Decimal("60")
    assert summary["sold_units_with_known_cost"] == 1
    assert summary["average_days_to_sale"] == 15


def test_channel_outcomes_compare_realized_margin_without_imputing_cost():
    units = [
        PlantUnit("U1", "B1", "Cuprea", PlantStatus.SOLD, Decimal("50"), date(2026, 2, 1)),
        PlantUnit("U2", "B2", "Cuprea", PlantStatus.SOLD, None, date(2026, 2, 1)),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("125"), date(2026, 2, 6)),
        Sale("S2", "U2", "Palmstreet", Decimal("75"), date(2026, 2, 11)),
    ]

    summary = summarize_channels(units, sales)["Palmstreet"]

    assert summary["revenue"] == Decimal("200")
    assert summary["average_realized_sale_price"] == Decimal("100")
    assert summary["realized_profit_on_known_costs"] == Decimal("75")
    assert summary["realized_gross_margin_on_known_costs"] == Decimal("0.6")
    assert summary["sold_units_with_known_cost"] == 1
    assert summary["average_days_to_sale"] == 7.5
