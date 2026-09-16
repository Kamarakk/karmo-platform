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
    assert summary["units"][0]["aging_bucket"] == "31_60_days"
    assert summary["units"][1]["allocated_landed_cost"] is None
    assert summary["units"][1]["days_held_to_dataset_cutoff"] is None
    assert summary["units"][1]["aging_bucket"] is None
    assert summary["aging"]["31_60_days"] == {
        "units": 1,
        "known_capital_tied_up": Decimal("80"),
        "units_with_known_cost": 1,
        "units_with_unknown_cost": 0,
    }
    assert summary["aging"]["unknown_age"] == {
        "units": 1,
        "known_capital_tied_up": None,
        "units_with_known_cost": 0,
        "units_with_unknown_cost": 1,
    }


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


def test_inventory_exposure_aging_buckets_preserve_cost_unknowns():
    units = [
        PlantUnit(
            "u-0",
            "b1",
            "A",
            PlantStatus.READY,
            Decimal("10"),
            acquired_date=date(2026, 4, 30),
        ),
        PlantUnit(
            "u-31",
            "b1",
            "A",
            PlantStatus.READY,
            Decimal("20"),
            acquired_date=date(2026, 3, 30),
        ),
        PlantUnit(
            "u-61",
            "b1",
            "A",
            PlantStatus.READY,
            None,
            acquired_date=date(2026, 2, 28),
        ),
        PlantUnit(
            "u-91",
            "b1",
            "A",
            PlantStatus.READY,
            Decimal("40"),
            acquired_date=date(2026, 1, 29),
        ),
        PlantUnit(
            "u-cutoff",
            "b1",
            "A",
            PlantStatus.SOLD,
            Decimal("5"),
            acquired_date=date(2026, 4, 1),
        ),
    ]
    sales = [
        Sale(
            "s-cutoff",
            "u-cutoff",
            "Palmstreet",
            Decimal("50"),
            sale_date=date(2026, 4, 30),
        )
    ]

    summary = summarize_inventory_exposure(units, sales)

    assert summary["aging"]["0_30_days"]["units"] == 1
    assert summary["aging"]["0_30_days"]["known_capital_tied_up"] == Decimal("10")
    assert summary["aging"]["31_60_days"]["units"] == 1
    assert summary["aging"]["31_60_days"]["known_capital_tied_up"] == Decimal("20")
    assert summary["aging"]["61_90_days"]["units"] == 1
    assert summary["aging"]["61_90_days"]["known_capital_tied_up"] is None
    assert summary["aging"]["61_90_days"]["units_with_unknown_cost"] == 1
    assert summary["aging"]["91_plus_days"]["units"] == 1
    assert summary["aging"]["91_plus_days"]["known_capital_tied_up"] == Decimal("40")
