from datetime import date
from decimal import Decimal

from bloomboss.inventory import summarize_inventory_exposure
from bloomboss.models import PlantStatus, PlantUnit, Sale


def test_inventory_exposure_uses_dataset_cutoff_and_preserves_unknowns():
    units = [
        PlantUnit(
            unit_id="u-high",
            batch_id="b1",
            cultivar="Alocasia A",
            status=PlantStatus.READY,
            allocated_landed_cost=Decimal("80"),
            acquired_date=date(2026, 1, 1),
        ),
        PlantUnit(
            unit_id="u-unknown",
            batch_id="b2",
            cultivar="Alocasia B",
            status=PlantStatus.GROWING,
            allocated_landed_cost=None,
            acquired_date=None,
        ),
        PlantUnit(
            unit_id="u-sold",
            batch_id="b3",
            cultivar="Alocasia C",
            status=PlantStatus.SOLD,
            allocated_landed_cost=Decimal("40"),
            acquired_date=date(2026, 2, 1),
        ),
    ]
    sales = [
        Sale(
            sale_id="s1",
            unit_id="u-sold",
            channel="Palmstreet",
            sale_price=Decimal("100"),
            sale_date=date(2026, 3, 1),
        )
    ]

    summary = summarize_inventory_exposure(units, sales)

    assert summary["dataset_cutoff_date"] == date(2026, 3, 1)
    assert summary["active_inventory_units"] == 2
    assert summary["active_inventory_units_with_known_cost"] == 1
    assert summary["active_inventory_units_with_unknown_cost"] == 1
    assert summary["known_capital_tied_up"] == Decimal("80")
    assert [row["unit_id"] for row in summary["units"]] == ["u-high", "u-unknown"]
    assert summary["units"][0]["days_held_to_dataset_cutoff"] == 59
    assert summary["units"][1]["allocated_landed_cost"] is None
    assert summary["units"][1]["days_held_to_dataset_cutoff"] is None


def test_inventory_exposure_excludes_lost_giveaway_and_sold_units():
    units = [
        PlantUnit("u-ready", "b1", "A", PlantStatus.READY, Decimal("25")),
        PlantUnit("u-lost", "b1", "A", PlantStatus.LOST, Decimal("25")),
        PlantUnit("u-give", "b1", "A", PlantStatus.GIVEAWAY, Decimal("25")),
        PlantUnit("u-sale", "b1", "A", PlantStatus.READY, Decimal("25")),
    ]
    sales = [Sale("s1", "u-sale", "Palmstreet", Decimal("60"))]

    summary = summarize_inventory_exposure(units, sales)

    assert summary["active_inventory_units"] == 1
    assert summary["known_capital_tied_up"] == Decimal("25")
    assert [row["unit_id"] for row in summary["units"]] == ["u-ready"]
