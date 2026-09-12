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
        Sale(
            "S1",
            "U1",
            "Palmstreet",
            Decimal("200"),
            date(2026, 1, 11),
            selling_fees=Decimal("20"),
            shipping_cost=Decimal("10"),
        ),
        Sale("S2", "U3", "Palmstreet", Decimal("150"), date(2026, 1, 22)),
    ]

    summary = summarize_cultivars(units, sales)["Pink Plumbea"]

    assert summary["revenue"] == Decimal("350")
    assert summary["realized_profit_on_known_costs"] == Decimal("120")
    assert summary["realized_gross_margin_on_known_costs"] == Decimal("0.6")
    assert summary["sold_units_with_known_net_profit"] == 1
    assert summary["known_net_revenue_on_known_costs"] == Decimal("170")
    assert summary["known_net_profit_on_known_costs"] == Decimal("90")
    assert summary["known_net_margin_on_known_costs"] == Decimal("90") / Decimal("170")
    assert summary["known_cost_lost"] == Decimal("60")
    assert summary["sold_units_with_known_cost"] == 1
    assert summary["average_days_to_sale"] == 15


def test_channel_outcomes_compare_realized_margin_without_imputing_cost():
    units = [
        PlantUnit("U1", "B1", "Cuprea", PlantStatus.SOLD, Decimal("50"), date(2026, 2, 1)),
        PlantUnit("U2", "B2", "Cuprea", PlantStatus.SOLD, None, date(2026, 2, 1)),
        PlantUnit("U3", "B3", "Cuprea", PlantStatus.SOLD, Decimal("40"), date(2026, 2, 1)),
    ]
    sales = [
        Sale(
            "S1",
            "U1",
            "Palmstreet",
            Decimal("125"),
            date(2026, 2, 6),
            selling_fees=Decimal("12"),
            shipping_cost=Decimal("8"),
        ),
        Sale("S2", "U2", "Palmstreet", Decimal("75"), date(2026, 2, 11)),
        Sale("S3", "U3", "Palmstreet", Decimal("80"), date(2026, 2, 7)),
    ]

    summary = summarize_channels(units, sales)["Palmstreet"]

    assert summary["revenue"] == Decimal("280")
    assert summary["average_realized_sale_price"] == Decimal("280") / Decimal("3")
    assert summary["realized_profit_on_known_costs"] == Decimal("115")
    assert summary["realized_gross_margin_on_known_costs"] == Decimal("115") / Decimal("205")
    assert summary["sold_units_with_known_cost"] == 2
    assert summary["sold_units_with_known_net_profit"] == 1
    assert summary["known_net_revenue_on_known_costs"] == Decimal("105")
    assert summary["known_net_profit_on_known_costs"] == Decimal("55")
    assert summary["known_net_margin_on_known_costs"] == Decimal("55") / Decimal("105")
    assert summary["average_days_to_sale"] == Decimal("22") / Decimal("3")


def test_known_net_outcomes_stay_unknown_when_fees_or_shipping_are_missing():
    unit = PlantUnit(
        "U1",
        "B1",
        "Variegated Frydek",
        PlantStatus.SOLD,
        Decimal("100"),
        date(2026, 3, 1),
    )
    sale = Sale(
        "S1",
        "U1",
        "Palmstreet",
        Decimal("250"),
        date(2026, 3, 15),
        selling_fees=Decimal("25"),
        shipping_cost=None,
    )

    cultivar = summarize_cultivars([unit], [sale])["Variegated Frydek"]
    channel = summarize_channels([unit], [sale])["Palmstreet"]

    for summary in (cultivar, channel):
        assert summary["sold_units_with_known_net_profit"] == 0
        assert summary["known_net_revenue_on_known_costs"] is None
        assert summary["known_net_profit_on_known_costs"] is None
        assert summary["known_net_margin_on_known_costs"] is None
