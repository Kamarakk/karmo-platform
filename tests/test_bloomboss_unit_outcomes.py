from datetime import date
from decimal import Decimal

from bloomboss.models import PlantStatus, PlantUnit, Sale
from bloomboss.outcomes import summarize_units


def test_unit_outcomes_report_truthful_realized_profit_and_return():
    units = [
        PlantUnit(
            unit_id="u-profit",
            batch_id="b1",
            cultivar="Alocasia Pink",
            status=PlantStatus.SOLD,
            allocated_landed_cost=Decimal("100"),
            acquired_date=date(2026, 1, 1),
        ),
        PlantUnit(
            unit_id="u-unknown-cost",
            batch_id="b1",
            cultivar="Alocasia Pink",
            status=PlantStatus.SOLD,
            allocated_landed_cost=None,
            acquired_date=date(2026, 1, 5),
        ),
    ]
    sales = [
        Sale(
            sale_id="s-profit",
            unit_id="u-profit",
            channel="Palmstreet",
            sale_price=Decimal("250"),
            sale_date=date(2026, 2, 1),
            selling_fees=Decimal("25"),
            shipping_cost=Decimal("15"),
        ),
        Sale(
            sale_id="s-unknown-cost",
            unit_id="u-unknown-cost",
            channel="Palmstreet",
            sale_price=Decimal("300"),
            sale_date=date(2026, 2, 5),
        ),
    ]

    result = summarize_units(units, sales)

    profitable = result["u-profit"]
    assert profitable["sale_price"] == Decimal("250")
    assert profitable["allocated_landed_cost"] == Decimal("100")
    assert profitable["realized_profit_on_known_cost"] == Decimal("150")
    assert profitable["realized_return_on_known_cost"] == Decimal("1.5")
    assert profitable["known_net_profit"] == Decimal("110")
    assert profitable["days_to_sale"] == 31

    unknown = result["u-unknown-cost"]
    assert unknown["sale_price"] == Decimal("300")
    assert unknown["allocated_landed_cost"] is None
    assert unknown["realized_profit_on_known_cost"] is None
    assert unknown["realized_return_on_known_cost"] is None
    assert unknown["known_net_profit"] is None


def test_unit_outcomes_do_not_mislabel_unsold_inventory_as_realized_profit_or_loss():
    unit = PlantUnit(
        unit_id="u-growing",
        batch_id="b2",
        cultivar="Anthurium",
        status=PlantStatus.GROWING,
        allocated_landed_cost=Decimal("80"),
        acquired_date=date(2026, 3, 1),
    )

    result = summarize_units([unit], [])

    assert result["u-growing"] == {
        "cultivar": "Anthurium",
        "batch_id": "b2",
        "status": "growing",
        "sale_id": None,
        "sale_channel": None,
        "sale_price": None,
        "allocated_landed_cost": Decimal("80"),
        "realized_profit_on_known_cost": None,
        "realized_return_on_known_cost": None,
        "known_net_profit": None,
        "days_to_sale": None,
    }
