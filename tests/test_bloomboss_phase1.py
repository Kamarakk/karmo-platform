from datetime import date
from decimal import Decimal

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
