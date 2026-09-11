from datetime import date
from decimal import Decimal

import pytest

from bloomboss.analytics import summarize_business
from bloomboss.ingest import load_history_csv
from bloomboss.models import PlantStatus, PlantUnit, Sale


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
    assert summary["by_channel"]["Palmstreet"]["sales"] == 1


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
