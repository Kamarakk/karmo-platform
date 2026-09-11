from datetime import date
from decimal import Decimal

import pytest

from bloomboss.analytics import summarize_business, summarize_suppliers
from bloomboss.data_quality import summarize_history_quality
from bloomboss.ingest import load_history_csv
from bloomboss.models import PlantStatus, PlantUnit, PurchaseBatch, Sale
from bloomboss.validation import validate_history_relationships


def test_unknown_money_stays_unknown(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,sale_price,sale_channel,selling_fees,outbound_shipping_cost\n"
        "B1,U1,Pink Plumbea,sold,185,Palmstreet,,\n",
        encoding="utf-8",
    )
    _, units, sales = load_history_csv(path)
    assert units[0].allocated_landed_cost is None
    assert sales[0].selling_fees is None
    assert sales[0].known_net_revenue is None


def test_summary_uses_realized_values():
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("80"), date(2026, 1, 1)),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("80"), date(2026, 1, 1)),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("185"), date(2026, 1, 11), Decimal("10"), Decimal("15"))
    ]
    summary = summarize_business(units, sales)
    assert summary["total_revenue"] == Decimal("185")
    assert summary["known_landed_cost"] == Decimal("160")
    assert summary["realized_gross_profit_on_known_costs"] == Decimal("105")
    assert summary["sell_through_rate"] == Decimal("0.5")
    assert summary["loss_rate"] == Decimal("0.5")
    assert summary["average_days_to_sale"] == 10
    assert summary["active_inventory_units"] == 0
    assert summary["known_capital_tied_up"] is None
    assert summary["active_inventory_units_with_unknown_cost"] == 0
    assert summary["by_channel"]["Palmstreet"]["sales"] == 1


def test_capital_tied_up_counts_only_active_unsold_known_costs():
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.READY, Decimal("80")),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.GROWING, None),
        PlantUnit("U3", "B1", "Pink Plumbea", PlantStatus.RETAINED, Decimal("55")),
        PlantUnit("U4", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("40")),
        PlantUnit("U5", "B1", "Pink Plumbea", PlantStatus.GIVEAWAY, Decimal("25")),
        PlantUnit("U6", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("60")),
    ]
    sales = [Sale("S1", "U6", "Palmstreet", Decimal("150"))]

    summary = summarize_business(units, sales)

    assert summary["active_inventory_units"] == 3
    assert summary["known_capital_tied_up"] == Decimal("135")
    assert summary["active_inventory_units_with_unknown_cost"] == 1


def test_duplicate_unit_id_fails_visibly(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status\n"
        "B1,U1,Pink Plumbea,growing\n"
        "B1,U1,Pink Plumbea,growing\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate unit_id"):
        load_history_csv(path)


def test_conflicting_repeated_batch_facts_fail(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,supplier\n"
        "B1,U1,Pink Plumbea,growing,Supplier A\n"
        "B1,U2,Pink Plumbea,growing,Supplier B\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicting repeated facts"):
        load_history_csv(path)


def test_negative_money_fails_instead_of_becoming_history(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "batch_id,unit_id,cultivar,status,allocated_landed_cost\n"
        "B1,U1,Pink Plumbea,growing,-20\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="negative money"):
        load_history_csv(path)


def test_supplier_summary_keeps_unknown_supplier_separate():
    batches = [
        PurchaseBatch("B1", "Pink Plumbea", "Supplier A"),
        PurchaseBatch("B2", "Pink Plumbea", None),
    ]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("80")),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.LOST, Decimal("80")),
        PlantUnit("U3", "B2", "Pink Plumbea", PlantStatus.SOLD, None),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("185")),
        Sale("S2", "U3", "Etsy", Decimal("150")),
    ]

    summary = summarize_suppliers(batches, units, sales)
    assert summary["Supplier A"]["units"] == 2
    assert summary["Supplier A"]["sold"] == 1
    assert summary["Supplier A"]["lost"] == 1
    assert summary["Supplier A"]["realized_profit_on_known_costs"] == Decimal("105")
    assert summary["Supplier A"]["sell_through_rate"] == Decimal("0.5")
    assert summary["UNKNOWN"]["units"] == 1
    assert summary["UNKNOWN"]["units_with_known_cost"] == 0


def test_history_quality_reports_coverage_without_imputing_missing_values():
    batches = [
        PurchaseBatch(
            "B1",
            "Pink Plumbea",
            "Supplier A",
            date(2026, 1, 1),
            2,
            Decimal("100"),
            Decimal("20"),
            Decimal("10"),
        ),
        PurchaseBatch("B2", "Cuprea", None),
    ]
    units = [
        PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.SOLD, Decimal("65"), date(2026, 1, 1)),
        PlantUnit("U2", "B1", "Pink Plumbea", PlantStatus.GROWING, Decimal("65"), date(2026, 1, 1)),
        PlantUnit("U3", "B2", "Cuprea", PlantStatus.UNKNOWN, None, None),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("185"), date(2026, 1, 11), Decimal("10"), None)
    ]

    quality = summarize_history_quality(batches, units, sales)

    assert quality["coverage"]["batch_supplier"] == Decimal("0.5")
    assert quality["coverage"]["batch_full_landed_cost"] == Decimal("0.5")
    assert quality["coverage"]["unit_allocated_landed_cost"] == Decimal(2) / Decimal(3)
    assert quality["coverage"]["unit_status"] == Decimal(2) / Decimal(3)
    assert quality["coverage"]["sale_selling_fees"] == Decimal("1")
    assert quality["coverage"]["sale_outbound_shipping"] == Decimal("0")
    assert quality["coverage"]["sale_net_revenue"] == Decimal("0")
    assert quality["missing_counts"]["sold_unit_cost_basis"] == 0


def test_cross_record_validation_reports_broken_relationships():
    batches = [PurchaseBatch("B1", "Pink Plumbea")]
    units = [
        PlantUnit("U1", "B1", "Cuprea", PlantStatus.LOST, acquired_date=date(2026, 2, 1)),
        PlantUnit("U2", "MISSING", "Pink Plumbea", PlantStatus.GROWING),
    ]
    sales = [
        Sale("S1", "U1", "Palmstreet", Decimal("100"), sale_date=date(2026, 1, 31)),
        Sale("S2", "U1", "Etsy", Decimal("95"), sale_date=date(2026, 2, 2)),
        Sale("S3", "UNKNOWN", "Palmstreet", Decimal("75")),
    ]

    issues = validate_history_relationships(batches, units, sales)
    codes = {issue.code for issue in issues}

    assert "CULTIVAR_CONFLICT" in codes
    assert "UNIT_BATCH_MISSING" in codes
    assert "SALE_STATUS_CONFLICT" in codes
    assert "SALE_BEFORE_ACQUISITION" in codes
    assert "MULTIPLE_SALES_FOR_UNIT" in codes
    assert "SALE_UNIT_MISSING" in codes


def test_cross_record_validation_accepts_unknowns_without_inventing_facts():
    batches = [PurchaseBatch("B1", "Pink Plumbea")]
    units = [PlantUnit("U1", "B1", "Pink Plumbea", PlantStatus.UNKNOWN)]
    sales = [Sale("S1", "U1", "Palmstreet", Decimal("100"))]

    assert validate_history_relationships(batches, units, sales) == []
